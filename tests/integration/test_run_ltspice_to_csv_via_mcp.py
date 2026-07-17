from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastmcp import Client

from bltspice_mcp.app import create_mcp_server
from bltspice_mcp.config import ServerConfig

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TESTFILES = PROJECT_ROOT / "testfiles"

BAD_STATUSES = {
    "invalid input!",
    "file not found!",
    "unsupported file type!",
    "internal error",
    "LTspice operation timed out!",
}


async def _poll_status(client: Client, timeout_s: float = 10.0) -> dict:
    deadline = asyncio.get_event_loop().time() + timeout_s
    while asyncio.get_event_loop().time() < deadline:
        status = (await client.call_tool("execute_status")).data
        if status.get("status") != "performing LTspice operation in progress":
            return status
        await asyncio.sleep(0.05)
    return (await client.call_tool("execute_status")).data


async def _execute(client: Client, api_name: str, inputs: dict, *, timeout_s: float = 10.0) -> dict:
    started = (await client.call_tool("execute", {"api_name": api_name, "inputs": inputs})).data
    assert started["status"] == "performing LTspice operation in progress"
    final = await _poll_status(client, timeout_s=timeout_s)
    assert final["status"] not in BAD_STATUSES, f"{api_name} failed with {final}"
    return final


@pytest.mark.asyncio
async def test_run_ltspice_to_csv_style_workflow(tmp_path: Path):
    cfg = ServerConfig(
        mcp_server_name="My PyLTSpice MCP Server",
        mcp_server_url="stdio://",
        wine_path=str((tmp_path / "wine").resolve()),
        ltspice_path=str((tmp_path / "LTspice.exe").resolve()),
        enable_extra_tools=True,
        timeout=20,
    )
    server = create_mcp_server(config=cfg, project_root=PROJECT_ROOT)

    async with Client(server) as client:
        runtime = (await client.call_tool("runtime_info")).data
        assert runtime["status"] == "LTspice operation completed!"
        assert runtime["operation"] == "runtime_info"

        await _execute(
            client,
            "SpiceEditor",
            {"new_object_name": "opamp_net", "netlist_file": str((TESTFILES / "opampdouble.net").resolve())},
        )
        await _execute(
            client,
            "SimRunner",
            {"new_object_name": "runner", "output_folder": str((tmp_path / "run_ltspice_to_csv").resolve())},
        )

        run_final = await _execute(
            client,
            "SimRunner.run",
            {
                "object_name": "runner",
                "new_object_name": "run_task",
                "netlist": str((TESTFILES / "opampdouble.net").resolve()),
                "wait_resource": True,
            },
            timeout_s=20.0,
        )
        if run_final["status"] != "LTspice operation completed!":
            assert run_final["status"] in {"simulator not configured!", "simulation failed!"}
            return

        wait_final = await _execute(client, "wait_results", {"object_name": "run_task"}, timeout_s=20.0)
        assert wait_final["status"] == "LTspice operation completed!"
        raw_file, _log_file = wait_final["output"]["result"]
        assert raw_file

        await _execute(client, "RawRead", {"new_object_name": "raw", "raw_filename": raw_file})

        csv_final = await _execute(
            client,
            "traces_to_csv",
            {
                "object_name": "raw",
                "trace_refs": ["V(opamp_input)", "V(opamp_output)"],
                "output_files": str((tmp_path / "sim_wave_").resolve()),
            },
        )
        assert csv_final["status"] == "LTspice operation completed!"
        result = csv_final["output"]["result"]
        assert result["wave_count"] >= 1
        for written in result["written_files"]:
            path = Path(written)
            assert path.exists()
            content = path.read_text(encoding="utf-8")
            assert "xaxis,V(opamp_input),V(opamp_output)" in content
