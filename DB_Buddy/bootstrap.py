import importlib.util
import os
import shutil
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from queue import Empty, Queue
from tkinter import messagebox


BASE_DIR = Path(__file__).resolve().parent
APP_PATH = BASE_DIR / "desktop_app.py"
REQUIREMENTS_PATH = BASE_DIR / "requirements.txt"
MODEL_NAME = os.environ.get("DB_BUDDY_MODEL", "qwen2.5-coder:7b")
LOCAL_PYTHON = BASE_DIR / ".venv" / "Scripts" / "python.exe"


@dataclass(frozen=True)
class PackageSpec:
    display_name: str
    import_name: str


REQUIRED_PACKAGES = [
    PackageSpec("streamlit", "streamlit"),
    PackageSpec("streamlit-mermaid", "streamlit_mermaid"),
    PackageSpec("pywebview", "webview"),
    PackageSpec("pandas", "pandas"),
    PackageSpec("SQLAlchemy", "sqlalchemy"),
    PackageSpec("PyMySQL", "pymysql"),
    PackageSpec("Faker", "faker"),
    PackageSpec("langchain", "langchain"),
    PackageSpec("langchain-community", "langchain_community"),
]


class BootstrapUI:
    def __init__(self) -> None:
        self.queue: Queue[tuple[str, str]] = Queue()
        self.finished = False
        self.root = None
        self.headless = False

        try:
            self.root = tk.Tk()
            self.root.title("DB-Buddy Setup")
            self.root.geometry("620x380")
            self.root.minsize(560, 320)
            self.root.configure(bg="#1f1f1f")
            self.root.protocol("WM_DELETE_WINDOW", self._on_close)

            title = tk.Label(
                self.root,
                text="DB-Buddy Setup",
                font=("Segoe UI", 16, "bold"),
                fg="white",
                bg="#1f1f1f",
            )
            title.pack(anchor="w", padx=18, pady=(16, 6))

            self.status_var = tk.StringVar(value="Checking dependencies...")
            status = tk.Label(
                self.root,
                textvariable=self.status_var,
                font=("Segoe UI", 10),
                fg="#cfcfcf",
                bg="#1f1f1f",
                justify="left",
                wraplength=560,
            )
            status.pack(anchor="w", padx=18, pady=(0, 10))

            self.text = tk.Text(
                self.root,
                height=12,
                bg="#111111",
                fg="#d8d8d8",
                insertbackground="white",
                relief="flat",
                highlightthickness=1,
                highlightbackground="#444444",
                wrap="word",
            )
            self.text.pack(fill="both", expand=True, padx=18, pady=(0, 14))
            self.text.configure(state="disabled")

            self.root.after(100, self._pump_queue)
        except Exception:
            self.headless = True
            self.root = None
            self.status_var = None
            self.text = None
            print("DB-Buddy Setup (console mode)")
            print("Tkinter UI is unavailable, continuing in console mode.")

    def log(self, message: str) -> None:
        self.queue.put(("log", message))

    def status(self, message: str) -> None:
        self.queue.put(("status", message))

    def error(self, message: str) -> None:
        self.queue.put(("error", message))

    def close(self) -> None:
        self.queue.put(("close", ""))

    def _append_text(self, message: str) -> None:
        if self.headless or self.text is None:
            print(message)
            return
        self.text.configure(state="normal")
        self.text.insert("end", message + "\n")
        self.text.see("end")
        self.text.configure(state="disabled")

    def _pump_queue(self) -> None:
        try:
            while True:
                kind, message = self.queue.get_nowait()
                if kind == "log":
                    self._append_text(message)
                elif kind == "status":
                    if self.status_var is not None:
                        self.status_var.set(message)
                    self._append_text(f"[INFO] {message}")
                elif kind == "error":
                    if self.status_var is not None:
                        self.status_var.set(message)
                    self._append_text(f"[ERROR] {message}")
                elif kind == "close":
                    self.finished = True
                    if self.root is not None:
                        self.root.destroy()
                    return
        except Empty:
            pass

        if not self.finished:
            self.root.after(100, self._pump_queue)

    def _on_close(self) -> None:
        self._append_text("Setup was closed before finishing.")
        self.finished = True
        if self.root is not None:
            self.root.destroy()

    def run(self) -> None:
        if self.root is not None:
            self.root.mainloop()
        else:
            while not self.finished:
                try:
                    kind, message = self.queue.get(timeout=0.1)
                except Empty:
                    continue
                if kind == "log":
                    self._append_text(message)
                elif kind == "status":
                    self._append_text(f"[INFO] {message}")
                elif kind == "error":
                    self._append_text(f"[ERROR] {message}")
                elif kind == "close":
                    self.finished = True


