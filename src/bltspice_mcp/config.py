from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator


DEFAULT_CONVERT_SETTINGS = {
    "ltspice_windows_path": "C:\\users\\brosnan\\AppData\\Local\\LTspice\\",
    "ltspice_wine_path": "~/.wine/drive_c/users/brosnan/AppData/Local/LTspice/",
    "custom_search_paths": ["./valid_asy/"],
    "minimum_dist": 32,
    "wire_pin_out_dist": 16,
    "grid_size": 16,
    "autoplace_iter": 12,
    "ltspice_version": 4.1,
}


class ConvertSettings(BaseModel):
    """Optional settings used by the electronics-design LTspice converters."""

    model_config = ConfigDict(extra="forbid")

    ltspice_windows_path: str = Field(default=DEFAULT_CONVERT_SETTINGS["ltspice_windows_path"])
    ltspice_wine_path: str = Field(default=DEFAULT_CONVERT_SETTINGS["ltspice_wine_path"])
    custom_search_paths: list[str] = Field(
        default_factory=lambda: list(DEFAULT_CONVERT_SETTINGS["custom_search_paths"])
    )
    minimum_dist: int = Field(default=32, ge=0)
    wire_pin_out_dist: int = Field(default=16, ge=0)
    grid_size: int = Field(default=16, gt=0)
    autoplace_iter: int = Field(default=12, gt=0)
    ltspice_version: float = Field(default=4.1, gt=0)

    @field_validator("ltspice_windows_path", "ltspice_wine_path")
    @classmethod
    def normalize_convert_path_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("custom_search_paths")
    @classmethod
    def validate_custom_search_paths(cls, value: list[str]) -> list[str]:
        return [path.strip() for path in value]


class ServerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mcp_server_name: str = Field(default="My PyLTSpice MCP Server")
    mcp_server_url: str = Field(default="stdio://")
    wine_path: str | None = Field(default=None)
    ltspice_path: str = Field(default="")
    enable_extra_tools: bool = Field(default=True)
    timeout: int = Field(default=600, ge=1)
    convert_settings: ConvertSettings = Field(default_factory=ConvertSettings)

    @field_validator("mcp_server_url")
    @classmethod
    def validate_server_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https", "stdio"}:
            raise ValueError("mcp_server_url must use http://, https://, or stdio://")
        return value

    @field_validator("ltspice_path", "wine_path")
    @classmethod
    def normalize_paths(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            return value
        value = _dedupe_repeated_executable_name(value)
        return str(Path(value).expanduser().resolve())


def _dedupe_repeated_executable_name(path_value: str) -> str:
    path = Path(path_value)
    name = path.name
    half = len(name) // 2
    if (
        len(name) % 2 == 0
        and name[:half].lower() == name[half:].lower()
        and name[:half].lower().endswith(".exe")
    ):
        return str(path.with_name(name[:half]))
    return path_value


DEFAULT_CONFIG = {
    "mcp_server_name": "My PyLTSpice MCP Server",
    "mcp_server_url": "http://localhost:7543",
    "wine_path": "/usr/bin/wine",
    "ltspice_path": "/home/brosnan/.wine/drive_c/Program Files/ADI/LTspice/LTspice.exe",
    "enable_extra_tools": True,
    "timeout": 600,
    "convert_settings": DEFAULT_CONVERT_SETTINGS,
}


def load_config(config_path: Path) -> ServerConfig:
    data = json.loads(config_path.read_text(encoding="utf-8"))
    return ServerConfig.model_validate(data)


def write_default_config(config_path: Path) -> None:
    config_path.write_text(json.dumps(DEFAULT_CONFIG, indent=2) + "\n", encoding="utf-8")
