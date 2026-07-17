# run_worst_case.py via bltspice_mcp

Use this for LLMs in OpenCode, OpenAI Codex, or Claude Code.

## Goal
Replicate README WorstCaseAnalysis workflow through MCP.

## Preconditions
- MCP server `bltspice_mcp` is connected.
- File: `/home/brosnan/bltspice_mcp/bltspice_mcp/testfiles/sallenkey.asc`

## Step-by-step
1. Create AscEditor:
```json
{"tool":"execute","arguments":{"api_name":"AscEditor","inputs":{"new_object_name":"sallenkey","asc_filename":"/home/brosnan/bltspice_mcp/bltspice_mcp/testfiles/sallenkey.asc"}}}
```
2. Create SimRunner:
```json
{"tool":"execute","arguments":{"api_name":"SimRunner","inputs":{"new_object_name":"runner_wc","output_folder":"/home/brosnan/bltspice_mcp/bltspice_mcp/testfiles/temp_wca"}}}
```
3. Create WorstCaseAnalysis:
```json
{"tool":"execute","arguments":{"api_name":"WorstCaseAnalysis","inputs":{"new_object_name":"wca","circuit_file":"sallenkey","runner":"runner_wc"}}}
```
4. Poll `execute_status` after each step.
5. Set tolerances:
```json
{"tool":"execute","arguments":{"api_name":"set_tolerance","inputs":{"object_name":"wca","ref":"R","new_tolerance":0.01}}}
```
```json
{"tool":"execute","arguments":{"api_name":"set_tolerance","inputs":{"object_name":"wca","ref":"C","new_tolerance":0.1}}}
```
```json
{"tool":"execute","arguments":{"api_name":"set_tolerance","inputs":{"object_name":"wca","ref":"V","new_tolerance":0.1}}}
```
6. Optional run (needs configured simulator):
```json
{"tool":"execute","arguments":{"api_name":"run_testbench","inputs":{"object_name":"wca"}}}
```
7. Poll status and read outcome.
