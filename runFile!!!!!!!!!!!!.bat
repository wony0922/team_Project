@echo off
rem -------------------------------------------------
rem DB_Buddy 실행 배치 파일 (bootstrap 포함)
rem 부트스트랩 파일 대신 .bat 파일을 더블 클릭해서 실행할 것.
rem -------------------------------------------------

rem 현재 스크립트가 위치한 디렉터리로 이동
cd /d "%~dp0"

rem -------------------------------------------------
rem 가상환경 탐색 (.venv / venv)
rem -------------------------------------------------
if exist ".venv\Scripts\activate.bat" (
    echo [INFO] .venv 가상환경을 활성화합니다.
    call .venv\Scripts\activate.bat
) else if exist "venv\Scripts\activate.bat" (
    echo [INFO] venv 가상환경을 활성화합니다.
    call venv\Scripts\activate.bat
) else if exist "DB_Buddy\venv\Scripts\activate.bat" (
    echo [INFO] DB_Buddy\venv 가상환경을 활성화합니다.
    call DB_Buddy\venv\Scripts\activate.bat
) else if exist "DB_Buddy\.venv\Scripts\activate.bat" (
    echo [INFO] DB_Buddy\.venv 가상환경을 활성화합니다.
    call DB_Buddy\.venv\Scripts\activate.bat
) else (
    echo [INFO] 가상환경을 찾지 못했습니다. 시스템 Python을 사용합니다.
)

rem bootstrap.py 실행 (패키지 설치 및 앱 실행 담당)
python DB_Buddy\bootstrap.py

rem 배치 파일 종료
exit /b
