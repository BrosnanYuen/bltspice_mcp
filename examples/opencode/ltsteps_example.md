# ltsteps_example.py via bltspice_mcp

Use this for LLMs in OpenCode, OpenAI Codex, or Claude Code.

## Goal
Replicate log parsing with `LTSpiceLogReader` from README.

## Preconditions
- MCP server `bltspice_mcp` is connected.
- Log file: `/home/brosnan/bltspice_mcp/bltspice_mcp/testfiles/Batch_Test_AD820_15.log`

## Step-by-step
1. Create reader object:
```json
bltspice_mcp_execute {"api_name":"LTSpiceLogReader","inputs":{"new_object_name":"log_reader","log_filename":"/home/brosnan/bltspice_mcp/bltspice_mcp/testfiles/Batch_Test_AD820_15.log"}}
```
2. Poll `execute_status`.
3. Get step variables:
```json
bltspice_mcp_execute {"api_name":"get_step_vars","inputs":{"object_name":"log_reader"}}
```
4. Poll `execute_status`.
5. Get measure names:
```json
bltspice_mcp_execute {"api_name":"get_measure_names","inputs":{"object_name":"log_reader"}}
```
6. Poll `execute_status`.
7. Optional: access values by index/field using object methods via `execute`.

