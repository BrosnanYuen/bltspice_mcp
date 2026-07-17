from __future__ import annotations

import csv
import logging
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import PyLTSpice
from PyLTSpice import (
    AscEditor,
    LTSpiceLogReader,
    LTspice,
    RawRead,
    RawWrite,
    SimCommander,
    SimRunner,
    SpiceCircuit,
    SpiceEditor,
    SpiceReadException,
    Trace,
    add_log_handler,
    all_loggers,
    set_log_level,
)
from PyLTSpice.log.logfile_data import LTComplex, LogfileData
from PyLTSpice.log.ltsteps import LTSpiceExport, reformat_LTSpice_export
from PyLTSpice.log.semi_dev_op_reader import opLogReader
from PyLTSpice.sim.process_callback import ProcessCallback
from PyLTSpice.sim.sim_stepping import SimStepper
from PyLTSpice.sim.tookit.montecarlo import Montecarlo
from PyLTSpice.sim.tookit.worst_case import WorstCaseAnalysis
from PyLTSpice.utils.detect_encoding import EncodingDetectError, detect_encoding
from PyLTSpice.utils.sweep_iterators import sweep, sweep_iterators, sweep_log, sweep_log_n, sweep_n

from .config import ConvertSettings, ServerConfig
from .conversion import CONVERSION_APIS, CONVERSION_CALLABLES


class UnsupportedFileTypeError(ValueError):
    pass


READ_APIS = {
    "RawRead",
    "LTSpiceRawRead",
    "SpiceCircuit",
    "SpiceEditor",
    "AscEditor",
    "LTSpiceLogReader",
    "LTSpiceExport",
    "opLogReader",
    "detect_encoding",
}


