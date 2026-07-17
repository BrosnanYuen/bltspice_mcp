from __future__ import annotations

import os
import platform
import shutil
from pathlib import Path
from typing import Any

import psutil

from .config import ServerConfig


def _masked_env_value(value: str | None) -> str | None:
    if value is None:
        return None
    if len(value) <= 6:
        return "***"
    return value[:3] + "***" + value[-3:]


def detect_runtime_mode(config: ServerConfig) -> str:
    system = platform.system().lower()
    if system == "windows":
        return "windows_native"
    if system == "darwin" and config.wine_path in (None, ""):
        return "macos_native"
    return "wine"


def ltspice_process_running(config: ServerConfig) -> bool:
    target_name = Path(config.ltspice_path).name.lower() if config.ltspice_path else ""
    if not target_name:
        return False
    for proc in psutil.process_iter(attrs=["name", "cmdline"]):
        name = (proc.info.get("name") or "").lower()
        cmdline = " ".join(proc.info.get("cmdline") or []).lower()
        if target_name in name or target_name in cmdline:
            return True
    return False


def runtime_info_payload(config: ServerConfig) -> dict[str, Any]:
    runtime_mode = detect_runtime_mode(config)
    ltspice_path = Path(config.ltspice_path).expanduser().resolve() if config.ltspice_path else None
    wine_path = Path(config.wine_path).expanduser().resolve() if config.wine_path else None

    ltspice_exists = bool(ltspice_path and ltspice_path.exists())
    wine_exists = True
    if runtime_mode == "wine":
        wine_exists = bool(wine_path and wine_path.exists())

    env_snapshot = {
        "LTSPICEFOLDER": _masked_env_value(os.getenv("LTSPICEFOLDER")),
        "LTSPICEEXECUTABLE": _masked_env_value(os.getenv("LTSPICEEXECUTABLE")),
        "WINEFOLDER": _masked_env_value(os.getenv("WINEFOLDER")),
        "WINEEXECUTABLE": _masked_env_value(os.getenv("WINEEXECUTABLE")),
    }

    simulator_configured = ltspice_exists and wine_exists

    return {
        "os": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "python": platform.python_version(),
        },
        "mode": runtime_mode,
        "spice_exe": str(ltspice_path) if ltspice_path else "",
        "wine_exe": str(wine_path) if wine_path else "",
        "wine_prefix": str(Path(os.getenv("WINEFOLDER", "~/.wine")).expanduser().resolve()),
        "env": env_snapshot,
        "ltspice_running": ltspice_process_running(config),
        "simulator_configured": simulator_configured,
        "which_wine": shutil.which("wine") or "",
    }
