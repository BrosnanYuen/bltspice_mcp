# kicad_sch_to_ltspice_netlist via bltspice_mcp

Use this for LLMs in OpenCode, OpenAI Codex, or Claude Code.

## Goal
Convert a KiCad schematic (`.kicad_sch`) into a validated LTspice netlist (`.net`)
with MCP tool calls.

## Preconditions
- MCP server `bltspice_mcp` is connected.
- KiCad symbol libraries are installed and `convert_settings.kicad_path` points at
  them (default `/usr/share/kicad/`).
- Input schematic exists, for example
  `/home/brosnan/bltspice_mcp/bltspice_mcp/testfiles/rc-filter.kicad_sch`.

## Step-by-step
1. Optional runtime check:
```json
bltspice_mcp_runtime_info {}
```
2. Convert the schematic:
```json
bltspice_mcp_execute {"api_name":"kicad_sch_to_ltspice_netlist","inputs":{"kicad_sch_filepath":"/home/brosnan/bltspice_mcp/bltspice_mcp/testfiles/rc-filter.kicad_sch","ltspice_netlist_filepath_out":"/tmp/rc-filter.net"}}
```
3. Poll `execute_status` until the status is no longer in progress.
4. Read `output.result`. Success is `[true, "OK", 0]`; failure is
   `[false, "<error code>", <line>]`.

## Optional per-request settings
Override individual `convert_settings` values for one call:
```json
bltspice_mcp_execute {"api_name":"kicad_sch_to_ltspice_netlist","inputs":{"kicad_sch_filepath":"/abs/input.kicad_sch","ltspice_netlist_filepath_out":"/abs/output.net","convert_settings":{"kicad_path":"/usr/share/kicad/"}}}
```

## Expected error codes
- `INVALID_CONVERT_SETTINGS`
- `INVALID_KICAD_SCH_FILE`
- `KICAD_SCH_READ_ERROR`
- `KICAD_SCH_PARSE_ERROR`
- `UNKNOWN_KICAD_SYMBOL`
- `UNCONNECTED_SYMBOL_PIN`
- `MISSING_COMPONENT_PAYLOAD`
- `INVALID_OUTPUT_PATH`
- `WRITE_ERROR`
- `INVALID_GENERATED_NETLIST`
