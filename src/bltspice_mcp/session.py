from __future__ import annotations

import asyncio
import json
import multiprocessing
import os
import queue
import signal
import traceback
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import psutil
from mcp.types import LoggingMessageNotification, LoggingMessageNotificationParams

from .config import ServerConfig
from .dispatcher import ApiDispatcher, UnsupportedFileTypeError
from .responses import (
    completed,
    file_not_found,
    in_progress,
    internal_error,
    invalid_input,
    parser_failed,
    simulation_failed,
    simulator_not_configured,
    timed_out,
    unsupported_file_type,
)
from .runtime import runtime_info_payload


Notifier = Callable[[dict[str, Any]], None]
_SESSION_TOKEN_ENV = "BLTSPICE_MCP_SESSION_TOKEN"
_WORKER_READY = "ready"
_WORKER_RESULT = "result"


def _execute_api_response(dispatcher: ApiDispatcher, api_name: str, inputs: dict[str, Any]) -> dict[str, Any]:
    """Execute and normalize one dispatcher call inside a session worker process."""
    try:
        output_obj_name, output = dispatcher.execute_api(api_name, inputs)
        return completed("execute", output=output, output_obj_name=output_obj_name)
    except FileNotFoundError:
        return file_not_found("execute")
    except UnsupportedFileTypeError:
        return unsupported_file_type("execute")
    except (ValueError, TypeError):
        return invalid_input("execute")
    except TimeoutError:
        return timed_out("execute")
    except Exception as exc:  # pragma: no cover - runtime integration guard
        if api_name in {"RawRead", "LTSpiceRawRead", "LTSpiceLogReader", "LTSpiceExport", "opLogReader"}:
            return parser_failed("execute")
        if "simulator" in str(exc).lower() and "config" in str(exc).lower():
            return simulator_not_configured("execute")
        if "simulation" in str(exc).lower() or "run" in api_name.lower():
            return simulation_failed("execute")
        return internal_error("execute")


def _session_process_main(
    config_data: dict[str, Any],
    project_root: str,
    session_token: str,
    command_queue: Any,
    result_queue: Any,
) -> None:
    """Own all dispatcher objects, PyLTSpice threads, and child processes for one MCP session."""
    if hasattr(os, "setsid"):
        os.setsid()
    os.environ[_SESSION_TOKEN_ENV] = session_token

    dispatcher = ApiDispatcher(
        config=ServerConfig.model_validate(config_data),
        project_root=Path(project_root),
    )
    result_queue.put((_WORKER_READY, os.getpid()))

    while True:
        message = command_queue.get()
        if message is None:
            return
        request_id, api_name, inputs = message
        result_queue.put((_WORKER_RESULT, request_id, _execute_api_response(dispatcher, api_name, inputs)))


@dataclass
class OperationRequest:
    operation: str
    handler: Callable[[], Awaitable[dict[str, Any]]]
    timeout: int
    generation: int
    notifier: Notifier | None = None


@dataclass
class SessionState:
    queue: asyncio.Queue[OperationRequest] = field(default_factory=asyncio.Queue)
    worker_task: asyncio.Task[None] | None = None
    current_task: asyncio.Task[dict[str, Any]] | None = None
    reset_task: asyncio.Task[None] | None = None
    reset_done: asyncio.Event = field(default_factory=asyncio.Event)
    generation: int = 0
    process: multiprocessing.Process | None = None
    command_queue: Any = None
    result_queue: Any = None
    session_token: str = field(default_factory=lambda: uuid.uuid4().hex)
    last_status: dict[str, Any] = field(
        default_factory=lambda: completed("idle", output={"message": "no operation yet"})
    )

    def __post_init__(self) -> None:
        self.reset_done.set()


