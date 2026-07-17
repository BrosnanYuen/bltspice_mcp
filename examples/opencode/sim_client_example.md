# sim_client_example.py via bltspice_mcp

Use this for LLMs in OpenCode, OpenAI Codex, or Claude Code.

## Goal
Handle README `sim_client_example.py` in the context of `bltspice_mcp`.

## Important Limitation
`sim_client_example.py` uses `SimClient` (PyLTSpice remote client/server API). The `bltspice_mcp` server exposes only:
- `runtime_info`
- `execute_status`
- `stop_reset`
- `execute`

`SimClient` is not part of supported `execute` APIs in this MCP server.

## Recommended MCP-compatible substitute
1. Use `runtime_info` to validate runtime.
2. Use `execute` with `SpiceEditor`/`AscEditor`/`SimRunner` flows for local queued simulation tasks.
3. Poll `execute_status` after each queued operation.

## If you intentionally test unsupported API behavior
1. Call:
```json
bltspice_mcp_execute {"api_name":"SimClient","inputs":{"host":"http://localhost","port":9000}}
```
2. Poll `execute_status`.
3. Expect `invalid input!` as deterministic response.

