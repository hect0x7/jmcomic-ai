from enum import Enum
from pathlib import Path

import typer

from jmcomic_ai.core import JmcomicService

app = typer.Typer(
    name="jmcomic-ai",
    help="JMComic AI Agent Interface",
    add_completion=True,
    no_args_is_help=True,
)


class TransportType(str, Enum):
    stdio = "stdio"  # Standard I/O (for local subprocess mode)
    sse = "sse"  # Server-Sent Events (recommended for Claude Desktop)
    http = "http"  # streamable_http


@app.command()
def mcp(
    transport: TransportType = typer.Argument(
        TransportType.sse, help="Transport mode: 'sse' (default), 'stdio', or 'http'"
    ),
    option: Path | None = typer.Option(None, "--option", help="Path to jmcomic option file"),
    port: int = typer.Option(8000, help="Port for server (ignored for stdio)"),
    host: str = typer.Option("127.0.0.1", help="Host for server (ignored for stdio)"),
):
    """
    Start the MCP Server.

    Transport modes:
    - sse: Server-Sent Events (default, recommended for Claude Desktop)
    - stdio: Standard Input/Output (for local subprocess mode)
    - http: Streamable HTTP (for production deployments, horizontal scaling)

    Note: SSE transport is deprecated in MCP spec, but still supported by Claude Desktop.
    Consider using 'http' (Streamable HTTP) for new deployments.
    """
    # Defer import to avoid circular dependency or early loading
    from jmcomic_ai.mcp.server import run_server

    # Initialize service to check/ensure option availability
    # We pass str(option) because JmcomicService expects str or None
    service = JmcomicService(str(option) if option else None)

    transport_value: str = transport.value
    typer.echo(f"Starting MCP Server ({transport_value}) using option: {service.option_path}", err=True)

    # Print configuration hint
    import json

    typer.echo("\n💡 以下配置可直接复制到您的 MCP 客户端配置文件中 (Cursor/Windsurf/Claude Desktop 等)", err=True)

    if transport == TransportType.stdio:
        config = {"mcpServers": {"jmcomic-ai": {"command": "jmai", "args": ["mcp", "stdio"]}}}
        typer.echo("\n--- MCP Client Config (stdio 标准输入输出模式) ---", err=True)
        typer.echo(json.dumps(config, indent=2), err=True)
        typer.echo("----------------------------------------------------\n", err=True)

    elif transport == TransportType.sse:
        config = {"mcpServers": {"jmcomic-ai": {"url": f"http://{host}:{port}/sse"}}}
        typer.echo("\n--- MCP Client Config (SSE 服务器推送模式) ---", err=True)
        typer.echo(json.dumps(config, indent=2), err=True)
        typer.echo("----------------------------------------------\n", err=True)

    elif transport == TransportType.http:
        config = {"mcpServers": {"jmcomic-ai": {"url": f"http://{host}:{port}/mcp"}}}
        typer.echo("\n--- MCP Client Config (HTTP 流式传输模式) ---", err=True)
        typer.echo(json.dumps(config, indent=2), err=True)
        typer.echo("---------------------------------------------\n", err=True)

    run_server(transport_value, service, host=host, port=port)


skills_app = typer.Typer(name="skills", help="Manage generic skills resources", no_args_is_help=True)
app.add_typer(skills_app, name="skills")


@skills_app.command("install")
def install_skills(
    target_dir: Path | None = typer.Argument(
        None, help="Directory to install skills into. Defaults to ~/.claude/skills/jmcomic"
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Force overwrite existing files"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """
    Install built-in skill definitions (SKILL.md, etc.) to a directory.
    """
    from jmcomic_ai.skills.manager import SkillManager

    manager = SkillManager()

    if target_dir is None:
        # Default to ~/.claude/skills/jmcomic (Standard for Claude Desktop)
        target_dir = Path.home() / ".claude" / "skills" / "jmcomic"

    typer.echo(f"Target directory: {target_dir.resolve()}")

    # 1. Confirmation (unless -y is passed)
    if not yes:
        if not typer.confirm("Proceed with installation?", default=True):
            typer.echo("Installation cancelled.")
            return

    if not target_dir.exists():
        target_dir.mkdir(parents=True, exist_ok=True)

    # 2. Duplicate Check / Conflict Handing
    if force:
        manager.install(target_dir, overwrite=True)
    else:
        if manager.has_conflicts(target_dir):
            typer.echo("Warning: Some skill files already exist in the target directory.")
            if yes or typer.confirm("Overwrite existing files?"):
                manager.install(target_dir, overwrite=True)
            else:
                typer.echo("Skipping existing files.")
                manager.install(target_dir, overwrite=False)
        else:
            manager.install(target_dir)

    typer.echo("Skills installed successfully.")


@skills_app.command("uninstall")
def uninstall_skills(
    target_dir: Path | None = typer.Argument(
        None, help="Directory to uninstall skills from. Defaults to ~/.claude/skills/jmcomic"
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """
    Uninstall skills from the directory.
    """
    from jmcomic_ai.skills.manager import SkillManager

    manager = SkillManager()

    if target_dir is None:
        # Default to ~/.claude/skills/jmcomic
        target_dir = Path.home() / ".claude" / "skills" / "jmcomic"

    if not target_dir.exists():
        typer.echo(f"Target directory {target_dir} does not exist.")
        return

    if yes or typer.confirm(f"Are you sure you want to delete skills from {target_dir}?", default=True):
        manager.uninstall(target_dir)
        typer.echo("Skills uninstalled successfully.")


# Option 命令组
option_app = typer.Typer(name="option", help="Manage jmcomic option (configuration)", no_args_is_help=True)
app.add_typer(option_app, name="option")


@option_app.command("show")
def option_show():
    """Show current option file path and content"""
    service = JmcomicService()
    typer.echo(f"Option file: {service.option_path}")
    typer.echo("---")
    if service.option_path.exists():
        typer.echo(service.option_path.read_text(encoding="utf-8"))
    else:
        typer.echo("Option file does not exist yet.")


@option_app.command("path")
def option_path():
    """Print option file path"""
    service = JmcomicService()
    typer.echo(service.option_path)


@option_app.command("edit")
def option_edit():
    """Open option file in default editor"""
    import platform
    import subprocess

    service = JmcomicService()
    path = str(service.option_path)

    if not service.option_path.exists():
        typer.echo(f"Option file does not exist: {path}")
        typer.echo("It will be created when you first use the service.")
        return

    try:
        if platform.system() == "Windows":
            subprocess.run(["notepad", path])
        elif platform.system() == "Darwin":
            subprocess.run(["open", "-e", path])
        else:
            subprocess.run(["xdg-open", path])
    except Exception as e:
        typer.echo(f"Failed to open editor: {e}")
        typer.echo(f"Please manually edit: {path}")


if __name__ == "__main__":
    app()
