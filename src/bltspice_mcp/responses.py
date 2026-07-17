from __future__ import annotations

from typing import Any


def in_progress(operation: str) -> dict[str, Any]:
    return {
        "status": "performing LTspice operation in progress",
        "operation": operation,
    }


def completed(operation: str, output: dict[str, Any] | None = None, output_obj_name: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": "LTspice operation completed!",
        "operation": operation,
        "output": output or {},
    }
    if output_obj_name:
        payload["output_obj_name"] = output_obj_name
    return payload


def invalid_input(operation: str) -> dict[str, Any]:
    return {
        "status": "invalid input!",
        "operation": operation,
    }


def file_not_found(operation: str) -> dict[str, Any]:
    return {
        "status": "file not found!",
        "operation": operation,
    }


def unsupported_file_type(operation: str) -> dict[str, Any]:
    return {
        "status": "unsupported file type!",
        "operation": operation,
    }


def simulator_not_configured(operation: str) -> dict[str, Any]:
    return {
        "status": "simulator not configured!",
        "operation": operation,
    }


def simulation_failed(operation: str) -> dict[str, Any]:
    return {
        "status": "simulation failed!",
        "operation": operation,
    }


def parser_failed(operation: str) -> dict[str, Any]:
    return {
        "status": "parser failed!",
        "operation": operation,
    }


def timed_out(operation: str) -> dict[str, Any]:
    return {
        "status": "LTspice operation timed out!",
        "operation": operation,
    }


def internal_error(operation: str) -> dict[str, Any]:
    return {
        "status": "internal error",
        "operation": operation,
    }
