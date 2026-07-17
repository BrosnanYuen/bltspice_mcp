# LLM Tool-Calling Guide (OpenCode, Claude Code, OpenAI Codex)

## Core MCP Tools
| Tool | Input | Purpose |
|---|---|---|
| `runtime_info` | `{}` | Return runtime diagnostics for LTspice/Wine/OS and simulator readiness immediately. |
| `execute_status` | `{}` | Poll latest status for the session queue. |
| `stop_reset` | `{}` | Cancel/reset queue and object registry for current session. |
| `execute` | `{"api_name": "...", "inputs": {...}}` | Queue one PyLTSpice API operation. |

## Async Behavior
1. Call `runtime_info` for immediate diagnostics (no queue, no polling).
2. Call `stop_reset` or `execute`.
3. Immediate response for queued operations: `performing LTspice operation in progress`.
4. Poll with `execute_status` until status is not in-progress.
5. Read `output` and optional `output_obj_name` on completion.

## Standard Response Shapes
In progress:
```json
{"status":"performing LTspice operation in progress","operation":"execute"}
```
Completed:
```json
{"status":"LTspice operation completed!","operation":"execute","output_obj_name":"obj1","output":{}}
```
Immediate `runtime_info` response:
```json
{"status":"LTspice operation completed!","operation":"runtime_info","output":{"os":{},"ltspice_running":false}}
```
Error statuses:
- `invalid input!`
- `file not found!`
- `unsupported file type!`
- `simulator not configured!`
- `simulation failed!`
- `parser failed!`
- `LTspice operation timed out!`
- `internal error`

## `execute` API Names
`inputs.new_object_name` may be provided to store newly created objects.

| api_name | Typical inputs | Description |
|---|---|---|
| `all_loggers` | none | Return logger names used by PyLTSpice stack. |
| `set_log_level` | `level:int` | Set global logging level. |
| `add_log_handler` | `handler_type:"null"|"stream"` | Add handler to known loggers. |
| `RawRead` | `raw_filename`, `traces_to_read?`, `dialect?`, `verbose?` | Read LTspice RAW file. |
| `LTSpiceRawRead` | same as `RawRead` | Alias of `RawRead`. |
| `traces_to_csv` | `object_name`, `trace_refs:[...]`, `output_files` | Export selected traces from `RawRead` object into per-wave CSV files. |
| `RawWrite` | `**kwargs` | Build/write LTspice RAW content. |
| `Trace` | `name`, `data`, `whattype?` | Create RAW trace. |
| `SpiceCircuit` | `netlist source/path` | Generic spice circuit API. |
| `SpiceEditor` | `netlist_file`, `encoding?`, `create_blank?` | Netlist editor. |
| `AscEditor` | `asc_filename`, `encoding?` | LTspice ASC editor. |
| `SimRunner` | `simulator?`, `parallel_sims?`, `timeout?`, `verbose?`, `output_folder?` | Batch runner. |
| `SimCommander` | `netlist_file`, `parallel_sims?`, `timeout?`, `verbose?`, `encoding?`, `simulator?` | Legacy editor+runner. |
| `LTspice` | none | Return LTspice simulator class. |
| `LTSpiceLogReader` | `log_filename`, `read_measures?`, `step_set?` | Parse LTspice log step/measure data. |
| `reformat_LTSpice_export` | `input_file`, `output_file?` | Reformat export text. |
| `LTSpiceExport` | `export_filename` | Parse LTspice export file. |
| `LogfileData` | ctor args | Generic logfile dataset holder. |
| `LTComplex` | ctor args | Complex-value wrapper. |
| `opLogReader` | `filename` | Parse op-point log sections. |
| `ProcessCallback` | ctor args | Callback base class. |
| `SimStepper` | `editor`, `runner` | Parameter/model sweep controller. |
| `Montecarlo` | `circuit_file`, `runner` | Monte Carlo analysis toolkit. |
| `WorstCaseAnalysis` | `circuit_file`, `runner` | Worst-case analysis toolkit. |
| `is_valid_ltspice_netlist_file` | `filepath` | Validate an LTspice netlist file. |
| `ltspice_netlist_to_asc` | `netlist_filepath`, `asc_filepath_out` | Convert an LTspice netlist to an ASC schematic using configured `convert_settings`. |
| `sweep` | `stop` OR `start,stop,step` | Linear sweep iterator. |
| `sweep_n` | `start,stop,n` | Linear sweep fixed points. |
| `sweep_log` | `start,stop,step_factor/base` | Logarithmic sweep iterator. |
| `sweep_log_n` | `start,stop,n` | Logarithmic sweep fixed points. |
| `sweep_iterators` | none | Multi-parameter sweep helper object. |
| `EncodingDetectError` | ctor args | Encoding exception type. |
| `detect_encoding` | `file/path`, `encodings?`, `**kwargs` | Detect text encoding. |

