# raw_write_example.py via bltspice_mcp

Use this for LLMs in OpenCode, OpenAI Codex, or Claude Code.

## Goal
Replicate the README RawWrite snippet using MCP calls.

## Preconditions
- MCP server `bltspice_mcp` is connected.
- Output path is absolute.

## Step-by-step
1. Create writer object:
```json
{"tool":"execute","arguments":{"api_name":"RawWrite","inputs":{"new_object_name":"rw"}}}
```
2. Poll `execute_status` until completion.
3. Create traces:
```json
{"tool":"execute","arguments":{"api_name":"Trace","inputs":{"new_object_name":"tx","name":"time","data":[0.0,0.000001,0.000002]}}}
```
```json
{"tool":"execute","arguments":{"api_name":"Trace","inputs":{"new_object_name":"vy","name":"N001","data":[0.0,0.5,1.0]}}}
```
```json
{"tool":"execute","arguments":{"api_name":"Trace","inputs":{"new_object_name":"vz","name":"N002","data":[1.0,0.5,0.0]}}}
```
4. Poll after each call.
5. Add each trace to writer:
```json
{"tool":"execute","arguments":{"api_name":"add_trace","inputs":{"object_name":"rw","trace":"tx"}}}
```
```json
{"tool":"execute","arguments":{"api_name":"add_trace","inputs":{"object_name":"rw","trace":"vy"}}}
```
```json
{"tool":"execute","arguments":{"api_name":"add_trace","inputs":{"object_name":"rw","trace":"vz"}}}
```
6. Poll after each call.
7. Save RAW:
```json
{"tool":"execute","arguments":{"api_name":"save","inputs":{"object_name":"rw","filename":"/home/brosnan/bltspice_mcp/bltspice_mcp/testfiles/teste_snippet1.raw"}}}
```
8. Poll `execute_status` and confirm `LTspice operation completed!`.
