"""Keep every subprocess in this test suite invisible on a Windows desktop."""

import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def stdio_python() -> str:
    executable = Path(sys.executable)
    hidden = executable.with_name("pythonw.exe")
    return str(hidden) if os.name == "nt" and hidden.is_file() else str(executable)


@contextmanager
def hidden_windows_processes():
    if os.name != "nt":
        yield
        return
    original_init = subprocess.Popen.__init__

    def initialize_hidden(self, *args, **kwargs):
        # Patch the initializer, not the class: asyncio/MCP may use Popen
        # subclasses or retry without flags after a platform-specific failure.
        kwargs["creationflags"] = kwargs.get("creationflags", 0) | NO_WINDOW
        return original_init(self, *args, **kwargs)

    with patch.object(subprocess.Popen, "__init__", initialize_hidden):
        yield