MCP argument names follow the PyLTSpice constructor signatures exactly. Use `asc_filename` for `AscEditor` and `editor` for `SimStepper`; legacy aliases are not supported.

For `ltspice_netlist_to_asc`, `convert_settings` is optional in `inputs`. When
it is omitted, the server uses the optional `convert_settings` section from
`config.json`, including defaults for every setting. Values supplied in a
request override the configured values for that request.

## Method Calls via `execute`
Server supports direct object method invocation when `inputs.object_name` is present.
Examples:
- `{"api_name":"set_tolerance","inputs":{"object_name":"mc","ref":"C","new_tolerance":0.1,"distribution":"uniform"}}`
- `{"api_name":"get_trace_names","inputs":{"object_name":"raw1"}}`
- `{"api_name":"save_netlist","inputs":{"object_name":"ed1","run_netlist_file":"/abs/path/out.net"}}`

Dotted names are also supported (e.g. `SpiceEditor.run`).

## `traces_to_csv` Details
- `trace_refs` accepts any-length arrays and writes all listed traces as CSV columns.
- CSV header is `xaxis` plus each item in `trace_refs`.
- `output_files` can be:
  - A string prefix/path such as `./sim_wave_` (creates `./sim_wave_0.csv`, `./sim_wave_1.csv`, ...)
  - An explicit array of `.csv` file paths with one entry per wave

Example:
```json
{"tool":"execute","arguments":{"api_name":"traces_to_csv","inputs":{"object_name":"raw","trace_refs":["V(opamp_input)","V(opamp_output)"],"output_files":"./sim_wave_"}}}
```

## `run_ltspice_to_csv.py` Equivalent Calls
Use this sequence to mirror `netlistexample/run_ltspice_to_csv.py`:
1. `SpiceEditor` on `/home/brosnan/bltspice_mcp/bltspice_mcp/testfiles/opampdouble.net`
2. `SimRunner` with an output folder
3. `SimRunner.run` with `new_object_name:"run_task"`
4. `wait_results` on `run_task` to get `raw_file`
5. `RawRead` using that raw file
6. `traces_to_csv` with
   - `trace_refs:["V(opamp_input)","V(opamp_output)"]`
   - `output_files:"./sim_wave_"`

Codex/OpenCode ready recipes:
- `/home/brosnan/bltspice_mcp/bltspice_mcp/examples/codex/run_ltspice_to_csv.md`
- `/home/brosnan/bltspice_mcp/bltspice_mcp/examples/opencode/run_ltspice_to_csv.md`

## Example Workflow
```json
{"tool":"runtime_info","arguments":{}}
```
```json
{"tool":"execute","arguments":{"api_name":"AscEditor","inputs":{"new_object_name":"sallenkey","asc_filename":"/abs/path/testfiles/sallenkey.asc"}}}
```
```json
{"tool":"execute","arguments":{"api_name":"SimRunner","inputs":{"new_object_name":"runner1","output_folder":"/abs/path/temp_mc"}}}
```
```json
{"tool":"execute","arguments":{"api_name":"Montecarlo","inputs":{"new_object_name":"mc","circuit_file":"sallenkey","runner":"runner1"}}}
```
```json
{"tool":"execute","arguments":{"api_name":"set_tolerance","inputs":{"object_name":"mc","ref":"C","new_tolerance":0.1,"distribution":"uniform"}}}
```

## Integration-Test Mapping
Integration suites exercise these flows through MCP client calls:
- `tests/integration/test_examples_via_mcp.py` for the checked-in example-name manifest
- `tests/integration/test_readme_examples_via_mcp.py` for the checked-in README example-name list
