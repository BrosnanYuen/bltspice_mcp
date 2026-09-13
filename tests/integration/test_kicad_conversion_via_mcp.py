from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from electronics_design import is_valid_kicad_sch_file, is_valid_ltspice_netlist_file
from fastmcp import Client

from bltspice_mcp.app import create_mcp_server
from bltspice_mcp.config import ServerConfig

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TESTFILES = PROJECT_ROOT / "testfiles"
KICAD_PATH = Path("/usr/share/kicad")

pytestmark = pytest.mark.skipif(
    not KICAD_PATH.is_dir(),
    reason="KiCad symbol libraries are not installed at /usr/share/kicad",
)


async def _poll_status(client: Client, timeout_s: float = 120.0) -> dict:
    deadline = asyncio.get_event_loop().time() + timeout_s
    while asyncio.get_event_loop().time() < deadline:
        status = (await client.call_tool("execute_status")).data
        if status.get("status") != "performing LTspice operation in progress":
            return status
        await asyncio.sleep(0.05)
    return (await client.call_tool("execute_status")).data


def _server(tmp_path: Path):
    cfg = ServerConfig(
        mcp_server_name="My PyLTSpice MCP Server",
        mcp_server_url="stdio://",
        wine_path=str((tmp_path / "wine").resolve()),
        ltspice_path=str((tmp_path / "LTspice.exe").resolve()),
        enable_extra_tools=True,
        timeout=180,
        convert_settings={"kicad_path": str(KICAD_PATH)},
    )
    return create_mcp_server(config=cfg, project_root=PROJECT_ROOT)


async def _execute(client: Client, api_name: str, inputs: dict) -> dict:
    started = (await client.call_tool("execute", {"api_name": api_name, "inputs": inputs})).data
    assert started["status"] == "performing LTspice operation in progress"
    final = await _poll_status(client)
    assert final["status"] == "LTspice operation completed!", final
    return final


@pytest.mark.asyncio
async def test_kicad_sch_to_ltspice_netlist_via_mcp(tmp_path: Path):
    server = _server(tmp_path)

    async with Client(server) as client:
        output_path = tmp_path / "rc-filter.net"
        final = await _execute(
            client,
            "kicad_sch_to_ltspice_netlist",
            {
                "kicad_sch_filepath": str((TESTFILES / "rc-filter.kicad_sch").resolve()),
                "ltspice_netlist_filepath_out": str(output_path.resolve()),
            },
        )

        assert final["output"]["result"] == [True, "OK", 0]
        assert output_path.exists()
        assert is_valid_ltspice_netlist_file(str(output_path)) == (True, "")
        assert "V1 VDD 0 SINE(2 1 1k 0 0 0) AC 1" in output_path.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_ltspice_netlist_to_kicad_sch_via_mcp(tmp_path: Path):
    server = _server(tmp_path)

    async with Client(server) as client:
        output_path = tmp_path / "testfile.kicad_sch"
        final = await _execute(
            client,
            "ltspice_netlist_to_kicad_sch",
            {
                "ltspice_netlist_filepath": str((TESTFILES / "testfile.net").resolve()),
                "kicad_sch_filepath_out": str(output_path.resolve()),
            },
        )

        assert final["output"]["result"] == [True, "OK", 0]
        assert output_path.exists()
        assert is_valid_kicad_sch_file(str(output_path)) == (True, "")
        assert output_path.read_text(encoding="utf-8").startswith("(kicad_sch")
