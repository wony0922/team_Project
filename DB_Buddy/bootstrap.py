## 부트스트랩 파일.
# 처음 app.py를 실행할 때 Streamlit 및 필요한 패키지가 없으면 자동 설치하고 실행.
# 학교 컴퓨터로 시연할 가능성이 높을 것 같아서......
#  참고로 Tkinter GUI로 다운로드를 받을 것인지 물어 볼텐데, 당연히 무지성 yes 연타!!

import importlib.util as importlib_util, os, subprocess, sys
from pathlib import Path

# -------------------------------------------------------------------------
# 다운로드 받아야 할 패키지 리스트
# -------------------------------------------------------------------------
# [수정됨] pip 패키지명과 import 모듈명이 다른 패키지를 함께 관리합니다.
REQUIRED_PACKAGES = [
    ("streamlit", "streamlit"),
    ("streamlit-mermaid", "streamlit_mermaid"),
    ("pandas", "pandas"),
    ("SQLAlchemy", "sqlalchemy"),
    ("PyMySQL", "pymysql"),
    ("Faker", "faker"),
    ("langchain", "langchain"),
    ("langchain-community", "langchain_community"),
]

# -------------------------------------------------------------------------
# 누락된 패키지 확인
# -------------------------------------------------------------------------
missing_packages = [pkg for pkg, module in REQUIRED_PACKAGES if importlib_util.find_spec(module) is None]

# -------------------------------------------------------------------------
# GUI 로 Yes/No 확인 함수 (Tkinter)
# -------------------------------------------------------------------------
def _ask_yes_no(title: str, message: str) -> bool:
    """Tkinter 윈도우에 Yes / No 버튼을 표시하고 사용자의 선택을 반환합니다."""
    import tkinter as tk
    result = {"answer": None}

    def on_yes():
        result["answer"] = True
        dlg.destroy()

    def on_no():
        result["answer"] = False
        dlg.destroy()

    dlg = tk.Tk()
    dlg.title(title)
    tk.Label(dlg, text=message, wraplength=400).pack(padx=20, pady=10)
    btn_frame = tk.Frame(dlg)
    btn_frame.pack(pady=10)
    tk.Button(btn_frame, text="Yes", width=8, command=on_yes).pack(side="left", padx=5)
    tk.Button(btn_frame, text="No", width=8, command=on_no).pack(side="right", padx=5)
    dlg.mainloop()
    return result["answer"]

# -------------------------------------------------------------------------
# 메인 로직: 패키지 설치 후 Streamlit 실행
# -------------------------------------------------------------------------
def main():
    if missing_packages:
        try:
            pkg_list = ", ".join(missing_packages)
            answer = _ask_yes_no(
                "Missing Packages",
                f"{len(missing_packages)}개의 패키지를 설치해야 합니다.\n패키지 리스트: {pkg_list}\n지금 설치하시겠습니까?",
            )
            if not answer:
                sys.exit("User cancelled package installation.")
        except Exception:
            # Tkinter 사용이 불가능한 경우 콘솔 프롬프트 fallback
            resp = input(
                f"{len(missing_packages)} packages are missing: {', '.join(missing_packages)}. Install now? [y/N] "
            )
            if resp.lower() != "y":
                sys.exit("Package installation cancelled by user.")
        # pip 로 누락된 패키지 설치
        subprocess.check_call([sys.executable, "-m", "pip", "install", *missing_packages])

    # Streamlit 앱 실행
    app_path = Path(__file__).resolve().parent / "app.py"
    # [수정됨] localhost 전용이 아니라 외부 접속 가능한 0.0.0.0 바인딩을 기본값으로 사용합니다.
    host = os.environ.get("DB_BUDDY_HOST", "0.0.0.0")
    port = os.environ.get("DB_BUDDY_PORT", "8501")
    subprocess.check_call([
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_path),
        "--server.address",
        host,
        "--server.port",
        port,
    ])

if __name__ == "__main__":
    main()
