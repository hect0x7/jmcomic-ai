import json
import locale
import os
from enum import Enum
from pathlib import Path

import typer

from jmcomic_ai import __version__
from jmcomic_ai.core import JmcomicService, resolve_option_path


def version_callback(value: bool):
    """
    Callback function to display version and exit.

    Args:
        value: If True, displays version and exits the program.
    """
    if value:
        typer.echo(f"jmai version: {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="jmcomic-ai",
    help="JMComic AI Agent Interface",
    add_completion=True,
    no_args_is_help=True,
)


@app.callback()
def main(
        version: bool | None = typer.Option(
            None,
            "--version",
            "-v",
            help="Show the version and exit.",
            callback=version_callback,
            is_eager=True,
        ),
):
    """
    JMComic AI Agent Interface
    """
    pass


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
        reload: bool = typer.Option(False, "--reload", help="Auto-reload server on file changes"),
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

    transport_value: str = transport.value

    if reload:
        from jmcomic_ai.mcp.reloader import run_with_reloader

        src_path = Path(__file__).parent.parent
        run_with_reloader(src_path)
    else:
        # Initialize service only when actually running the server (not the monitor process)
        service = JmcomicService(str(option) if option else None)
        if transport != TransportType.stdio:
            typer.echo(f"Starting MCP Server ({transport_value}) using option: {service.option_path}", err=True)

            typer.echo(
                "\n💡 Copy and paste the following configuration into your MCP client config (Cursor, Windsurf, "
                "Claude Desktop, etc.)",
                err=True,
            )

        if transport == TransportType.sse:
            config = {"mcpServers": {"jmcomic-ai": {"url": f"http://{host}:{port}/sse"}}}
            typer.echo("\n--- MCP Client Config (SSE Mode) ---", err=True)
            typer.echo(json.dumps(config, indent=2), err=True)
            typer.echo("----------------------------------------------\n", err=True)

        elif transport == TransportType.http:
            config = {"mcpServers": {"jmcomic-ai": {"url": f"http://{host}:{port}/mcp"}}}
            typer.echo("\n--- MCP Client Config (HTTP Streaming Mode) ---", err=True)
            typer.echo(json.dumps(config, indent=2), err=True)
            typer.echo("---------------------------------------------\n", err=True)

        run_server(transport_value, service, host=host, port=port)


skills_app = typer.Typer(name="skills", help="Manage generic skills resources", no_args_is_help=True)
app.add_typer(skills_app, name="skills")


def _resolve_skill_language(language: str | None = None) -> str:
    """Resolve zh/en from an explicit option, environment, or system locale."""
    is_explicit = language is not None
    locale_value = language or (
        os.environ.get("JMAI_LANG")
        or os.environ.get("LC_ALL")
        or os.environ.get("LC_MESSAGES")
        or os.environ.get("LANG")
        or locale.getlocale()[0]
        or "en"
    )
    normalized = locale_value.lower().replace("-", "_")
    if normalized.startswith("zh"):
        return "zh"
    if normalized.startswith(("en", "c.")) or normalized in {"c", "posix"}:
        return "en"
    if is_explicit:
        raise typer.BadParameter("Supported languages: zh, en", param_hint="--lang")
    return "en"


def _skill_text(language: str, english: str, chinese: str) -> str:
    return chinese if language == "zh" else english


@skills_app.callback(invoke_without_command=True)
def skills_shortcuts(
        ctx: typer.Context,
        install_shortcut: bool = typer.Option(False, "--install", "-i", help="Interactive skill installation"),
        uninstall_shortcut: bool = typer.Option(False, "--uninstall", "-u", help="Interactive skill uninstallation"),
        language: str | None = typer.Option(None, "--lang", help="Interface language: zh or en", envvar="JMAI_LANG"),
):
    """Use -i/-u as shortcuts for the install/uninstall subcommands."""
    if ctx.invoked_subcommand is not None:
        return
    if install_shortcut and uninstall_shortcut:
        raise typer.BadParameter("Choose either --install/-i or --uninstall/-u, not both")
    if install_shortcut:
        install_skills(target_dir=None, platform=None, force=False, yes=False, language=language)
    elif uninstall_shortcut:
        uninstall_skills(target_dir=None, platform=None, yes=False, language=language)


def _prompt_skill_platform(action: str, language: str) -> str:
    """Prompt for a supported Agent Skills platform."""
    choices = {
        "1": "claude",
        "2": "codex",
        "3": "gemini",
        "4": "all",
        "claude": "claude",
        "codex": "codex",
        "gemini": "gemini",
        "all": "all",
    }
    action_text = _skill_text(language, action, "安装" if action == "install" else "卸载")
    heading = _skill_text(
        language,
        f"Select platforms to {action_text} the jmcomic skill:",
        f"请选择要{action_text} jmcomic Skill 的平台：",
    )
    typer.secho(f"\n{heading}", fg=typer.colors.BRIGHT_CYAN, bold=True)
    typer.echo("  1. Claude")
    typer.echo("  2. Codex")
    typer.echo("  3. Gemini CLI")
    typer.echo(f"  4. {_skill_text(language, 'All platforms', '全部平台')}")

    while True:
        selection = typer.prompt(_skill_text(language, "Platform", "平台"), default="4").strip().lower()
        if selection in choices:
            return choices[selection]
        typer.secho(
            _skill_text(
                language,
                "Invalid selection. Enter 1-4 or claude/codex/gemini/all.",
                "选择无效，请输入 1-4 或 claude/codex/gemini/all。",
            ),
            fg=typer.colors.RED,
        )


