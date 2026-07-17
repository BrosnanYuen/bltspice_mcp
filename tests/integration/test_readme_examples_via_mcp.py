from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from fastmcp import Client

from bltspice_mcp.app import create_mcp_server
from bltspice_mcp.config import ServerConfig

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_MANIFEST = PROJECT_ROOT / "tests" / "fixtures" / "pyltspice_example_manifest.json"
TESTFILES = PROJECT_ROOT / "testfiles"

BAD_STATUSES = {
    "file not found!",
    "unsupported file type!",
    "internal error",
    "LTspice operation timed out!",
}


async def _poll_status(client: Client, timeout_s: float = 5.0) -> dict:
    deadline = asyncio.get_event_loop().time() + timeout_s
    while asyncio.get_event_loop().time() < deadline:
        status = (await client.call_tool("execute_status")).data
        if status.get("status") != "performing LTspice operation in progress":
            return status
        await asyncio.sleep(0.05)
    return (await client.call_tool("execute_status")).data


async def _execute(client: Client, api_name: str, inputs: dict, *, allow_invalid: bool = False) -> dict:
    started = (await client.call_tool("execute", {"api_name": api_name, "inputs": inputs})).data
    assert started["status"] == "performing LTspice operation in progress"
    final = await _poll_status(client)
    if allow_invalid:
        assert final["status"] in {"LTspice operation completed!", "invalid input!"}
    else:
        assert final["status"] not in BAD_STATUSES, f"{api_name} failed with {final}"
        assert final["status"] in {"LTspice operation completed!", "invalid input!", "simulator not configured!", "simulation failed!", "parser failed!"}
    return final


def _readme_example_names() -> list[str]:
    manifest = json.loads(EXAMPLE_MANIFEST.read_text(encoding="utf-8"))
    return sorted(manifest["readme_examples"])


async def _raw_read_example(client: Client, temp_dir: Path) -> None:
    await _execute(
        client,
        "RawRead",
        {"new_object_name": "raw_tran", "raw_filename": str((TESTFILES / "TRAN - STEP.raw").resolve())},
    )
    await _execute(client, "get_trace_names", {"object_name": "raw_tran"})
    await _execute(client, "get_steps", {"object_name": "raw_tran"})


async def _raw_write_example(client: Client, temp_dir: Path) -> None:
    await _execute(client, "RawWrite", {"new_object_name": "raw_writer"})
    await _execute(client, "Trace", {"new_object_name": "trace_time", "name": "time", "data": [0.0, 1e-6, 2e-6]})
    await _execute(client, "all_loggers", {})


async def _sim_runner_example(client: Client, temp_dir: Path) -> None:
    await _execute(client, "SimRunner", {"new_object_name": "runner", "output_folder": str((temp_dir / "temp").resolve())})
    await _execute(
        client,
        "SpiceEditor",
        {"new_object_name": "netlist", "netlist_file": str((TESTFILES / "testfile.net").resolve())},
    )
    await _execute(client, "set_parameters", {"object_name": "netlist", "res": 0, "cap": 0.0001})
    await _execute(client, "set_component_value", {"object_name": "netlist", "reference": "R1", "value": "4k"})


async def _run_montecarlo_example(client: Client, temp_dir: Path) -> None:
    await _execute(
        client,
        "AscEditor",
        {"new_object_name": "sallenkey_mc", "asc_filename": str((TESTFILES / "sallenkey.asc").resolve())},
    )
    await _execute(client, "SimRunner", {"new_object_name": "runner_mc", "output_folder": str((temp_dir / "temp_mc").resolve())})
    await _execute(client, "Montecarlo", {"new_object_name": "mc", "circuit_file": "sallenkey_mc", "runner": "runner_mc"})
    await _execute(client, "set_tolerance", {"object_name": "mc", "ref": "R", "new_tolerance": 0.01})


async def _run_worst_case_example(client: Client, temp_dir: Path) -> None:
    await _execute(
        client,
        "AscEditor",
        {"new_object_name": "sallenkey_wc", "asc_filename": str((TESTFILES / "sallenkey.asc").resolve())},
    )
    await _execute(client, "SimRunner", {"new_object_name": "runner_wc", "output_folder": str((temp_dir / "temp_wca").resolve())})
    await _execute(client, "WorstCaseAnalysis", {"new_object_name": "wca", "circuit_file": "sallenkey_wc", "runner": "runner_wc"})
    await _execute(client, "set_tolerance", {"object_name": "wca", "ref": "C", "new_tolerance": 0.1})


async def _ltsteps_example(client: Client, temp_dir: Path) -> None:
    await _execute(
        client,
        "LTSpiceLogReader",
        {"new_object_name": "log_reader", "log_filename": str((TESTFILES / "Batch_Test_AD820_15.log").resolve())},
    )
    await _execute(client, "get_step_vars", {"object_name": "log_reader"})
    await _execute(client, "get_measure_names", {"object_name": "log_reader"})


async def _sim_client_example(client: Client, temp_dir: Path) -> None:
    # README sim_client example is out-of-scope for this MCP API surface.
    await _execute(client, "SimClient", {"host": "http://localhost", "port": 9000}, allow_invalid=True)


README_SCENARIOS = {
    "raw_read_example.py": _raw_read_example,
    "raw_write_example.py": _raw_write_example,
    "sim_runner_example.py": _sim_runner_example,
    "run_montecarlo.py": _run_montecarlo_example,
    "run_worst_case.py": _run_worst_case_example,
    "ltsteps_example.py": _ltsteps_example,
    "sim_client_example.py": _sim_client_example,
}


@pytest.mark.asyncio
@pytest.mark.parametrize("example_name", sorted(README_SCENARIOS.keys()))
async def test_readme_examples_via_mcp(example_name: str, tmp_path: Path):
    assert sorted(README_SCENARIOS.keys()) == _readme_example_names()

    cfg = ServerConfig(
        mcp_server_name="My PyLTSpice MCP Server",
        mcp_server_url="stdio://",
        wine_path=str((tmp_path / "wine").resolve()),
        ltspice_path=str((tmp_path / "LTspice.exe").resolve()),
        enable_extra_tools=True,
        timeout=10,
    )
    server = create_mcp_server(config=cfg, project_root=PROJECT_ROOT)

    async with Client(server) as client:
        runtime_started = (await client.call_tool("runtime_info")).data
        assert runtime_started["status"] == "LTspice operation completed!"
        assert runtime_started["operation"] == "runtime_info"
        assert "os" in runtime_started["output"]
        assert "ltspice_running" in runtime_started["output"]

        await README_SCENARIOS[example_name](client, tmp_path)

        reset_started = (await client.call_tool("stop_reset")).data
        assert reset_started["status"] == "performing LTspice operation in progress"
        reset_final = await _poll_status(client)
        assert reset_final["status"] == "LTspice operation completed!"
