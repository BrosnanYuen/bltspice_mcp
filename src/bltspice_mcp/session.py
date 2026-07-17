from __future__ import annotations

import asyncio
import json
import traceback
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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


@dataclass
class OperationRequest:
    operation: str
    handler: Callable[[], Awaitable[dict[str, Any]]]
    timeout: int
    notifier: Notifier | None = None


@dataclass
class SessionState:
    dispatcher: ApiDispatcher
    queue: asyncio.Queue[OperationRequest] = field(default_factory=asyncio.Queue)
    worker_task: asyncio.Task[None] | None = None
    current_task: asyncio.Task[dict[str, Any]] | None = None
    last_status: dict[str, Any] = field(default_factory=lambda: completed("idle", output={"message": "no operation yet"}))


class SessionManager:
    def __init__(self, config: ServerConfig, project_root: Path):
        self.config = config
        self.project_root = project_root
        self._sessions: dict[str, SessionState] = {}

    def get_or_create(self, session_id: str) -> SessionState:
        if session_id not in self._sessions:
            dispatcher = ApiDispatcher(config=self.config, project_root=self.project_root)
            self._sessions[session_id] = SessionState(dispatcher=dispatcher)
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

        async def _handler() -> dict[str, Any]:
            # Cancel active task and clear queued work, then clear object registry.
            if session.current_task and not session.current_task.done():
                session.current_task.cancel()
            while not session.queue.empty():
                try:
                    session.queue.get_nowait()
                    session.queue.task_done()
                except asyncio.QueueEmpty:
                    break
            session.dispatcher.reset()
            return completed("stop_reset", output={"queue_cleared": True, "objects_cleared": True})

        await session.queue.put(OperationRequest("stop_reset", _handler, self.config.timeout, notifier))
        session.last_status = in_progress("stop_reset")
        return session.last_status

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

        async def _handler() -> dict[str, Any]:
            try:
                output_obj_name, output = session.dispatcher.execute_api(api_name, inputs)
                return completed("execute", output=output, output_obj_name=output_obj_name)
            except FileNotFoundError:
                return file_not_found("execute")
            except UnsupportedFileTypeError:
                return unsupported_file_type("execute")
            except (ValueError, TypeError):
                return invalid_input("execute")
            except TimeoutError:
                return timed_out("execute")
            except Exception as exc:  # pragma: no cover - catch-all for runtime integrations
                # Parse-heavy operations get parser_failed for better diagnostics.
                if api_name in {"RawRead", "LTSpiceRawRead", "LTSpiceLogReader", "LTSpiceExport", "opLogReader"}:
                    return parser_failed("execute")
                if "simulator" in str(exc).lower() and "config" in str(exc).lower():
                    return simulator_not_configured("execute")
                if "simulation" in str(exc).lower() or "run" in api_name.lower():
                    return simulation_failed("execute")
                return internal_error("execute")

        await session.queue.put(OperationRequest("execute", _handler, self.config.timeout, notifier))
        session.last_status = in_progress("execute")
        return session.last_status

    def get_status(self, session_id: str) -> dict[str, Any]:
        session = self.get_or_create(session_id)
        return session.last_status

    async def _worker_loop(self, session_id: str, session: SessionState) -> None:
        while True:
            request = await session.queue.get()
            try:
                session.current_task = asyncio.create_task(request.handler())
                try:
                    result = await asyncio.wait_for(session.current_task, timeout=request.timeout)
                except asyncio.TimeoutError:
                    result = timed_out(request.operation)
                except asyncio.CancelledError:
                    result = completed(request.operation, output={"cancelled": True})

                session.last_status = result
                self._notify(request.notifier, result)
            except Exception:  # pragma: no cover - worker guard
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
