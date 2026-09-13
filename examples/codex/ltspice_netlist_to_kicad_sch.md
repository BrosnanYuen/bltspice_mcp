# ltspice_netlist_to_kicad_sch via bltspice_mcp

Use this for LLMs in OpenAI Codex, OpenCode, or Claude Code.

## Goal
Convert a validated LTspice netlist (`.net`) into a validated KiCad schematic
(`.kicad_sch`) with MCP tool calls.

## Preconditions
- MCP server `bltspice_mcp` is connected.
- KiCad symbol libraries are installed and `convert_settings.kicad_path` points at
  them (default `/usr/share/kicad/`).
- Input netlist exists and passes `is_valid_ltspice_netlist_file`, for example
  `/home/brosnan/bltspice_mcp/bltspice_mcp/testfiles/testfile.net`.

## Step-by-step
1. Optional runtime check:
```json
{"tool":"runtime_info","arguments":{}}
```
2. Optional netlist validation:
```json
{"tool":"execute","arguments":{"api_name":"is_valid_ltspice_netlist_file","inputs":{"filepath":"/home/brosnan/bltspice_mcp/bltspice_mcp/testfiles/testfile.net"}}}
```
3. Convert the netlist:
```json
{"tool":"execute","arguments":{"api_name":"ltspice_netlist_to_kicad_sch","inputs":{"ltspice_netlist_filepath":"/home/brosnan/bltspice_mcp/bltspice_mcp/testfiles/testfile.net","kicad_sch_filepath_out":"/tmp/testfile.kicad_sch"}}}
```
4. Poll `execute_status` until the status is no longer in progress.
5. Read `output.result`. Success is `[true, "OK", 0]`; failure is
   `[false, "<error code>", <line>]`.

## Optional per-request settings
Override individual `convert_settings` values for one call:
```json
{"tool":"execute","arguments":{"api_name":"ltspice_netlist_to_kicad_sch","inputs":{"ltspice_netlist_filepath":"/abs/input.net","kicad_sch_filepath_out":"/abs/output.kicad_sch","convert_settings":{"kicad_path":"/usr/share/kicad/"}}}}
```

## Expected error codes
- `INVALID_CONVERT_SETTINGS`
- `INVALID_NETLIST_FILE`
- `NETLIST_READ_ERROR`
- `INVALID_OUTPUT_PATH`
- `WRITE_ERROR`
- `INVALID_GENERATED_KICAD_SCH`
