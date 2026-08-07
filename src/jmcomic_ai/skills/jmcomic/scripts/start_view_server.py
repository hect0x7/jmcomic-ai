"""Start jm-view-server for a local JMComic download directory."""

from __future__ import annotations

import argparse
import shlex
import shutil
import subprocess
from pathlib import Path

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def build_command(executable: str, directory: Path, host: str, port: int, password: str | None) -> list[str]:
    if not 1 <= port <= 65535:
        raise ValueError("Port must be between 1 and 65535")
    if host not in LOCAL_HOSTS and not password:
        raise ValueError("A password is required when exposing the reader beyond this computer")

    command = [executable, str(directory), "--host", host, "--port", str(port), "--no-debug"]
    if password:
        command.extend(["--password", password])
    return command


def redact_command(command: list[str]) -> list[str]:
    redacted = command.copy()
    if "--password" in redacted:
        password_index = redacted.index("--password") + 1
        if password_index < len(redacted):
            redacted[password_index] = "********"
    return redacted


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start jm-view-server for downloaded manga")
    parser.add_argument("directory", help="Downloaded manga directory to serve")
    parser.add_argument("--host", default="127.0.0.1", help="Listen host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8080, help="Listen port (default: 8080)")
    parser.add_argument("--password", help="Reader password; required for LAN exposure")
    parser.add_argument("--dry-run", action="store_true", help="Validate and print the command without starting it")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    directory = Path(args.directory).expanduser().resolve()
    if not directory.is_dir():
        raise SystemExit(f"Download directory does not exist: {directory}")

    executable = shutil.which("jms")
    if executable is None:
        raise SystemExit("jm-view-server is not installed. Install it with: python -m pip install jm-view-server")

    try:
        command = build_command(executable, directory, args.host, args.port, args.password)
    except ValueError as error:
        raise SystemExit(str(error)) from error

    display_host = "127.0.0.1" if args.host == "0.0.0.0" else args.host
    print(f"Reader URL: http://{display_host}:{args.port}", flush=True)
    print(f"Shared directory: {directory}", flush=True)
    if args.dry_run:
        print(f"Command: {shlex.join(redact_command(command))}")
        return

    try:
        raise SystemExit(subprocess.run(command, check=False).returncode)
    except KeyboardInterrupt:
        raise SystemExit(130) from None


if __name__ == "__main__":
    main()
