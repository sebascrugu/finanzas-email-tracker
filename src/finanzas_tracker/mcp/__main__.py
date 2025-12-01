#!/usr/bin/env python3
"""
Script para ejecutar el servidor MCP de Finanzas Tracker.

Este script inicia el servidor MCP que permite a Claude Desktop
interactuar con tus datos financieros.

Uso:
    poetry run python -m finanzas_tracker.mcp

    O como script:
    poetry run mcp-server
"""

import asyncio

from finanzas_tracker.mcp.server import run_server


def main() -> None:
    """Entry point para el servidor MCP."""
    asyncio.run(run_server())


if __name__ == "__main__":
    main()