@skills_app.command("install")
def install_skills(
        target_dir: Path | None = typer.Argument(
            None, help="Custom parent directory to install the jmcomic skill into"
        ),
        platform: str | None = typer.Option(
            None, "--platform", "-p", help="Target platform: claude, codex, gemini, or all"
        ),
        force: bool = typer.Option(False, "--force", "-f", help="Force overwrite existing files"),
        yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
        language: str | None = typer.Option(None, "--lang", help="Interface language: zh or en", envvar="JMAI_LANG"),
):
    """
    Install built-in skill definitions (SKILL.md, etc.) to a directory.
    """
    from jmcomic_ai.skills.manager import SkillManager

    language = _resolve_skill_language(language)
    manager = SkillManager()

    if target_dir is not None:
        target_dirs = {"custom": target_dir.resolve()}
        typer.echo(
            _skill_text(
                language,
                f"[*] Target parent directory: {target_dirs['custom']}",
                f"[*] 目标父目录：{target_dirs['custom']}",
            )
        )
    else:
        selected_platform = platform or ("claude" if yes else _prompt_skill_platform("install", language))
        try:
            target_dirs = manager.get_platform_target_dirs(selected_platform)
        except ValueError as error:
            raise typer.BadParameter(str(error), param_hint="--platform") from error
        typer.secho(
            _skill_text(
                language,
                f"[*] Installing for platform selection: {selected_platform}",
                f"[*] 正在为所选平台准备安装：{selected_platform}",
            ),
            fg=typer.colors.CYAN,
        )
        typer.secho(
            _skill_text(
                language,
                "[*] Hint: Pass a custom PATH to override platform directories",
                "[*] 提示：传入自定义 PATH 可覆盖平台默认目录",
            ),
            fg=typer.colors.CYAN,
        )

    # 1. Preview
    typer.secho(
        f"\n{_skill_text(language, '[ Installation Structure Preview ]', '[ 安装结构预览 ]')}",
        fg=typer.colors.BRIGHT_MAGENTA,
        bold=True,
    )
    for platform_name, platform_target_dir in target_dirs.items():
        preview = manager.get_install_preview(platform_target_dir)
        typer.echo(
            _skill_text(
                language,
                f"[{platform_name}] Target Directory: {preview['skill_target_dir']}",
                f"[{platform_name}] 目标目录：{preview['skill_target_dir']}",
            )
        )
        typer.echo(_skill_text(language, "File Tree:", "文件列表："))
        for file_path in preview["files"]:
            typer.echo(f"  - {file_path}")
    typer.echo("")

    # 2. Confirmation (unless -y is passed)
    if not yes:
        if not typer.confirm(_skill_text(language, "Proceed with installation?", "确认安装？"), default=True):
            typer.echo(_skill_text(language, "Installation cancelled.", "已取消安装。"))
            return

    installed_platforms = []
    for platform_name, platform_target_dir in target_dirs.items():
        platform_target_dir.mkdir(parents=True, exist_ok=True)

        if force:
            manager.install(platform_target_dir, overwrite=True)
        elif manager.has_conflicts(platform_target_dir):
            typer.echo(
                _skill_text(
                    language,
                    f"Warning: Some skill files already exist for {platform_name}.",
                    f"警告：{platform_name} 已存在部分 Skill 文件。",
                )
            )
            if yes or typer.confirm(
                _skill_text(
                    language,
                    f"Overwrite existing files for {platform_name}?",
                    f"是否覆盖 {platform_name} 的现有文件？",
                )
            ):
                manager.install(platform_target_dir, overwrite=True)
            else:
                typer.echo(_skill_text(language, "Skipping existing files.", "已跳过现有文件。"))
                manager.install(platform_target_dir, overwrite=False)
        else:
            manager.install(platform_target_dir)
        installed_platforms.append(platform_name)

    platforms_text = ", ".join(installed_platforms)
    typer.echo(
        _skill_text(
            language,
            f"Skills installed successfully for: {platforms_text}",
            f"Skill 安装成功，平台：{platforms_text}",
        )
    )


