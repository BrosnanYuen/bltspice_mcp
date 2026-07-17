# raw_read_example.py via bltspice_mcp

Use this for LLMs in OpenCode, OpenAI Codex, or Claude Code.

## Goal
Replicate `PyLTSpice/examples/raw_read_example.py` through MCP calls.

## Preconditions
- MCP server `bltspice_mcp` is connected.
- Use absolute file paths.
- Example raw file: `/home/brosnan/bltspice_mcp/bltspice_mcp/testfiles/TRAN - STEP.raw`

## Step-by-step
1. Check runtime:
```json
{"tool":"runtime_info","arguments":{}}
```
2. Poll until complete:
```json
{"tool":"execute_status","arguments":{}}
```
3. Load RAW into object `raw_tran`:
```json
{"tool":"execute","arguments":{"api_name":"RawRead","inputs":{"new_object_name":"raw_tran","raw_filename":"/home/brosnan/bltspice_mcp/bltspice_mcp/testfiles/TRAN - STEP.raw"}}}
```
4. Poll `execute_status` until not in progress.
5. Get trace names:
```json
{"tool":"execute","arguments":{"api_name":"get_trace_names","inputs":{"object_name":"raw_tran"}}}
```
6. Poll `execute_status`.
7. Get RAW properties:
```json
{"tool":"execute","arguments":{"api_name":"get_raw_property","inputs":{"object_name":"raw_tran"}}}
```
8. Poll `execute_status`.
9. Read traces from object:
```json
{"tool":"execute","arguments":{"api_name":"get_trace","inputs":{"object_name":"raw_tran","trace_ref":"I(R1)"}}}
```
```json
{"tool":"execute","arguments":{"api_name":"get_trace","inputs":{"object_name":"raw_tran","trace_ref":"time"}}}
```
10. Poll after each call.
