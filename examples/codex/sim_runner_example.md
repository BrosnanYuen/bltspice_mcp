# sim_runner_example.py via bltspice_mcp

Use this for LLMs in OpenCode, OpenAI Codex, or Claude Code.

## Goal
Replicate the SimRunner + SpiceEditor workflow from README.

## Preconditions
- MCP server `bltspice_mcp` is connected.
- LTspice runtime configured if you want actual simulation runs.

## Step-by-step
1. Create runner:
```json
{"tool":"execute","arguments":{"api_name":"SimRunner","inputs":{"new_object_name":"runner","output_folder":"/home/brosnan/bltspice_mcp/bltspice_mcp/testfiles/temp"}}}
```
2. Poll `execute_status`.
3. Create netlist object:
```json
{"tool":"execute","arguments":{"api_name":"SpiceEditor","inputs":{"new_object_name":"net","netlist_file":"/home/brosnan/bltspice_mcp/bltspice_mcp/testfiles/testfile.net"}}}
```
4. Poll `execute_status`.
5. Apply edits:
```json
{"tool":"execute","arguments":{"api_name":"set_parameters","inputs":{"object_name":"net","res":0,"cap":0.0001}}}
```
```json
{"tool":"execute","arguments":{"api_name":"set_component_value","inputs":{"object_name":"net","reference":"R2","value":"2k"}}}
```
```json
{"tool":"execute","arguments":{"api_name":"set_component_value","inputs":{"object_name":"net","reference":"R1","value":"4k"}}}
```
```json
{"tool":"execute","arguments":{"api_name":"set_parameter","inputs":{"object_name":"net","param":"run","value":0}}}
```
6. Poll after each call.
7. Run simulation (optional if LTspice configured):
```json
{"tool":"execute","arguments":{"api_name":"run","inputs":{"object_name":"net"}}}
```
8. Poll `execute_status`. If runtime is missing, expect `simulator not configured!` or `simulation failed!`.
