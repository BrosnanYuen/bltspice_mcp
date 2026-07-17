from __future__ import annotations

import argparse
from pathlib import Path

from .app import create_mcp_server, run_server
from .config import ServerConfig, load_config, write_default_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LTspice MCP server using PyLTSpice")
    parser.add_argument("--config", type=Path, default=Path("config.json"), help="Path to config.json")
    parser.add_argument(
        "--write-default-config",
        action="store_true",
        help="Write default config.json and exit",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.write_default_config:
        write_default_config(args.config)
        return

    if not args.config.exists():
        raise SystemExit(f"Config file not found: {args.config}")

    config: ServerConfig = load_config(args.config)
    server = create_mcp_server(config=config, project_root=Path.cwd())
    run_server(server, config)


if __name__ == "__main__":
    main()
