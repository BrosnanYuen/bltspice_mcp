from pathlib import Path
from unittest.mock import Mock

import pytest

from bltspice_mcp.app import run_server
from bltspice_mcp.config import ServerConfig


def _config(tmp_path: Path, url: str) -> ServerConfig:
    return ServerConfig(
        mcp_server_name="x",
        mcp_server_url=url,
        wine_path=str(tmp_path / "wine"),
        ltspice_path=str(tmp_path / "ltspice.exe"),
        enable_extra_tools=True,
        timeout=10,
    )


def test_run_server_stdio_transport(tmp_path: Path):
    cfg = _config(tmp_path, "stdio://")
    mcp = Mock()

    run_server(mcp, cfg)

    mcp.run.assert_called_once_with(transport="stdio")


@pytest.mark.parametrize(
    "url,host,port",
    [
        ("http://localhost:7543/mcp", "localhost", 7543),
        ("https://127.0.0.1:8443/mcp", "127.0.0.1", 8443),
        ("http://localhost", "localhost", 7543),
        ("https://localhost", "localhost", 7543),
    ],
)
def test_run_server_http_https_forces_root_path(url: str, host: str, port: int, tmp_path: Path):
    cfg = _config(tmp_path, url)
    mcp = Mock()

    run_server(mcp, cfg)

    mcp.run.assert_called_once_with(
        transport="streamable-http",
        host=host,
        port=port,
        path="/",
    )
