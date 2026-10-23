"""CLI entry point: stdio only; stdout belongs exclusively to MCP."""

import argparse
import asyncio
import logging
from pathlib import Path
import sys

from .client import PlumClient, PlumError
from .config import ConfigError, load_config
from .server import create_server


async def check_connection(config):
    """Perform one authenticated read of the deployed API contract."""
    client = PlumClient(config)
    try:
        await client.call("search_help")
    finally:
        await client.close()


def main():
    """Do not print configuration values, HTTP traces or secrets."""
    parser = argparse.ArgumentParser(
        description="Plum-Virion read-only MCP server (stdio)"
    )
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="Validate config without network access",
    )
    parser.add_argument(
        "--check", action="store_true", help="Check authentication and Discovery API v1"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        config = load_config(args.config)
        if args.check_config:
            print("Configuration valid (no network request).", file=sys.stderr)
        elif args.check:
            asyncio.run(check_connection(config))
            print(
                "Plum authentication and Discovery API v1 available.", file=sys.stderr
            )
        else:
            create_server(PlumClient(config)).run(transport="stdio")
    except (ConfigError, PlumError) as error:
        print(str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
