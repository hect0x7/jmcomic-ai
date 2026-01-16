import os
import sys
import subprocess
import time
from pathlib import Path
from typing import Callable
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

class RestartHandler(FileSystemEventHandler):
    def __init__(self, restart_callback: Callable[[], None]) -> None:
        self.restart_callback = restart_callback
        self.last_restart: float = 0

    def on_modified(self, event: FileSystemEvent) -> None:
        if event.src_path.endswith(".py"):
            now = time.time()
            if now - self.last_restart > 1:  # 节流: 1秒内只重启一次
                print(f"\n[*] Detected change in {event.src_path}, restarting server...", file=sys.stderr)
                self.restart_callback()
                self.last_restart = now

def run_with_reloader(watch_path: Path) -> None:
    """
    运行带有热重载功能的服务器。
    由于 FastMCP 运行在 asyncio 中且通常会阻塞主线程,
    最简单的 reload 实现是主进程作为监控, 子进程运行服务器。
    """
    process = None

    def start_process() -> None:
        nonlocal process
        if process:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        
        # 构造重启动命令: 剔除 --reload 后的当前命令
        args = [sys.executable, "-m", "jmcomic_ai.cli"]
        # 获取除了 --reload 之外的所有参数
        original_args = sys.argv[1:]
        filtered_args = [arg for arg in original_args if arg != "--reload"]
        
        # 确保不再次进入 reload 逻辑
        cmd = args + filtered_args
        process = subprocess.Popen(cmd)

    # 初始启动
    start_process()

    event_handler = RestartHandler(start_process)
    observer = Observer()
    observer.schedule(event_handler, str(watch_path), recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
            if process and process.poll() is not None:
                # 如果子进程意外退出（非代码变更引起），我们也尝试重启
                print("[!] Server process exited. Restarting in 2 seconds...", file=sys.stderr)
                time.sleep(2)
                start_process()
    except KeyboardInterrupt:
        observer.stop()
        if process:
            process.terminate()
    observer.join()
