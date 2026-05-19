import subprocess
import time
import webview
import socket
import sys
import os

def is_port_open(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def start_streamlit():
    # 현재 스크립트 위치 기준으로 python.exe 경로 탐색
    python_exe = os.path.join(os.path.dirname(__file__), "venv", "Scripts", "python.exe")
    if not os.path.exists(python_exe):
        python_exe = sys.executable  # venv 환경이 아닐 경우 시스템 파이썬 사용
        
    app_py = os.path.join(os.path.dirname(__file__), "app.py")
    
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
