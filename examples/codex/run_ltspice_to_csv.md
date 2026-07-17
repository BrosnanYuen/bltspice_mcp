# run_ltspice_to_csv.py via bltspice_mcp

Use this for LLMs in OpenAI Codex, OpenCode, or Claude Code.

## Goal
Replicate `netlistexample/run_ltspice_to_csv.py` with MCP tool calls:
- run LTspice on `opampdouble.net`
- load produced `.raw`
- export `V(opamp_input)` and `V(opamp_output)` to per-wave CSV files

## Preconditions
- MCP server `bltspice_mcp` is connected.
- `opampdouble.net` exists at `/home/brosnan/bltspice_mcp/bltspice_mcp/testfiles/opampdouble.net`.
- LTspice runtime is configured if you need an actual simulation run.

## Step-by-step
1. Optional runtime check:
```json
{"tool":"runtime_info","arguments":{}}
```
2. Create netlist/editor object:
```json
{"tool":"execute","arguments":{"api_name":"SpiceEditor","inputs":{"new_object_name":"opamp_net","netlist_file":"/home/brosnan/bltspice_mcp/bltspice_mcp/testfiles/opampdouble.net"}}}
```
3. Poll `execute_status`.
4. Create simulation runner:
```json
{"tool":"execute","arguments":{"api_name":"SimRunner","inputs":{"new_object_name":"runner","output_folder":"/home/brosnan/bltspice_mcp/bltspice_mcp/testfiles"}}}
```
5. Poll `execute_status`.
6. Start simulation task:
```json
{"tool":"execute","arguments":{"api_name":"SimRunner.run","inputs":{"object_name":"runner","new_object_name":"run_task","netlist":"/home/brosnan/bltspice_mcp/bltspice_mcp/testfiles/opampdouble.net","wait_resource":true}}}
```
7. Poll `execute_status`.
8. Get generated raw/log paths:
```json
{"tool":"execute","arguments":{"api_name":"wait_results","inputs":{"object_name":"run_task"}}}
```
9. Poll `execute_status`, then read `output.result[0]` as `raw_file`.
10. Load raw object:
```json
{"tool":"execute","arguments":{"api_name":"RawRead","inputs":{"new_object_name":"raw","raw_filename":"<raw_file_from_wait_results>"}}}
```
11. Poll `execute_status`.
12. Export traces to CSV:
```json
{"tool":"execute","arguments":{"api_name":"traces_to_csv","inputs":{"object_name":"raw","trace_refs":["V(opamp_input)","V(opamp_output)"],"output_files":"./sim_wave_"}}}
```
13. Poll `execute_status`. Expect files like `./sim_wave_0.csv`, `./sim_wave_1.csv`, ...

## Expected runtime caveat
If LTspice/Wine are not configured, `SimRunner.run` may return:
- `simulator not configured!`
- `simulation failed!`
