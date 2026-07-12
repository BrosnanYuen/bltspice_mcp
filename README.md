# ltspice_mcp

Asynchronous MCP server for LTspice + PyLTSpice (`PyLTSpice>=5.5.1`) built with `fastmcp>=3.2.4`.

## What It Does
- Exposes exactly 4 MCP tools: `runtime_info`, `execute_status`, `stop_reset`, `execute`
- Returns `runtime_info` immediately with OS/runtime status
- Keeps `execute` and `stop_reset` non-blocking (`in progress` response)
- Runs operations in per-session FIFO queues
- Sends completion/error notifications to MCP clients
- Uses only PyLTSpice APIs in server logic (no direct `spicelib` usage)
- Includes `execute` helper API `traces_to_csv` to export selected traces from `RawRead` objects into per-wave CSV files

## Project Layout
- `src/ltspice_mcp/` server source code
- `tests/unit/` unit tests
- `tests/integration/` integration tests
- `testfiles/` copied example assets (`.asc/.log/.raw/.asy/.txt/.net`)
- `examples/codex/` and `examples/opencode/` MCP call recipes for LLM agents
- `config.json` server configuration
- `LLM.md` LLM tool-calling reference

## Requirements
- Python 3.11+
- LTspice installed
- Linux/macOS with Wine for Windows LTspice binary

## Quick Setup
```bash
cd /home/brosnan/ltspice_mcp/ltspice_mcp
python3 -m venv .venv
. .venv/bin/activate
pip install -U pip
pip install "PyLTSpice>=6.0.1" "fastmcp>=3.4.4" "electronics-design>=0.1.2" pytest pytest-asyncio
pip install -e .
```

## Configuration
`config.json` (absolute paths required):
```json
{
  "mcp_server_name": "My PyLTSpice MCP Server",
  "mcp_server_url": "http://localhost:7543",
  "wine_path": "/usr/bin/wine",
  "ltspice_path": "/home/brosnan/.wine/drive_c/Program Files/ADI/LTspice/LTspice.exe",
  "enable_extra_tools": true,
  "timeout": 600
}
```

`mcp_server_url` supports `http://`, `https://`, and `stdio://`.

## Run Server
Stdio transport:
```bash
. .venv/bin/activate
python -m ltspice_mcp --config /home/brosnan/ltspice_mcp/ltspice_mcp/config.json
```

## MCP Client Config Examples
### OpenCode
```json
{
  "mcpServers": {
    "ltspice_mcp": {
      "command": "/home/brosnan/ltspice_mcp/ltspice_mcp/.venv/bin/python",
      "args": [
        "-m",
        "ltspice_mcp",
        "--config",
        "/home/brosnan/ltspice_mcp/ltspice_mcp/config.json"
      ]
    }
  }
}
```

### Claude Code
```json
{
  "mcpServers": {
    "ltspice_mcp": {
      "command": "/home/brosnan/ltspice_mcp/ltspice_mcp/.venv/bin/python",
      "args": [
        "-m",
        "ltspice_mcp",
        "--config",
        "/home/brosnan/ltspice_mcp/ltspice_mcp/config.json"
      ]
    }
  }
}
```

### OpenAI Codex
```json
{
  "mcp_servers": {
    "ltspice_mcp": {
      "command": "/home/brosnan/ltspice_mcp/ltspice_mcp/.venv/bin/python",
      "args": [
        "-m",
        "ltspice_mcp",
        "--config",
        "/home/brosnan/ltspice_mcp/ltspice_mcp/config.json"
      ]
    }
  }
}
```

## Response Contract
Server statuses:
- `performing LTspice operation in progress`
- `LTspice operation completed!`
- `invalid input!`
- `file not found!`
- `unsupported file type!`
- `simulator not configured!`
- `simulation failed!`
- `parser failed!`
- `LTspice operation timed out!`
- `internal error`

Each payload includes `operation`. Successful responses include `output`, and optionally `output_obj_name`.

## `traces_to_csv` via `execute`
Convert selected traces from a loaded `RawRead` object into one CSV per wave/step.

Inputs:
- `object_name`: name of a stored `RawRead` object
- `trace_refs`: array of trace names (any length), for example `["V(opamp_input)", "V(opamp_output)"]`
- `output_files`:
  - string prefix/path, example `./sim_wave_` -> writes `./sim_wave_0.csv`, `./sim_wave_1.csv`, ...
  - or array of explicit `.csv` paths with one entry per wave

Example MCP call:
```json
{"tool":"execute","arguments":{"api_name":"traces_to_csv","inputs":{"object_name":"raw","trace_refs":["V(opamp_input)","V(opamp_output)"],"output_files":"./sim_wave_"}}}
```

## `run_ltspice_to_csv.py` Equivalent MCP Flow
Equivalent artifacts are included for the op-amp example workflow:
- netlist fixture: `/home/brosnan/ltspice_mcp/ltspice_mcp/testfiles/opampdouble.net`
- Codex recipe: `/home/brosnan/ltspice_mcp/ltspice_mcp/examples/codex/run_ltspice_to_csv.md`
- OpenCode recipe: `/home/brosnan/ltspice_mcp/ltspice_mcp/examples/opencode/run_ltspice_to_csv.md`
- integration test: `/home/brosnan/ltspice_mcp/ltspice_mcp/tests/integration/test_run_ltspice_to_csv_via_mcp.py`

## Integration Coverage
Integration tests now include:
- Core MCP flow test (`runtime_info`, `execute`, `execute_status`, `stop_reset`)
- Mapping coverage for all `PyLTSpice/examples/*.py` files
- Mapping coverage for all explicit examples referenced in `PyLTSpice/README.md`
- End-to-end `run_ltspice_to_csv.py` style MCP workflow for `opampdouble.net`

## Run Tests (One By One)
```bash
cd /home/brosnan/ltspice_mcp/ltspice_mcp
. .venv/bin/activate
pytest -q tests/unit/test_responses.py
pytest -q tests/unit/test_config.py
pytest -q tests/unit/test_dispatcher.py
pytest -q tests/unit/test_session.py
pytest -q tests/integration/test_mcp_server_integration.py
pytest -q tests/integration/test_examples_via_mcp.py
pytest -q tests/integration/test_readme_examples_via_mcp.py
pytest -q tests/integration/test_run_ltspice_to_csv_via_mcp.py
```

## Notes
- `runtime_info` is immediate and does not require `execute_status` polling.
- Server queues `execute`/`stop_reset` in FIFO per MCP session.
- `execute_status` polls the latest status for queued operations.
- Completion/error notifications are emitted through MCP notification channel.
