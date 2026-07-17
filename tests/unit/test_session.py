import asyncio
from pathlib import Path

import pytest

from bltspice_mcp.config import ServerConfig
from bltspice_mcp.session import SessionManager


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
    status = await manager.enqueue_execute("session-1", api_name="all_loggers", inputs={})
    assert status["status"] == "performing LTspice operation in progress"

    final = await _poll_status(manager, "session-1")
    assert final["status"] == "LTspice operation completed!"
    assert "result" in final["output"]


@pytest.mark.asyncio
async def test_enqueue_execute_invalid_input(config: ServerConfig, tmp_path: Path):
    manager = SessionManager(config=config, project_root=tmp_path)
    status = await manager.enqueue_execute("session-1", api_name=None, inputs={})
    assert status["status"] == "invalid input!"


@pytest.mark.asyncio
async def test_stop_reset_clears_registry(config: ServerConfig, tmp_path: Path):
    manager = SessionManager(config=config, project_root=tmp_path)
    await manager.enqueue_execute("session-1", api_name="RawWrite", inputs={"new_object_name": "rw"})
    await _poll_status(manager, "session-1")

    session = manager.get_or_create("session-1")
    assert "rw" in session.dispatcher.registry

    await manager.enqueue_stop_reset("session-1")
    final = await _poll_status(manager, "session-1")
    assert final["status"] == "LTspice operation completed!"
    assert final["operation"] == "stop_reset"
    assert session.dispatcher.registry == {}


@pytest.mark.asyncio
async def test_runtime_info_returns_immediately(config: ServerConfig, tmp_path: Path):
    manager = SessionManager(config=config, project_root=tmp_path)
    status = await manager.enqueue_runtime_info("session-1")
    assert status["status"] == "LTspice operation completed!"
    assert status["operation"] == "runtime_info"
    assert "os" in status["output"]
    assert "ltspice_running" in status["output"]