class ApiDispatcher:
    def __init__(self, config: ServerConfig, project_root: Path):
        self.config = config
        self.project_root = project_root.resolve()
        self.registry: dict[str, Any] = {}

    def reset(self) -> None:
        self.registry.clear()

    def execute_api(self, api_name: str, inputs: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
        if not isinstance(inputs, dict):
            raise ValueError("inputs must be a JSON object")

        # Dotted API names call methods on object instances.
        if "." in api_name:
            cls_name, method_name = api_name.split(".", 1)
            return self._execute_method(cls_name, method_name, inputs)

        # Allow direct object method calls like set_tolerance.
        if api_name not in self._callables() and "object_name" in inputs:
            target = self._resolve_object_by_name(str(inputs["object_name"]))
            kwargs = self._normalize_kwargs(api_name, {k: v for k, v in inputs.items() if k != "object_name"})
            result = getattr(target, api_name)(**kwargs)
            return None, {"result": self._serialize(result)}

        if api_name not in self._callables():
            raise ValueError(f"unknown api_name: {api_name}")

        kwargs = self._normalize_kwargs(api_name, dict(inputs))
        if api_name in CONVERSION_APIS:
            kwargs = self._apply_convert_settings(kwargs)

        if api_name in READ_APIS:
            self._validate_read_inputs(api_name, kwargs)

        if api_name == "add_log_handler":
            kwargs = self._normalize_add_handler(kwargs)

        callable_obj = self._callables()[api_name]
        result = callable_obj(**kwargs)

        output_obj_name = None
        new_name = inputs.get("new_object_name")
        if new_name:
            if not isinstance(new_name, str):
                raise ValueError("new_object_name must be a string")
            self.registry[new_name] = result
            output_obj_name = new_name

        return output_obj_name, {"result": self._serialize(result)}

    def _execute_method(self, class_name: str, method_name: str, inputs: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
        target = self._resolve_target_for_method(class_name, inputs)
        kwargs = {k: v for k, v in inputs.items() if k not in {"object_name", "new_object_name"}}
        kwargs = self._normalize_kwargs(f"{class_name}.{method_name}", kwargs)
        result = getattr(target, method_name)(**kwargs)

        output_obj_name = None
        new_name = inputs.get("new_object_name")
        if new_name:
            if not isinstance(new_name, str):
                raise ValueError("new_object_name must be a string")
            self.registry[new_name] = result
            output_obj_name = new_name

        return output_obj_name, {"result": self._serialize(result)}

    def _resolve_target_for_method(self, class_name: str, inputs: dict[str, Any]) -> Any:
        object_name = inputs.get("object_name")
        if object_name:
            return self._resolve_object_by_name(str(object_name))

        matches = [obj for obj in self.registry.values() if obj.__class__.__name__ == class_name]
        if not matches:
            raise ValueError(f"no object found for class {class_name}")
        if len(matches) > 1:
            raise ValueError(f"multiple objects found for class {class_name}; provide object_name")
        return matches[0]

    def _resolve_object_by_name(self, object_name: str) -> Any:
        if object_name not in self.registry:
            raise ValueError(f"unknown object_name: {object_name}")
        return self.registry[object_name]

    def _normalize_kwargs(self, api_name: str, kwargs: dict[str, Any]) -> dict[str, Any]:
        normalized: dict[str, Any] = {}
        for key, value in kwargs.items():
            if key == "new_object_name":
                continue
            if key == "convert_settings":
                normalized[key] = value
                continue
            normalized[key] = self._normalize_value(key, value)

        # Backward-compatible alias.
        if api_name == "LTSpiceRawRead":
            api_name = "RawRead"
        return normalized

    def _apply_convert_settings(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        configured_settings = self.config.convert_settings.model_dump()
        requested_settings = kwargs.get("convert_settings")

        if requested_settings is None:
            effective_settings: dict[str, Any] = configured_settings
        elif isinstance(requested_settings, ConvertSettings):
            effective_settings = {
                **configured_settings,
                **requested_settings.model_dump(),
            }
        elif isinstance(requested_settings, Mapping):
            effective_settings = {
                **configured_settings,
                **dict(requested_settings),
            }
        else:
            raise ValueError("convert_settings must be a JSON object")

        return {
            **kwargs,
            "convert_settings": self._normalize_convert_settings(effective_settings),
        }

    def _normalize_convert_settings(self, settings: Mapping[str, Any]) -> dict[str, Any]:
        normalized = dict(settings)

        for key in ("ltspice_wine_path",):
            if key in normalized:
                normalized[key] = self._normalize_convert_path(normalized[key], preserve_windows=False)

        if "custom_search_paths" in normalized:
            search_paths = normalized["custom_search_paths"]
            if isinstance(search_paths, str):
                search_paths = [search_paths]
            if isinstance(search_paths, (list, tuple)):
                normalized["custom_search_paths"] = [
                    self._normalize_convert_path(path, preserve_windows=False)
                    for path in search_paths
                ]

        # Keep Windows paths in Windows syntax. Path.resolve() on a Linux host
        # would incorrectly turn e.g. C:\\users\\... into a project-local path.
        if "ltspice_windows_path" in normalized:
            normalized["ltspice_windows_path"] = self._normalize_convert_path(
                normalized["ltspice_windows_path"],
                preserve_windows=True,
            )

        return normalized

    def _normalize_convert_path(self, value: Any, *, preserve_windows: bool) -> Any:
        if not isinstance(value, str):
            return value
        value = value.strip()
        if not value:
            return value
        if preserve_windows and self._looks_like_windows_path(value):
            return value

        path = Path(value).expanduser()
        if not path.is_absolute():
            path = self.project_root / path
        return str(path.resolve())

    @staticmethod
    def _looks_like_windows_path(value: str) -> bool:
        return (
            len(value) >= 3
            and value[1] == ":"
            and value[2] in {"\\", "/"}
        ) or value.startswith("\\\\")

    def _normalize_value(self, key: str, value: Any) -> Any:
        if isinstance(value, str):
            # Resolve object references by name when the key implies one.
            if key in {"circuit_file", "runner", "editor", "simulator", "spice_tool", "object_name"}:
                if value in self.registry:
                    return self.registry[value]

            # Resolve likely path-like values to absolute host paths.
            if any(token in key.lower() for token in ["file", "path", "folder"]):
                return str((self.project_root / value).resolve()) if not Path(value).is_absolute() else value

        if isinstance(value, list):
            return [self._normalize_value(key, item) for item in value]
        if isinstance(value, dict):
            return {k: self._normalize_value(k, v) for k, v in value.items()}
        return value

    def _normalize_add_handler(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        handler_spec = kwargs.get("handler") or kwargs.get("handler_type")
        if handler_spec is None:
            raise ValueError("add_log_handler requires handler or handler_type")

        if isinstance(handler_spec, str):
            lowered = handler_spec.lower()
            if lowered == "null":
                return {"handler": logging.NullHandler()}
            if lowered == "stream":
                return {"handler": logging.StreamHandler()}
            raise ValueError("unsupported handler_type")

        if isinstance(handler_spec, dict):
            lowered = str(handler_spec.get("type", "")).lower()
            if lowered == "null":
                return {"handler": logging.NullHandler()}
            if lowered == "stream":
                return {"handler": logging.StreamHandler()}
            raise ValueError("unsupported handler.type")

        raise ValueError("handler must be a supported string or object")

    def _validate_read_inputs(self, api_name: str, kwargs: dict[str, Any]) -> None:
        file_arg_keys = [
            "raw_file",
            "raw_filename",
            "netlist_file",
            "circuit_file",
            "asc_filename",
            "logfile",
            "log_filename",
            "input_file",
            "export_file",
            "export_filename",
            "file",
            "filename",
        ]
        candidate = None
        for key in file_arg_keys:
            if key in kwargs and isinstance(kwargs[key], str):
                candidate = kwargs[key]
                break

        if candidate is None:
            return

        path = Path(candidate)
        if not path.exists():
            raise FileNotFoundError(str(path))

        ext = path.suffix.lower()
        if api_name in {"AscEditor"} and ext not in {".asc", ".net", ".cir"}:
            raise UnsupportedFileTypeError("AscEditor supports .asc/.net/.cir")
        if api_name in {"SpiceEditor", "SpiceCircuit"} and ext not in {".asc", ".net", ".cir"}:
            raise UnsupportedFileTypeError("Spice editor supports .asc/.net/.cir")
        if api_name in {"RawRead", "LTSpiceRawRead"} and ext != ".raw":
            raise UnsupportedFileTypeError("RawRead supports .raw")
        if api_name in {"LTSpiceLogReader", "opLogReader"} and ext != ".log":
            raise UnsupportedFileTypeError("log reader supports .log")

    def _traces_to_csv(self, object_name: Any, trace_refs: Any, output_files: Any) -> dict[str, Any]:
        raw_obj = object_name
        if raw_obj is None:
            raise ValueError("traces_to_csv requires object_name")

        if not isinstance(trace_refs, list) or not trace_refs:
            raise ValueError("trace_refs must be a non-empty array of trace names")
        if not all(isinstance(trace_ref, str) and trace_ref.strip() for trace_ref in trace_refs):
            raise ValueError("trace_refs must contain only non-empty strings")

        steps = raw_obj.get_steps()
        wave_count = len(steps) if steps else 1
        if wave_count <= 0:
            wave_count = 1

        csv_paths = self._resolve_csv_paths(output_files, wave_count)
        written_files: list[str] = []

        for wave in range(wave_count):
            csv_path = csv_paths[wave]
            csv_path.parent.mkdir(parents=True, exist_ok=True)
            xaxis_values = self._get_xaxis_values(raw_obj, wave)
            trace_waves = [raw_obj.get_trace(trace_ref).get_wave(wave) for trace_ref in trace_refs]

            row_count = min([len(xaxis_values), *[len(trace_wave) for trace_wave in trace_waves]])
            with csv_path.open("w", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(["xaxis", *trace_refs])
                for idx in range(row_count):
                    writer.writerow([xaxis_values[idx], *[trace_wave[idx] for trace_wave in trace_waves]])
            written_files.append(str(csv_path.resolve()))

        return {
            "written_files": written_files,
            "wave_count": wave_count,
            "trace_refs": trace_refs,
        }

    def _resolve_csv_paths(self, output_files: Any, wave_count: int) -> list[Path]:
        if isinstance(output_files, str):
            base = Path(output_files)
            suffix = base.suffix.lower()
            if suffix == ".csv":
                if wave_count != 1:
                    raise ValueError("output_files as a .csv file requires exactly one wave")
                return [base]
            return [Path(f"{output_files}{wave}.csv") for wave in range(wave_count)]

        if isinstance(output_files, list):
            if len(output_files) != wave_count:
                raise ValueError("output_files list length must match number of waves")
            csv_paths = [Path(path) for path in output_files]
            if not all(path.suffix.lower() == ".csv" for path in csv_paths):
                raise ValueError("all output_files entries must end with .csv")
            return csv_paths

        raise ValueError("output_files must be a string prefix/path or an array of .csv file paths")

    def _get_xaxis_values(self, raw_obj: Any, wave: int) -> Any:
        try:
            return raw_obj.get_axis(wave)
        except Exception:
            trace_names = raw_obj.get_trace_names()
            if "time" in trace_names:
                return raw_obj.get_trace("time").get_wave(wave)
            if not trace_names:
                raise ValueError("raw object has no traces to derive xaxis values")
            return raw_obj.get_trace(trace_names[0]).get_wave(wave)

    def _callables(self) -> dict[str, Any]:
        callables = {
            "all_loggers": lambda: all_loggers(),
            "set_log_level": lambda level: set_log_level(level),
            "add_log_handler": lambda handler: add_log_handler(handler),
            "RawRead": RawRead,
            "LTSpiceRawRead": RawRead,
            "RawWrite": RawWrite,
            "Trace": Trace,
            "SpiceReadException": SpiceReadException,
            "SpiceCircuit": SpiceCircuit,
            "SpiceEditor": SpiceEditor,
            "AscEditor": AscEditor,
            "SimRunner": SimRunner,
            "SimCommander": SimCommander,
            "LTspice": lambda: LTspice,
            "LTSpiceLogReader": LTSpiceLogReader,
            "reformat_LTSpice_export": reformat_LTSpice_export,
            "LTSpiceExport": LTSpiceExport,
            "LogfileData": LogfileData,
            "LTComplex": LTComplex,
            "opLogReader": opLogReader,
            "ProcessCallback": ProcessCallback,
            "SimStepper": SimStepper,
            "Montecarlo": Montecarlo,
            "WorstCaseAnalysis": WorstCaseAnalysis,
            "sweep": sweep,
            "sweep_n": sweep_n,
            "sweep_log": sweep_log,
            "sweep_log_n": sweep_log_n,
            "sweep_iterators": sweep_iterators,
            "EncodingDetectError": EncodingDetectError,
            "detect_encoding": detect_encoding,
            "traces_to_csv": self._traces_to_csv,
        }
        callables.update(CONVERSION_CALLABLES)
        return callables

    def _serialize(self, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, Path):
            return str(value.resolve())
        if isinstance(value, dict):
            return {str(k): self._serialize(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [self._serialize(v) for v in value]

        return {
            "type": f"{value.__class__.__module__}.{value.__class__.__name__}",
            "repr": repr(value),
        }