class SessionManager:
    def __init__(self, config: ServerConfig, project_root: Path):
        self.config = config
        self.project_root = project_root
        self._sessions: dict[str, SessionState] = {}
        self._mp_context = multiprocessing.get_context("spawn")

    def get_or_create(self, session_id: str) -> SessionState:
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionState()
        session = self._sessions[session_id]
        if session.worker_task is None or session.worker_task.done():
            session.worker_task = asyncio.create_task(self._worker_loop(session_id, session))
        return session

    async def enqueue_runtime_info(self, session_id: str, notifier: Notifier | None = None) -> dict[str, Any]:
        session = self.get_or_create(session_id)
        session.last_status = completed("runtime_info", output=runtime_info_payload(self.config))
        self._notify(notifier, session.last_status)
        return session.last_status

    async def enqueue_stop_reset(self, session_id: str, notifier: Notifier | None = None) -> dict[str, Any]:
        session = self.get_or_create(session_id)
        if session.reset_task is not None and not session.reset_task.done():
            return session.last_status

        # Invalidate the active request before cancelling it so its completion cannot
        # overwrite the stop_reset status. Drain only work queued before this call;
        # requests submitted after this point wait for reset_done and run normally.
        session.generation += 1
        reset_generation = session.generation
        session.reset_done.clear()
        queued_cleared = 0
        while not session.queue.empty():
            try:
                session.queue.get_nowait()
                session.queue.task_done()
                queued_cleared += 1
            except asyncio.QueueEmpty:
                break

        if session.current_task is not None and not session.current_task.done():
            session.current_task.cancel()

        session.last_status = in_progress("stop_reset")
        session.reset_task = asyncio.create_task(
            self._perform_stop_reset(session, reset_generation, queued_cleared, notifier)
        )
        return session.last_status

    async def _perform_stop_reset(
        self,
        session: SessionState,
        reset_generation: int,
        queued_cleared: int,
        notifier: Notifier | None,
    ) -> None:
        try:
            # Let the queue worker observe cancellation before publishing the final reset status.
            await asyncio.sleep(0)
            kill_stats = await self._kill_session_processes(session)
            result = completed(
                "stop_reset",
                output={
                    "queue_cleared": True,
                    "queued_operations_killed": queued_cleared,
                    "objects_cleared": True,
                    **kill_stats,
                },
            )
            if session.generation == reset_generation:
                session.last_status = result
                self._notify(notifier, result)
        except Exception:  # pragma: no cover - last-resort reset guard
            if session.generation == reset_generation:
                session.last_status = internal_error("stop_reset")
                self._notify(notifier, session.last_status)
        finally:
            session.reset_done.set()

    async def enqueue_execute(
        self,
        session_id: str,
        api_name: str | None,
        inputs: dict[str, Any] | None,
        notifier: Notifier | None = None,
    ) -> dict[str, Any]:
        session = self.get_or_create(session_id)

        if not api_name or not isinstance(api_name, str):
            session.last_status = invalid_input("execute")
            return session.last_status
        if inputs is None:
            inputs = {}
        if not isinstance(inputs, dict):
            session.last_status = invalid_input("execute")
            return session.last_status

        request_generation = session.generation

        async def _handler() -> dict[str, Any]:
            return await self._execute_in_session_process(session, api_name, inputs)

        await session.queue.put(
            OperationRequest("execute", _handler, self.config.timeout, request_generation, notifier)
        )
        session.last_status = in_progress("execute")
        return session.last_status

    def get_status(self, session_id: str) -> dict[str, Any]:
        session = self.get_or_create(session_id)
        return session.last_status

    async def aclose(self) -> None:
        """Terminate every owned session process when the MCP server shuts down."""
        sessions = list(self._sessions.values())
        for session in sessions:
            session.generation += 1
            if session.current_task is not None and not session.current_task.done():
                session.current_task.cancel()
            if session.reset_task is not None and not session.reset_task.done():
                session.reset_task.cancel()

        tasks = [
            task
            for session in sessions
            for task in (session.current_task, session.reset_task)
            if task is not None
        ]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        for session in sessions:
            if session.worker_task is not None and not session.worker_task.done():
                session.worker_task.cancel()
        worker_tasks = [
            session.worker_task
            for session in sessions
            if session.worker_task is not None
        ]
        if worker_tasks:
            await asyncio.gather(*worker_tasks, return_exceptions=True)
        for session in sessions:
            await self._kill_session_processes(session)
        self._sessions.clear()

    async def _worker_loop(self, session_id: str, session: SessionState) -> None:
        while True:
            request = await session.queue.get()
            try:
                await session.reset_done.wait()
                session.current_task = asyncio.create_task(request.handler())
                try:
                    result = await asyncio.wait_for(session.current_task, timeout=request.timeout)
                except asyncio.TimeoutError:
                    await self._kill_session_processes(session)
                    result = timed_out(request.operation)
                except asyncio.CancelledError:
                    result = completed(request.operation, output={"cancelled": True})

                if request.generation == session.generation:
                    session.last_status = result
                    self._notify(request.notifier, result)
            except Exception:  # pragma: no cover - worker guard
                if request.generation == session.generation:
                    session.last_status = internal_error(request.operation)
                    self._notify(request.notifier, session.last_status)
                    self._notify(
                        request.notifier,
                        {
                            "status": "internal error",
                            "operation": request.operation,
                            "traceback": traceback.format_exc(),
                        },
                    )
            finally:
                session.current_task = None
                session.queue.task_done()

    async def _execute_in_session_process(
        self,
        session: SessionState,
        api_name: str,
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        await self._ensure_session_process(session)
        request_id = uuid.uuid4().hex
        session.command_queue.put((request_id, api_name, inputs))

        while True:
            process = session.process
            if process is None or not process.is_alive():
                return internal_error("execute")
            try:
                message = session.result_queue.get_nowait()
            except queue.Empty:
                await asyncio.sleep(0.02)
                continue
            if message[0] == _WORKER_RESULT and message[1] == request_id:
                return message[2]

    async def _ensure_session_process(self, session: SessionState) -> None:
        if session.process is not None and session.process.is_alive():
            return

        self._close_process_handles(session)
        session.command_queue = self._mp_context.Queue()
        session.result_queue = self._mp_context.Queue()
        process = self._mp_context.Process(
            target=_session_process_main,
            args=(
                self.config.model_dump(mode="python"),
                str(self.project_root),
                session.session_token,
                session.command_queue,
                session.result_queue,
            ),
            name=f"bltspice-session-{session.session_token[:12]}",
        )
        process.start()
        session.process = process

        while process.is_alive():
            try:
                message = session.result_queue.get_nowait()
            except queue.Empty:
                await asyncio.sleep(0.02)
                continue
            if message[0] == _WORKER_READY and message[1] == process.pid:
                return
        self._close_process_handles(session)
        raise RuntimeError("session worker failed to start")

    async def _kill_session_processes(self, session: SessionState) -> dict[str, Any]:
        """SIGKILL only processes carrying this session's unguessable ownership token."""
        process = session.process
        worker_pid = process.pid if process is not None else None
        tagged_processes: dict[int, psutil.Process] = {}
        current_uid = os.getuid() if hasattr(os, "getuid") else None

        if worker_pid is not None and process is not None and process.is_alive():
            try:
                tagged_processes[worker_pid] = psutil.Process(worker_pid)
            except psutil.NoSuchProcess:
                pass

        for candidate in psutil.process_iter(["pid", "uids"]):
            try:
                if candidate.pid == os.getpid():
                    continue
                if current_uid is not None and candidate.uids().real != current_uid:
                    continue
                if candidate.environ().get(_SESSION_TOKEN_ENV) == session.session_token:
                    tagged_processes[candidate.pid] = candidate
            except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
                continue

        thread_count = 0
        for candidate in tagged_processes.values():
            try:
                thread_count += candidate.num_threads()
            except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
                pass

        # Kill tagged children first, then the dedicated process group. The group
        # fallback catches children created during the process scan.
        for pid, candidate in tagged_processes.items():
            if pid == worker_pid:
                continue
            try:
                candidate.send_signal(signal.SIGKILL)
            except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
                pass

        worker_killed = False
        if process is not None and worker_pid is not None and process.is_alive():
            try:
                if hasattr(os, "killpg") and os.getpgid(worker_pid) == worker_pid:
                    os.killpg(worker_pid, signal.SIGKILL)
                else:
                    process.kill()
                worker_killed = True
            except (ProcessLookupError, psutil.NoSuchProcess):
                pass

        if process is not None:
            await asyncio.to_thread(process.join, 1.0)
        self._close_process_handles(session)

        return {
            "worker_process_killed": worker_killed,
            "processes_killed": len(tagged_processes),
            "threads_terminated_with_processes": thread_count,
        }

    def _close_process_handles(self, session: SessionState) -> None:
        for process_queue in (session.command_queue, session.result_queue):
            if process_queue is not None:
                try:
                    process_queue.close()
                    process_queue.cancel_join_thread()
                except (OSError, ValueError):
                    pass
        session.command_queue = None
        session.result_queue = None
        session.process = None

    def _notify(self, notifier: Notifier | None, payload: dict[str, Any]) -> None:
        if notifier is None:
            return
        try:
            notifier(payload)
        except Exception:
            return


def make_ctx_notifier(ctx: Any) -> Notifier:
    def _notify(payload: dict[str, Any]) -> None:
        notification = LoggingMessageNotification(
            params=LoggingMessageNotificationParams(
                level="info",
                logger="bltspice_mcp",
                data=json.dumps(payload),
            )
        )
        maybe_coro = ctx.send_notification(notification)
        if asyncio.iscoroutine(maybe_coro):
            asyncio.create_task(maybe_coro)

    return _notify
