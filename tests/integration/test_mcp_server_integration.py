import asyncio
from pathlib import Path

import pytest
from fastmcp import Client

from bltspice_mcp.app import create_mcp_server
from bltspice_mcp.config import ServerConfig

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TESTFILES = PROJECT_ROOT / "testfiles"


async def _poll_execute_status(client: Client, timeout_s: float = 3.0) -> dict:
    deadline = asyncio.get_event_loop().time() + timeout_s
    while asyncio.get_event_loop().time() < deadline:
        status = (await client.call_tool("execute_status")).data
        if status.get("status") != "performing LTspice operation in progress":
            return status
        await asyncio.sleep(0.05)
    return (await client.call_tool("execute_status")).data


@pytest.mark.asyncio
@pytest.mark.parametrize("server_url", ["stdio://", "http://localhost:7543/", "https://localhost:7543/"])
async def test_mcp_server_tools_end_to_end(tmp_path: Path, server_url: str):
    cfg = ServerConfig(
        mcp_server_name="My PyLTSpice MCP Server",
        mcp_server_url=server_url,
        wine_path=str((tmp_path / "wine").resolve()),
        ltspice_path=str((tmp_path / "LTspice.exe").resolve()),
        enable_extra_tools=True,
        timeout=3,
    )
    server = create_mcp_server(config=cfg, project_root=tmp_path)

    async with Client(server) as client:
        tools = await client.list_tools()
        tool_names = {tool.name for tool in tools}
        assert {"runtime_info", "execute_status", "stop_reset", "execute"}.issubset(tool_names)

        runtime_started = (await client.call_tool("runtime_info")).data
        assert runtime_started["status"] == "LTspice operation completed!"
        assert runtime_started["operation"] == "runtime_info"
        assert "output" in runtime_started
        assert "os" in runtime_started["output"]
        assert "ltspice_running" in runtime_started["output"]

        execute_started = (await client.call_tool("execute", {"api_name": "all_loggers", "inputs": {}})).data
        assert execute_started["status"] == "performing LTspice operation in progress"

        execute_final = await _poll_execute_status(client)
        assert execute_final["status"] == "LTspice operation completed!"
        assert execute_final["operation"] == "execute"
        assert "result" in execute_final["output"]

        rawread_started = (
            await client.call_tool(
                "execute",
                {
                    "api_name": "RawRead",
                    "inputs": {
                        "new_object_name": "raw_tran",
                        "raw_filename": str((TESTFILES / "TRAN - STEP.raw").resolve()),
                    },
                },
            )
        ).data
        assert rawread_started["status"] == "performing LTspice operation in progress"
        rawread_final = await _poll_execute_status(client)
        assert rawread_final["status"] == "LTspice operation completed!"

        traces_csv_started = (
            await client.call_tool(
                "execute",
                {
                    "api_name": "traces_to_csv",
                    "inputs": {
                        "object_name": "raw_tran",
                        "trace_refs": ["V(in)", "V(out)"],
                        "output_files": str((tmp_path / "sim_wave_").resolve()),
                    },
                },
            )
        ).data
        assert traces_csv_started["status"] == "performing LTspice operation in progress"
        traces_csv_final = await _poll_execute_status(client)
        assert traces_csv_final["status"] == "LTspice operation completed!"
        result = traces_csv_final["output"]["result"]
        assert result["wave_count"] >= 1
        assert len(result["written_files"]) == result["wave_count"]
        for csv_path in result["written_files"]:
            path = Path(csv_path)
            assert path.exists()
            assert path.suffix.lower() == ".csv"

        missing_file = (
            await client.call_tool(
                "execute",
                {
                    "api_name": "RawRead",
                    "inputs": {"raw_file": str((tmp_path / "missing.raw").resolve())},
                },
            )
        ).data
        assert missing_file["status"] == "performing LTspice operation in progress"

        missing_final = await _poll_execute_status(client)
        assert missing_final["status"] == "file not found!"

        reset_started = (await client.call_tool("stop_reset")).data
        assert reset_started["status"] == "performing LTspice operation in progress"

        reset_final = await _poll_execute_status(client)
        assert reset_final["status"] == "LTspice operation completed!"
        assert reset_final["operation"] == "stop_reset"
