from __future__ import annotations

import base64
import json
import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path

PACKAGE_NAME = "jmcomic-ai"


class UpdateError(RuntimeError):
    """Raised when a safe self-update strategy cannot be determined."""


@dataclass(frozen=True)
class UpdateStrategy:
    name: str
    command: tuple[str, ...]
    display_command: tuple[str, ...]


@dataclass(frozen=True)
class UpdateResult:
    return_code: int
    scheduled: bool = False


def get_installation_source() -> str:
    """Return registry, editable, vcs, direct-url, or missing for the installed package."""
    try:
        package_distribution = distribution(PACKAGE_NAME)
    except PackageNotFoundError:
        return "missing"

    direct_url = package_distribution.read_text("direct_url.json")
    if not direct_url:
        return "registry"

    try:
        metadata = json.loads(direct_url)
    except json.JSONDecodeError as error:
        raise UpdateError("Installed package source metadata is invalid") from error

    if metadata.get("dir_info", {}).get("editable") is True:
        return "editable"
    if metadata.get("vcs_info"):
        return "vcs"
    return "direct-url"


def get_installer() -> str | None:
    try:
        package_distribution = distribution(PACKAGE_NAME)
    except PackageNotFoundError:
        return None
    installer = package_distribution.read_text("INSTALLER")
    return installer.strip().lower() if installer and installer.strip() else None


def _get_uv_tool_dir(uv_executable: str) -> Path | None:
    result = subprocess.run(
        [uv_executable, "tool", "dir"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return Path(result.stdout.strip()).expanduser().resolve()


def _is_within(path: Path, parent: Path) -> bool:
    return path == parent or parent in path.parents


def _pip_available() -> bool:
    result = subprocess.run(
        [sys.executable, "-m", "pip", "--version"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def detect_update_strategy() -> UpdateStrategy:
    """Select a safe updater for the current installation."""
    installation_source = get_installation_source()
    if installation_source == "editable":
        raise UpdateError("Editable installation detected. Update the source checkout, then run `uv sync`.")
    if installation_source == "missing":
        raise UpdateError("Cannot find installed package metadata for jmcomic-ai")

    installer = get_installer()
    uv_executable = shutil.which("uv")
    if installer == "uv":
        if uv_executable is None:
            raise UpdateError("The package was installed by uv, but the uv executable is unavailable")
        uv_tool_dir = _get_uv_tool_dir(uv_executable)
        if uv_tool_dir is None:
            raise UpdateError("Cannot determine whether the current uv installation is a tool environment")
        if _is_within(Path(sys.prefix).resolve(), uv_tool_dir.resolve()):
            if installation_source == "direct-url":
                raise UpdateError("Local or archive uv tool installation detected. Reinstall from the same source to update safely.")
            return UpdateStrategy(
                name="uv tool",
                command=(uv_executable, "tool", "upgrade", PACKAGE_NAME, "--no-config"),
                display_command=("uv", "tool", "upgrade", PACKAGE_NAME, "--no-config"),
            )

        if installation_source in {"direct-url", "vcs"}:
            raise UpdateError("Direct URL installation detected. Reinstall from the same source URL to update safely.")
        return UpdateStrategy(
            name="uv pip",
            command=(
                uv_executable,
                "pip",
                "install",
                "--python",
                sys.executable,
                "--upgrade",
                PACKAGE_NAME,
                "--no-config",
            ),
            display_command=(
                "uv",
                "pip",
                "install",
                "--python",
                "python",
                "--upgrade",
                PACKAGE_NAME,
                "--no-config",
            ),
        )

    if installation_source in {"direct-url", "vcs"}:
        raise UpdateError("Direct URL installation detected. Reinstall from the same source URL to update safely.")

    if installer == "pip":
        if not _pip_available():
            raise UpdateError("The package was installed by pip, but pip is unavailable in the current Python environment")
        return UpdateStrategy(
            name="pip",
            command=(sys.executable, "-m", "pip", "install", "--upgrade", PACKAGE_NAME),
            display_command=("python", "-m", "pip", "install", "--upgrade", PACKAGE_NAME),
        )

    raise UpdateError(f"Unsupported or unknown package installer: {installer or 'unknown'}")


def format_update_command(strategy: UpdateStrategy) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(strategy.display_command)
    return shlex.join(strategy.display_command)


def _is_windows() -> bool:
    return os.name == "nt"


def _powershell_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _schedule_windows_update(strategy: UpdateStrategy) -> None:
    powershell = shutil.which("powershell.exe") or shutil.which("pwsh")
    if powershell is None:
        raise UpdateError("PowerShell is required to update a running jmai command on Windows")

    log_dir = Path.home() / ".jmcomic-ai"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "update.log"
    executable, *arguments = strategy.command
    argument_text = " ".join(_powershell_quote(argument) for argument in arguments)
    script = "\n".join(
        (
            f"Wait-Process -Id {os.getpid()} -ErrorAction SilentlyContinue",
            f"& {_powershell_quote(executable)} {argument_text} *> {_powershell_quote(str(log_path))}",
            "exit $LASTEXITCODE",
        )
    )
    encoded_script = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    creation_flags = (
        getattr(subprocess, "CREATE_NO_WINDOW", 0)
        | getattr(subprocess, "DETACHED_PROCESS", 0)
        | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    )
    subprocess.Popen(
        [powershell, "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded_script],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creation_flags,
    )


def run_update(strategy: UpdateStrategy) -> UpdateResult:
    """Run the selected update command or schedule it after exit on Windows."""
    if _is_windows():
        _schedule_windows_update(strategy)
        return UpdateResult(return_code=0, scheduled=True)
    return UpdateResult(return_code=subprocess.run(strategy.command, check=False).returncode)