@skills_app.command("uninstall")
def uninstall_skills(
        target_dir: Path | None = typer.Argument(
            None, help="Custom parent directory to uninstall the jmcomic skill from"
        ),
        platform: str | None = typer.Option(
            None, "--platform", "-p", help="Target platform: claude, codex, gemini, or all"
        ),
        yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
        language: str | None = typer.Option(None, "--lang", help="Interface language: zh or en", envvar="JMAI_LANG"),
):
    """
    Uninstall skills from the directory.
    """
    from jmcomic_ai.skills.manager import SkillManager

    language = _resolve_skill_language(language)
    manager = SkillManager()

    if target_dir is not None:
        target_dirs = {"custom": target_dir.resolve()}
        typer.echo(
            _skill_text(
                language,
                f"[*] Uninstalling from: {target_dirs['custom']}",
                f"[*] 卸载目标：{target_dirs['custom']}",
            )
        )
    else:
        selected_platform = platform or ("claude" if yes else _prompt_skill_platform("uninstall", language))
        try:
            target_dirs = manager.get_platform_target_dirs(selected_platform)
        except ValueError as error:
            raise typer.BadParameter(str(error), param_hint="--platform") from error
        typer.secho(
            _skill_text(
                language,
                f"[*] Uninstalling for platform selection: {selected_platform}",
                f"[*] 正在为所选平台准备卸载：{selected_platform}",
            ),
            fg=typer.colors.YELLOW,
        )

    # 1. Preview
    previews = {
        platform_name: manager.get_uninstall_preview(platform_target_dir)
        for platform_name, platform_target_dir in target_dirs.items()
    }
    symlink_previews = {name: preview for name, preview in previews.items() if preview["is_symlink"]}
    for preview in symlink_previews.values():
        typer.secho(
            _skill_text(
                language,
                f"[*] Skipped externally managed skill symlink: {preview['skill_target_dir']} "
                f"-> {preview['link_target']}. Nothing was changed; remove the link manually if intended.",
                f"[*] 已跳过外部管理的 Skill 软链接：{preview['skill_target_dir']} -> {preview['link_target']}。"
                "未做任何修改；如需删除，请手动处理。",
            ),
            fg=typer.colors.YELLOW,
        )

    existing_previews = {
        name: preview for name, preview in previews.items() if preview["exists"] and not preview["is_symlink"]
    }
    if not existing_previews:
        typer.secho(
            _skill_text(
                language,
                "[*] Skipped: No removable jmcomic skill directory found for the selected targets",
                "[*] 已跳过：所选目标中没有可卸载的 jmcomic Skill 目录",
            ),
            fg=typer.colors.YELLOW,
        )
        return

    typer.secho(
        f"\n{_skill_text(language, '[ Uninstallation Preview ]', '[ 卸载预览 ]')}",
        fg=typer.colors.BRIGHT_RED,
        bold=True,
    )
    typer.secho(
        _skill_text(language, "THE FOLLOWING DIRECTORY AND FILES WILL BE DELETED:", "以下目录和文件将被删除："),
        fg=typer.colors.RED,
    )
    for platform_name, preview in existing_previews.items():
        typer.echo(
            _skill_text(
                language,
                f"[{platform_name}] Path: {preview['skill_target_dir']}",
                f"[{platform_name}] 路径：{preview['skill_target_dir']}",
            )
        )
        typer.echo(_skill_text(language, "File Tree:", "文件列表："))
        for file_path in preview["files"]:
            typer.echo(f"  - {file_path}")

    typer.echo(
        "\n"
        + _skill_text(
            language,
            "Only the specific skill folder (jmcomic) will be removed. Your other skills remain safe.",
            "只会删除 jmcomic Skill 目录，其他 Skill 不受影响。",
        )
    )
    typer.echo("")

    # 2. Confirmation
    if yes or typer.confirm(
        _skill_text(
            language,
            "Are you sure you want to PERMANENTLY DELETE the 'jmcomic' skill folder?",
            "确认永久删除 jmcomic Skill 目录？",
        ),
        default=False,
    ):
        uninstalled_platforms = []
        for platform_name, preview in existing_previews.items():
            if manager.uninstall(preview["target_dir"]):
                uninstalled_platforms.append(platform_name)
        platforms_text = ", ".join(uninstalled_platforms)
        typer.echo(
            _skill_text(
                language,
                f"Skills uninstalled successfully for: {platforms_text}",
                f"Skill 卸载成功，平台：{platforms_text}",
            )
        )


# Option group
option_app = typer.Typer(name="option", help="Manage jmcomic option (configuration)", no_args_is_help=True)
app.add_typer(option_app, name="option")


@option_app.command("show")
def option_show():
    """Show current option file path and content"""
    resolved_path = resolve_option_path()
    typer.echo(f"Option file: {resolved_path}")
    typer.echo("---")
    if resolved_path.exists():
        typer.echo(resolved_path.read_text(encoding="utf-8"))
    else:
        typer.echo("Option file does not exist yet.")


@option_app.command("path")
def option_path():
    """Print option file path"""
    resolved_path = resolve_option_path()
    typer.echo(resolved_path)


@option_app.command("edit")
def option_edit():
    """Open option file in default editor"""
    import platform
    import subprocess

    resolved_path = resolve_option_path()
    path = str(resolved_path)

    if not resolved_path.exists():
        typer.echo(f"Option file does not exist: {path}")
        typer.echo("It will be created when you first use the service (e.g. jmai mcp).")
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