def _is_installed(import_name: str) -> bool:
    return importlib.util.find_spec(import_name) is not None


def _check_missing_packages():
    return [pkg for pkg in REQUIRED_PACKAGES if not _is_installed(pkg.import_name)]


def _run_command(command, ui: BootstrapUI, cwd: Path | None = None) -> int:
    ui.log("Running: " + " ".join(command))
    proc = subprocess.Popen(
        command,
        cwd=str(cwd or BASE_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert proc.stdout is not None
    for line in proc.stdout:
        ui.log(line.rstrip())

    return proc.wait()


def _ensure_python_packages(ui: BootstrapUI) -> bool:
    missing = _check_missing_packages()
    if not missing:
        ui.status("Python packages are already installed.")
        ui.log("All required Python packages are present.")
        return True

    ui.status("Installing missing Python packages...")
    ui.log("Missing packages: " + ", ".join(pkg.display_name for pkg in missing))

    commands = [
        [sys.executable, "-m", "pip", "install", "--upgrade", "pip"],
        [sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS_PATH)],
    ]

    for command in commands:
        code = _run_command(command, ui)
        if code != 0:
            ui.error("Python package installation failed.")
            return False

    ui.log("Python package installation finished.")
    return True


def _ollama_models() -> set[str]:
    result = subprocess.run(
        ["ollama", "list"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        return set()

    models = set()
    for line in result.stdout.splitlines()[1:]:
        parts = line.split()
        if parts:
            models.add(parts[0])
    return models


def _ollama_path() -> str | None:
    candidate = shutil.which("ollama")
    if candidate:
        return candidate

    local_paths = [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama.exe"),
        r"C:\Program Files\Ollama\ollama.exe",
        r"C:\Program Files (x86)\Ollama\ollama.exe",
    ]
    for path in local_paths:
        if path and os.path.exists(path):
            return path
    return None


def _ask_yes_no(title: str, message: str) -> bool:
    try:
        return messagebox.askyesno(title, message)
    except Exception:
        return False


def _ensure_ollama_model(ui: BootstrapUI) -> bool:
    ollama_exe = _ollama_path()
    if ollama_exe is None:
        ui.status("Ollama was not found.")
        ui.log("AI features need Ollama, but the executable is not installed or not on PATH.")
        if _ask_yes_no(
            "Ollama missing",
            "Ollama was not found on this PC.\n"
            "The app can still open, but ERD/AI features will be disabled.\n\n"
            "Open the Ollama download page now?",
        ):
            webbrowser.open("https://ollama.com/download")
        return True

    if MODEL_NAME in _ollama_models():
        ui.log(f"Ollama model '{MODEL_NAME}' is available.")
        return True

    ui.status(f"Pulling Ollama model '{MODEL_NAME}'...")
    code = _run_command([ollama_exe, "pull", MODEL_NAME], ui)
    if code != 0:
        ui.error(f"Failed to download Ollama model '{MODEL_NAME}'.")
        return False

    ui.log(f"Ollama model '{MODEL_NAME}' download complete.")
    return True


def _launch_app(ui: BootstrapUI) -> None:
    ui.status("Starting DB-Buddy...")
    command = [sys.executable, str(APP_PATH)]
    ui.log("Launching the desktop app automatically.")
    env = os.environ.copy()
    env["DB_BUDDY_OLLAMA_AVAILABLE"] = "1" if _ollama_path() is not None else "0"
    proc = subprocess.Popen(command, cwd=str(BASE_DIR), env=env)
    ui.log(f"desktop_app.py started (PID {proc.pid})")
    ui.close()


def _worker(ui: BootstrapUI) -> None:
    try:
        if not _ensure_python_packages(ui):
            return

        if not _ensure_ollama_model(ui):
            return

        _launch_app(ui)
    except Exception as exc:
        ui.error(f"Setup failed: {exc}")


def main() -> None:
    if LOCAL_PYTHON.exists() and Path(sys.executable).resolve() != LOCAL_PYTHON.resolve():
        os.execv(str(LOCAL_PYTHON), [str(LOCAL_PYTHON), str(Path(__file__).resolve())])

    ui = BootstrapUI()
    thread = threading.Thread(target=_worker, args=(ui,), daemon=True)
    thread.start()
    ui.run()


if __name__ == "__main__":
    main()
