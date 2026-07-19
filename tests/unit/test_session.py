import asyncio
import multiprocessing
import os
from pathlib import Path
import subprocess
import sys
import time

import psutil
import pytest

from bltspice_mcp.config import ServerConfig
from bltspice_mcp.session import SessionManager, _SESSION_TOKEN_ENV


def _tagged_process_tree(session_token: str, ready_queue) -> None:
    os.setsid()
    child_env = os.environ.copy()
    child_env[_SESSION_TOKEN_ENV] = session_token
    child = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        env=child_env,
    )
    ready_queue.put((os.getpid(), child.pid))
    time.sleep(60)


@pytest.fixture
def config(tmp_path: Path) -> ServerConfig:
    return ServerConfig(
        mcp_server_name="x",
        mcp_server_url="stdio://",
        wine_path=str(tmp_path / "wine"),
        ltspice_path=str(tmp_path / "ltspice.exe"),
        enable_extra_tools=True,
        timeout=2,
    )


async def _poll_status(manager: SessionManager, sid: str, timeout_s: float = 2.0) -> dict:
    deadline = asyncio.get_event_loop().time() + timeout_s
    while asyncio.get_event_loop().time() < deadline:
        status = manager.get_status(sid)
        if status.get("status") != "performing LTspice operation in progress":
            return status
        await asyncio.sleep(0.05)
    return manager.get_status(sid)


@pytest.mark.asyncio
async def test_enqueue_execute_and_complete(config: ServerConfig, tmp_path: Path):
    manager = SessionManager(config=config, project_root=tmp_path)
    try:
        status = await manager.enqueue_execute("session-1", api_name="all_loggers", inputs={})
        assert status["status"] == "performing LTspice operation in progress"

        final = await _poll_status(manager, "session-1")
        assert final["status"] == "LTspice operation completed!"
        assert "result" in final["output"]
    finally:
        await manager.aclose()


@pytest.mark.asyncio
async def test_enqueue_execute_invalid_input(config: ServerConfig, tmp_path: Path):
    manager = SessionManager(config=config, project_root=tmp_path)
    status = await manager.enqueue_execute("session-1", api_name=None, inputs={})
    assert status["status"] == "invalid input!"


@pytest.mark.asyncio
async def test_stop_reset_clears_registry(config: ServerConfig, tmp_path: Path):
    manager = SessionManager(config=config, project_root=tmp_path)
    try:
        await manager.enqueue_execute("session-1", api_name="RawWrite", inputs={"new_object_name": "rw"})
        created = await _poll_status(manager, "session-1")
        assert created["output_obj_name"] == "rw"

        session = manager.get_or_create("session-1")
        original_pid = session.process.pid

        await manager.enqueue_stop_reset("session-1")
        final = await _poll_status(manager, "session-1")
        assert final["status"] == "LTspice operation completed!"
        assert final["operation"] == "stop_reset"
        assert final["output"]["worker_process_killed"] is True
        assert session.process is None

        # The object lived in the killed session process and must no longer resolve.
        await manager.enqueue_execute("session-1", api_name="save", inputs={"object_name": "rw", "filename": "x.raw"})
        missing_object = await _poll_status(manager, "session-1")
        assert missing_object["status"] == "invalid input!"
        assert session.process.pid != original_pid
    finally:
        await manager.aclose()


@pytest.mark.asyncio
async def test_stop_reset_isolated_to_one_session(config: ServerConfig, tmp_path: Path):
    manager = SessionManager(config=config, project_root=tmp_path)
    try:
        await manager.enqueue_execute("session-a", api_name="RawWrite", inputs={"new_object_name": "a"})
        raw_file = Path(__file__).parents[2] / "testfiles" / "TRAN - STEP.raw"
        await manager.enqueue_execute(
            "session-b",
            api_name="RawRead",
            inputs={"new_object_name": "b", "raw_filename": str(raw_file)},
        )
        await _poll_status(manager, "session-a")
        await _poll_status(manager, "session-b")

        session_a = manager.get_or_create("session-a")
        session_b = manager.get_or_create("session-b")
        pid_a = session_a.process.pid
        pid_b = session_b.process.pid

        await manager.enqueue_stop_reset("session-a")
        reset = await _poll_status(manager, "session-a")
        assert reset["operation"] == "stop_reset"
        assert session_a.process is None
        assert session_b.process.is_alive()
        assert session_b.process.pid == pid_b

        await manager.enqueue_execute("session-b", api_name="get_trace_names", inputs={"object_name": "b"})
        session_b_result = await _poll_status(manager, "session-b")
        assert session_b_result["status"] == "LTspice operation completed!"
        assert "time" in session_b_result["output"]["result"]
        assert not psutil.pid_exists(pid_a)
    finally:
        await manager.aclose()


@pytest.mark.asyncio
async def test_session_kill_terminates_owned_process_tree(config: ServerConfig, tmp_path: Path):
    manager = SessionManager(config=config, project_root=tmp_path)
    process_context = multiprocessing.get_context("spawn")
    ready_queue = process_context.Queue()
    session = manager.get_or_create("session-tree")
    process = process_context.Process(
        target=_tagged_process_tree,
        args=(session.session_token, ready_queue),
    )
    process.start()
    session.process = process
    worker_pid, child_pid = await asyncio.to_thread(ready_queue.get, True, 5)

    try:
        stats = await manager._kill_session_processes(session)
        assert stats["worker_process_killed"] is True
        assert stats["processes_killed"] >= 2
        assert stats["threads_terminated_with_processes"] >= 2
        assert worker_pid != child_pid
        assert not psutil.pid_exists(worker_pid)
        child = psutil.Process(child_pid) if psutil.pid_exists(child_pid) else None
        assert child is None or child.status() == psutil.STATUS_ZOMBIE
    finally:
        if process.is_alive():
            process.kill()
            process.join(timeout=1)
        ready_queue.close()
        ready_queue.cancel_join_thread()
        await manager.aclose()


@pytest.mark.asyncio
async def test_runtime_info_returns_immediately(config: ServerConfig, tmp_path: Path):
    manager = SessionManager(config=config, project_root=tmp_path)
    status = await manager.enqueue_runtime_info("session-1")
    assert status["status"] == "LTspice operation completed!"
    assert status["operation"] == "runtime_info"
    assert "os" in status["output"]
    assert "ltspice_running" in status["output"]
