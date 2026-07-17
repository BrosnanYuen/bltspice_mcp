# run_montecarlo.py via bltspice_mcp

Use this for LLMs in OpenCode, OpenAI Codex, or Claude Code.

## Goal
Replicate README Montecarlo setup and execution flow through MCP.

## Preconditions
- MCP server `bltspice_mcp` is connected.
- File: `/home/brosnan/bltspice_mcp/bltspice_mcp/testfiles/sallenkey.asc`

## Step-by-step
1. Create AscEditor object:
```json
bltspice_mcp_execute {"api_name":"AscEditor","inputs":{"new_object_name":"sallenkey","asc_filename":"/home/brosnan/bltspice_mcp/bltspice_mcp/testfiles/sallenkey.asc"}}
```
2. Create SimRunner:
```json
bltspice_mcp_execute {"api_name":"SimRunner","inputs":{"new_object_name":"runner_mc","output_folder":"/home/brosnan/bltspice_mcp/bltspice_mcp/testfiles/temp_mc"}}
```
3. Create Montecarlo object:
```json
bltspice_mcp_execute {"api_name":"Montecarlo","inputs":{"new_object_name":"mc","circuit_file":"sallenkey","runner":"runner_mc"}}
```
4. Poll `execute_status` after each call.
5. Set tolerances:
```json
bltspice_mcp_execute {"api_name":"set_tolerance","inputs":{"object_name":"mc","ref":"R","new_tolerance":0.01}}
```
```json
bltspice_mcp_execute {"api_name":"set_tolerance","inputs":{"object_name":"mc","ref":"C","new_tolerance":0.1,"distribution":"uniform"}}
```
```json
bltspice_mcp_execute {"api_name":"set_tolerance","inputs":{"object_name":"mc","ref":"V","new_tolerance":0.1,"distribution":"normal"}}
```
6. Optional run steps (requires simulator):
```json
bltspice_mcp_execute {"api_name":"prepare_testbench","inputs":{"object_name":"mc","num_runs":1000}}
```
```json
bltspice_mcp_execute {"api_name":"run_testbench","inputs":{"object_name":"mc","runs_per_sim":100}}
```
7. Poll after each call and inspect final status.
