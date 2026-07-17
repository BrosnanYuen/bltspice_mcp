from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from fastmcp import Client

from bltspice_mcp.app import create_mcp_server
from bltspice_mcp.config import ServerConfig

PROJECT_ROOT = Path(__file__).resolve().parents[2]
# Keep the example-name contract in this repository instead of requiring a
# separate PyLTSpice source checkout at test time.
EXAMPLE_MANIFEST = PROJECT_ROOT / "tests" / "fixtures" / "pyltspice_example_manifest.json"
TESTFILES = PROJECT_ROOT / "testfiles"

BAD_STATUSES = {
    "invalid input!",
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


async def _execute(client: Client, api_name: str, inputs: dict) -> dict:
    started = (await client.call_tool("execute", {"api_name": api_name, "inputs": inputs})).data
    assert started["status"] == "performing LTspice operation in progress"
    final = await _poll_status(client)
    assert final["status"] not in BAD_STATUSES, f"{api_name} failed with {final}"
    return final


async def _scenario_ltsteps_example(client: Client, temp_dir: Path) -> None:
    await _execute(
        client,
        "LTSpiceLogReader",
        {"new_object_name": "log_reader", "log_filename": str((TESTFILES / "Batch_Test_AD820_15.log").resolve())},
    )
    await _execute(client, "get_step_vars", {"object_name": "log_reader"})
    await _execute(client, "get_measure_names", {"object_name": "log_reader"})


async def _scenario_raw_plotting(client: Client, temp_dir: Path) -> None:
    await _execute(
        client,
        "RawRead",
        {
            "new_object_name": "raw_noise",
            "raw_filename": str((TESTFILES / "Noise.raw").resolve()),
            "traces_to_read": ["V(onoise)"],
        },
    )
    await _execute(client, "get_trace_names", {"object_name": "raw_noise"})


async def _scenario_raw_read_example(client: Client, temp_dir: Path) -> None:
    await _execute(
        client,
        "RawRead",
        {"new_object_name": "raw_tran", "raw_filename": str((TESTFILES / "TRAN - STEP.raw").resolve())},
    )
    await _execute(client, "get_steps", {"object_name": "raw_tran"})
    await _execute(client, "get_raw_property", {"object_name": "raw_tran"})


async def _scenario_raw_write_example(client: Client, temp_dir: Path) -> None:
    await _execute(client, "RawWrite", {"new_object_name": "raw_writer"})
    await _execute(client, "Trace", {"new_object_name": "trace_time", "name": "time", "data": [0.0, 1e-6, 2e-6]})
    await _execute(client, "all_loggers", {})


async def _scenario_run_montecarlo(client: Client, temp_dir: Path) -> None:
    await _execute(
        client,
        "AscEditor",
        {"new_object_name": "sallenkey", "asc_filename": str((TESTFILES / "sallenkey.asc").resolve())},
    )
    await _execute(client, "SimRunner", {"new_object_name": "runner_mc", "output_folder": str((temp_dir / "temp_mc").resolve())})
    await _execute(client, "Montecarlo", {"new_object_name": "mc", "circuit_file": "sallenkey", "runner": "runner_mc"})
    await _execute(client, "set_tolerance", {"object_name": "mc", "ref": "C", "new_tolerance": 0.1, "distribution": "uniform"})


async def _scenario_run_worst_case(client: Client, temp_dir: Path) -> None:
    await _execute(
        client,
        "AscEditor",
        {"new_object_name": "sallenkey_wc", "asc_filename": str((TESTFILES / "sallenkey.asc").resolve())},
    )
    await _execute(client, "SimRunner", {"new_object_name": "runner_wc", "output_folder": str((temp_dir / "temp_wca").resolve())})
    await _execute(
        client,
        "WorstCaseAnalysis",
        {"new_object_name": "wca", "circuit_file": "sallenkey_wc", "runner": "runner_wc"},
    )
    await _execute(client, "set_tolerance", {"object_name": "wca", "ref": "R", "new_tolerance": 0.01})


async def _scenario_sim_runner_asc_example(client: Client, temp_dir: Path) -> None:
    await _execute(client, "SimRunner", {"new_object_name": "runner_asc", "output_folder": str((temp_dir / "temp").resolve())})
    await _execute(
        client,
        "AscEditor",
        {"new_object_name": "batch_asc", "asc_filename": str((TESTFILES / "sallenkey.asc").resolve())},
    )
    await _execute(client, "set_parameters", {"object_name": "batch_asc", "res": 0, "cap": 0.0001})
    await _execute(client, "set_component_value", {"object_name": "batch_asc", "device": "R1", "value": "4k"})


async def _scenario_sim_runner_callback_example(client: Client, temp_dir: Path) -> None:
    await _execute(client, "set_log_level", {"level": 10})
    await _execute(client, "add_log_handler", {"handler_type": "null"})
    await _execute(client, "SimRunner", {"new_object_name": "runner_cb", "output_folder": str((temp_dir / "temp_batch3").resolve())})
    await _execute(
        client,
        "AscEditor",
        {"new_object_name": "batch_cb", "asc_filename": str((TESTFILES / "sallenkey.asc").resolve())},
    )


async def _scenario_sim_runner_callback_process_example(client: Client, temp_dir: Path) -> None:
    await _execute(client, "all_loggers", {})
    await _execute(client, "SimRunner", {"new_object_name": "runner_proc", "output_folder": str((temp_dir / "temp_batch4").resolve())})
    await _execute(
        client,
        "SpiceEditor",
        {"new_object_name": "batch_spice", "netlist_file": str((TESTFILES / "Batch_Test.asc").resolve())},
    )


async def _scenario_sim_runner_example(client: Client, temp_dir: Path) -> None:
    await _execute(client, "SimRunner", {"new_object_name": "runner_main", "output_folder": str((temp_dir / "temp_main").resolve())})
    await _execute(
        client,
        "SpiceEditor",
        {"new_object_name": "batch_net", "netlist_file": str((TESTFILES / "testfile.net").resolve())},
    )
    await _execute(client, "set_parameter", {"object_name": "batch_net", "param": "run", "value": 0})


async def _scenario_sim_stepper_example(client: Client, temp_dir: Path) -> None:
    await _execute(client, "SimRunner", {"new_object_name": "runner_step", "parallel_sims": 4, "output_folder": str((temp_dir / "temp2").resolve())})
    await _execute(
        client,
        "AscEditor",
        {"new_object_name": "step_editor", "asc_filename": str((TESTFILES / "sallenkey.asc").resolve())},
    )
    await _execute(client, "SimStepper", {"new_object_name": "stepper", "editor": "step_editor", "runner": "runner_step"})
    await _execute(client, "set_parameter", {"object_name": "stepper", "param": "run", "value": 0})


async def _scenario_spice_editor_example(client: Client, temp_dir: Path) -> None:
    await _execute(
        client,
        "SpiceEditor",
        {"new_object_name": "noise_editor", "netlist_file": str((TESTFILES / "testfile.net").resolve())},
    )
    await _execute(client, "set_component_value", {"object_name": "noise_editor", "reference": "R1", "value": 11000})
    await _execute(client, "save_netlist", {"object_name": "noise_editor", "run_netlist_file": str((temp_dir / "Noise_updated.net").resolve())})


async def _scenario_sub_circuit_asc_edits(client: Client, temp_dir: Path) -> None:
    await _execute(
        client,
        "AscEditor",
        {"new_object_name": "top_circuit", "asc_filename": str((TESTFILES / "sallenkey.asc").resolve())},
    )
    await _execute(client, "get_components", {"object_name": "top_circuit"})
    await _execute(client, "set_component_value", {"object_name": "top_circuit", "device": "R1", "value": 11})


SCENARIOS = {
    "ltsteps_example.py": _scenario_ltsteps_example,
    "raw_plotting.py": _scenario_raw_plotting,
    "raw_read_example.py": _scenario_raw_read_example,
    "raw_write_example.py": _scenario_raw_write_example,
    "run_montecarlo.py": _scenario_run_montecarlo,
    "run_worst_case.py": _scenario_run_worst_case,
    "sim_runner_asc_example.py": _scenario_sim_runner_asc_example,
    "sim_runner_callback_example.py": _scenario_sim_runner_callback_example,
    "sim_runner_callback_process_example.py": _scenario_sim_runner_callback_process_example,
    "sim_runner_example.py": _scenario_sim_runner_example,
    "sim_stepper_example.py": _scenario_sim_stepper_example,
    "spice_editor_example.py": _scenario_spice_editor_example,
    "sub_circuit_asc_edits.py": _scenario_sub_circuit_asc_edits,
}


def _manifest_example_names() -> list[str]:
    manifest = json.loads(EXAMPLE_MANIFEST.read_text(encoding="utf-8"))
    return sorted(manifest["examples"])


@pytest.mark.asyncio
@pytest.mark.parametrize("example_name", sorted(SCENARIOS.keys()))
async def test_pyltspice_example_mapped_to_mcp_calls(example_name: str, tmp_path: Path):
    assert sorted(SCENARIOS.keys()) == _manifest_example_names()

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

        await SCENARIOS[example_name](client, tmp_path)

        reset_started = (await client.call_tool("stop_reset")).data
        assert reset_started["status"] == "performing LTspice operation in progress"
        reset_final = await _poll_status(client)
        assert reset_final["status"] == "LTspice operation completed!"
