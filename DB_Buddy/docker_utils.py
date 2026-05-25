import shutil
import socket
import subprocess
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional


BASE_DIR = Path(__file__).resolve().parent
DOCKER_DIR = BASE_DIR / "docker" / "mysql"
COMPOSE_PATH = DOCKER_DIR / "docker-compose.yml"
ENV_PATH = DOCKER_DIR / ".env"
INSTALLER_PATH = BASE_DIR / "downloads" / "Docker Desktop Installer.exe"

DOCKER_DESKTOP_DOWNLOAD_URL = (
    "https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe"
    "?utm_campaign=docs-driven-download-win-amd64&utm_medium=webreferral&utm_source=docker"
)

MYSQL_IMAGE = "mysql:8.0"
MYSQL_CONTAINER_NAME = "db-buddy-mysql"
DEFAULT_DATABASE = "db_buddy"
DEFAULT_USER = "dbbuddy"
DEFAULT_PASSWORD = "dbbuddy123"
DEFAULT_PORT = 3306


@dataclass(frozen=True)
class LocalMySQLInfo:
    host: str
    port: int
    user: str
    password: str
    database: str
    container_name: str = MYSQL_CONTAINER_NAME

    @property
    def sqlalchemy_url(self) -> str:
        from sqlalchemy.engine import URL

        return URL.create(
            "mysql+pymysql",
            username=self.user,
            password=self.password,
            host=self.host,
            port=self.port,
            database=self.database,
            query={"charset": "utf8mb4"},
        ).render_as_string(hide_password=False)


def docker_in_path() -> bool:
    return shutil.which("docker") is not None


def docker_is_ready() -> tuple[bool, str]:
    if not docker_in_path():
        return False, "Docker가 설치되어 있지 않습니다."

    proc = subprocess.run(
        ["docker", "info"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    if proc.returncode == 0:
        return True, "Docker가 준비되었습니다."

    message = (proc.stderr or proc.stdout or "").strip()
    if not message:
        message = "Docker는 설치되어 있지만 아직 실행되지 않았습니다."
    return False, message


def open_docker_download_page() -> None:
    import webbrowser

    webbrowser.open("https://docs.docker.com/desktop/setup/install/windows-install/")


def download_docker_installer(
    destination: Path | None = None,
    progress_callback: Optional[Callable[[int, Optional[int]], None]] = None,
) -> Path:
    target = destination or INSTALLER_PATH
    target.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = target.with_suffix(target.suffix + ".part")
    try:
        with urllib.request.urlopen(DOCKER_DESKTOP_DOWNLOAD_URL) as response:
            total = response.headers.get("Content-Length")
            total_size = int(total) if total and total.isdigit() else None
            downloaded = 0
            with tmp_path.open("wb") as file_handle:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    file_handle.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total_size)
        tmp_path.replace(target)
        return target
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise


def launch_docker_installer(installer_path: Path | None = None) -> None:
    path = installer_path or INSTALLER_PATH
    subprocess.Popen(
        [str(path), "install", "--user", "--accept-license"],
        cwd=str(path.parent),
    )


def is_port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def pick_mysql_port(preferred_port: int = DEFAULT_PORT, max_attempts: int = 20) -> int:
    if not is_port_open(preferred_port):
        return preferred_port

    for offset in range(1, max_attempts + 1):
        candidate = preferred_port + offset
        if not is_port_open(candidate):
            return candidate

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def ensure_mysql_stack_files(
    *,
    port: int,
    database: str = DEFAULT_DATABASE,
    user: str = DEFAULT_USER,
    password: str = DEFAULT_PASSWORD,
) -> None:
    DOCKER_DIR.mkdir(parents=True, exist_ok=True)
    (DOCKER_DIR / "data").mkdir(parents=True, exist_ok=True)

    env_content = "\n".join(
        [
            f"MYSQL_IMAGE={MYSQL_IMAGE}",
            f"MYSQL_CONTAINER_NAME={MYSQL_CONTAINER_NAME}",
            f"MYSQL_PORT={port}",
            f"MYSQL_DATABASE={database}",
            f"MYSQL_USER={user}",
            f"MYSQL_PASSWORD={password}",
            f"MYSQL_ROOT_PASSWORD={password}",
            "",
        ]
    )
    ENV_PATH.write_text(env_content, encoding="utf-8")

    compose_content = """services:
  mysql:
    image: ${MYSQL_IMAGE}
    container_name: ${MYSQL_CONTAINER_NAME}
    restart: unless-stopped
    environment:
      MYSQL_DATABASE: ${MYSQL_DATABASE}
      MYSQL_USER: ${MYSQL_USER}
      MYSQL_PASSWORD: ${MYSQL_PASSWORD}
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
      TZ: Asia/Seoul
    ports:
      - "${MYSQL_PORT}:3306"
    volumes:
      - ./data:/var/lib/mysql
"""
    COMPOSE_PATH.write_text(compose_content, encoding="utf-8")


def pull_mysql_image() -> None:
    proc = subprocess.run(
        ["docker", "image", "inspect", MYSQL_IMAGE],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode == 0:
        return

    subprocess.run(
        ["docker", "pull", MYSQL_IMAGE],
        check=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def wait_for_mysql(port: int, timeout_seconds: int = 90) -> None:
    deadline = time.time() + timeout_seconds

    while time.time() < deadline:
        if is_port_open(port):
            return
        time.sleep(2)

    raise TimeoutError(
        f"MySQL 포트 {port}가 시간 안에 열리지 않았습니다. Docker Desktop이 완전히 시작되었는지 확인해 주세요."
    )


def start_local_mysql(
    *,
    preferred_port: int = DEFAULT_PORT,
    database: str = DEFAULT_DATABASE,
    user: str = DEFAULT_USER,
    password: str = DEFAULT_PASSWORD,
) -> LocalMySQLInfo:
    ready, message = docker_is_ready()
    if not ready:
        raise RuntimeError(message)

    port = pick_mysql_port(preferred_port)
    ensure_mysql_stack_files(port=port, database=database, user=user, password=password)

    pull_mysql_image()

    subprocess.run(
        ["docker", "compose", "-f", COMPOSE_PATH.name, "up", "-d"],
        check=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(DOCKER_DIR),
    )

    wait_for_mysql(port)

    return LocalMySQLInfo(
        host="127.0.0.1",
        port=port,
        user=user,
        password=password,
        database=database,
    )
