import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, Tuple

import webview


def is_port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _find_free_port(preferred_port: int) -> int:
    """Use the preferred port if it is free; otherwise pick an available local port."""
    if not is_port_open(preferred_port):
        return preferred_port

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def start_streamlit() -> Tuple[subprocess.Popen, int, Path]:
    python_exe = sys.executable
    app_py = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")
    host = os.environ.get("DB_BUDDY_HOST", "127.0.0.1")
    preferred_port = int(os.environ.get("DB_BUDDY_PORT", "8501"))
    port = _find_free_port(preferred_port)
    log_path = Path(os.path.dirname(os.path.abspath(__file__))) / "streamlit-startup.log"

    with open(log_path, "w", encoding="utf-8") as log_file:
        proc = subprocess.Popen(
            [
                python_exe,
                "-m",
                "streamlit",
                "run",
                app_py,
                "--server.headless",
                "true",
                "--server.address",
                host,
                "--server.port",
                str(port),
            ],
            stdout=log_file,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )

    return proc, port, log_path


def _show_error(message: str, details: Optional[str] = None) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        if details:
            messagebox.showerror("DB-Buddy Desktop", f"{message}\n\n{details}")
        else:
            messagebox.showerror("DB-Buddy Desktop", message)
        root.destroy()
    except Exception:
        print(message)
        if details:
            print(details)


if __name__ == "__main__":
    proc, port, log_path = start_streamlit()

    # Wait until the server is ready, but stop early if it crashes.
    for _ in range(60):
        if proc.poll() is not None:
            break
        if is_port_open(port):
            break
        time.sleep(0.5)

    if proc.poll() is not None and not is_port_open(port):
        log_text = ""
        try:
            log_text = log_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            log_text = f"Log file: {log_path}"

        _show_error(
            "DB-Buddy server could not start.",
            "The app stopped before the local page became ready.\n\n"
            f"Startup log:\n{log_text[-4000:]}",
        )
        sys.exit(1)

    try:
        webview.create_window(
            "DB-Buddy Desktop",
            f"http://127.0.0.1:{port}",
            width=1400,
            height=900,
        )
        webview.start()
    finally:
        proc.terminate()
        proc.wait()
