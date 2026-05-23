import subprocess
import time
import webview
import socket
import sys
import os

def is_port_open(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def _find_python():
    """venv → .venv → 시스템 Python 순서로 사용 가능한 Python 실행파일을 찾습니다."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(base_dir, "venv", "Scripts", "python.exe"),
        os.path.join(base_dir, ".venv", "Scripts", "python.exe"),
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return sys.executable  # 가상환경이 없으면 시스템 Python 사용

def start_streamlit():
    python_exe = _find_python()
    app_py = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")
    
    # Streamlit을 headless 모드로 실행
    return subprocess.Popen(
        [python_exe, "-m", "streamlit", "run", app_py, "--server.headless", "true", "--server.port", "8501"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0 # 윈도우 창 안 띄움
    )

if __name__ == "__main__":
    # Streamlit 실행
    proc = start_streamlit()
    
    # Streamlit이 완전히 켜질 때까지 대기 (최대 15초)
    for _ in range(30):
        if is_port_open(8501):
            break
        time.sleep(0.5)
        
    try:
        # pywebview로 데스크탑 창 띄우기
        # Windows OS에서는 Edge HTML/WebView2 기반 창이 뜹니다.
        webview.create_window("DB-Buddy Desktop", "http://127.0.0.1:8501", width=1400, height=900)
        webview.start()
    finally:
        # 데스크탑 창이 닫히면 Streamlit 백그라운드 프로세스도 함께 깨끗하게 종료
        proc.terminate()
        proc.wait()
