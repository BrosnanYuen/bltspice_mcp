from pathlib import Path

import pytest

from bltspice_mcp.config import ConvertSettings, ServerConfig, load_config


def test_config_supports_required_schemes(tmp_path: Path):
    cfg = ServerConfig(
        mcp_server_name="x",
        mcp_server_url="stdio://",
        wine_path=str(tmp_path / "wine"),
        ltspice_path=str(tmp_path / "ltspice.exe"),
        enable_extra_tools=True,
        timeout=10,
    )
    assert cfg.mcp_server_url == "stdio://"


@pytest.mark.parametrize("url", ["http://localhost:7543", "https://localhost:7543", "stdio://"])
def test_config_url_variants(url: str, tmp_path: Path):
    cfg = ServerConfig(
        mcp_server_name="x",
        mcp_server_url=url,
        wine_path=str(tmp_path / "wine"),
        ltspice_path=str(tmp_path / "ltspice.exe"),
        enable_extra_tools=True,
        timeout=10,
    )
    assert cfg.mcp_server_url == url


def test_invalid_scheme_rejected(tmp_path: Path):
    with pytest.raises(ValueError):
        ServerConfig(
            mcp_server_name="x",
            mcp_server_url="ftp://localhost:7543",
            wine_path=str(tmp_path / "wine"),
            ltspice_path=str(tmp_path / "ltspice.exe"),
            enable_extra_tools=True,
            timeout=10,
        )


def test_ltspice_path_dedupes_repeated_exe_suffix():
    cfg = ServerConfig(
        mcp_server_name="x",
        mcp_server_url="stdio://",
        wine_path="/usr/bin/wine",
        ltspice_path="/tmp/LTspice.exeLTspice.exe",
        enable_extra_tools=True,
        timeout=10,
    )
    assert cfg.ltspice_path.endswith("/tmp/LTspice.exe")


def test_convert_settings_are_optional_and_have_defaults():
    cfg = ServerConfig()

    assert isinstance(cfg.convert_settings, ConvertSettings)
    assert cfg.convert_settings.ltspice_windows_path == "C:\\users\\brosnan\\AppData\\Local\\LTspice\\"
    assert cfg.convert_settings.ltspice_wine_path == "~/.wine/drive_c/users/brosnan/AppData/Local/LTspice/"
    assert cfg.convert_settings.custom_search_paths == ["./valid_asy/"]
    assert cfg.convert_settings.minimum_dist == 32
    assert cfg.convert_settings.wire_pin_out_dist == 16
    assert cfg.convert_settings.grid_size == 16
    assert cfg.convert_settings.autoplace_iter == 12
    assert cfg.convert_settings.ltspice_version == 4.1


def test_convert_settings_can_be_partially_overridden():
    cfg = ServerConfig.model_validate({"convert_settings": {"grid_size": 24}})

    assert cfg.convert_settings.grid_size == 24
    assert cfg.convert_settings.minimum_dist == 32
    assert cfg.convert_settings.autoplace_iter == 12


def test_convert_settings_reject_invalid_values():
    with pytest.raises(ValueError):
        ServerConfig.model_validate({"convert_settings": {"minimum_dist": -1}})

    with pytest.raises(ValueError):
        ServerConfig.model_validate({"convert_settings": {"unknown": 1}})


def test_checked_in_config_loads_with_convert_settings():
    cfg = load_config(Path(__file__).parents[2] / "config.json")

    assert cfg.convert_settings.grid_size == 16
