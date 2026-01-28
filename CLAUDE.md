# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 🛠 Common Commands

This project uses `uv` for dependency and environment management.

### Development & Execution
- **Run CLI**: `uv run jmai [args]` or `uv run jmcomic-ai [args]`
- **Start MCP Server (SSE)**: `uv run jmai mcp` (Port 8000 by default)
- **Start MCP Server (stdio)**: `uv run jmai mcp stdio`
- **Start MCP with Hot Reload**: `uv run jmai mcp --reload`
- **Install AI Skills**: `uv run jmai skills install` (Exports to `~/.claude/skills/jmcomic`)
- **Manage Options**: `uv run jmai option show|path|edit`

### Build & Quality Control
- **Build Package**: `uv build`
- **Linting**: `uv run ruff check src/`
- **Type Checking**: `uv run mypy src/`
- **Run All Tests**: `uv run python -m unittest discover tests`
- **Run Integration Test**: `uv run python tests/test_mcp_integration.py`

## 🏗 High-Level Architecture

JMComic AI is an intermediary layer that exposes the `jmcomic` crawler's capabilities to AI agents via the Model Context Protocol (MCP).

### Core Components
- **Transport Layer (`src/jmcomic_ai/mcp/`)**: Built using `FastMCP`. Handles communication between AI clients (Cursor, Claude, etc.) and the server via SSE/HTTP or stdio.
- **Service Layer (`src/jmcomic_ai/cli.py` & others)**: Connects MCP tools to the underlying crawler logic and manages the CLI application.
- **Knowledge Layer (`src/jmcomic_ai/skills/`)**: Contains `SKILL.md` and related logic to inject domain-specific expertise into AI agents.
- **Configuration System**: Manages `option.yml` which controls proxies, download paths, threading, and crawler behavior.

### Critical Reference
- **`reference/`**: This directory contains a local copy of the upstream `jmcomic` source code. Because the upstream library is complex and frequently updated, developers should consult this directory to understand the implementation of core entities (like `JmAlbumDetail`) before modifying MCP tools.

## 📝 Coding Guidelines
- **Type Safety**: Use static type hints and verify with `mypy`.
- **Linting**: Follow the rules defined in `pyproject.toml` (120 character line length).
- **Tool Definitions**: When adding or modifying MCP tools in `src/jmcomic_ai/mcp/`, ensure clear docstrings as they are directly consumed by AI agents.
- **Environment**: Prefer `uv run` for executing commands to ensure consistent environment usage.
