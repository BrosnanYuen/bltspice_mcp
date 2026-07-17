from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from fastmcp import Context, FastMCP

from .config import ServerConfig
from .responses import invalid_input
from .session import SessionManager, make_ctx_notifier


def _session_id_from_ctx(ctx: Context) -> str:
    sid = getattr(ctx, "session_id", None)
    if sid:
        return str(sid)
    return "default"


def create_mcp_server(config: ServerConfig, project_root: Path) -> FastMCP:
    manager = SessionManager(config=config, project_root=project_root)
    mcp = FastMCP(name=config.mcp_server_name)

    @mcp.tool(name="runtime_info", description="Check LTspice runtime configuration and host diagnostics.")
    async def runtime_info(ctx: Context) -> dict:
        session_id = _session_id_from_ctx(ctx)
        return await manager.enqueue_runtime_info(session_id=session_id, notifier=make_ctx_notifier(ctx))

    @mcp.tool(name="execute_status", description="Poll status of last queued/active LTspice operation.")
    async def execute_status(ctx: Context) -> dict:
        session_id = _session_id_from_ctx(ctx)
        return manager.get_status(session_id=session_id)

    @mcp.tool(name="stop_reset", description="Stop/reset queued operations and clear server object state.")
    async def stop_reset(ctx: Context) -> dict:
        session_id = _session_id_from_ctx(ctx)
        return await manager.enqueue_stop_reset(session_id=session_id, notifier=make_ctx_notifier(ctx))

    @mcp.tool(name="execute", description="Execute one PyLTSpice API request asynchronously.")
    async def execute(api_name: str | None = None, inputs: dict | None = None, ctx: Context | None = None) -> dict:
        api_name = api_name.replace("\"","")
        api_name = api_name.replace("\'","")
        if ctx is None:
            return invalid_input("execute")
        session_id = _session_id_from_ctx(ctx)
        return await manager.enqueue_execute(
            session_id=session_id,
            api_name=api_name,
            inputs=inputs,
            notifier=make_ctx_notifier(ctx),
        )

    return mcp


def run_server(mcp: FastMCP, config: ServerConfig) -> None:
    parsed = urlparse(config.mcp_server_url)
    scheme = parsed.scheme

    if scheme == "stdio":
        mcp.run(transport="stdio")
        return

    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 7543
    # FastMCP streamable-http transport serves both HTTP and HTTPS deployments when proxied.
    # Force MCP endpoint at "/" (not default "/mcp") for both http:// and https:// configs.
    mcp.run(transport="streamable-http", host=host, port=port, path="/")
