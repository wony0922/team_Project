# 원래 실행파일 역할을 bootstrap.py가 해 주지만,
# 부트스트랩 파일 대신 .bat 파일을 더블 클릭해서 실행할 것.
# 수정에 용이하게 하여 유지 보수성을 높이기 위함

@echo off
rem -------------------------------------------------
rem DB_Buddy 실행 배치 파일 (bootstrap 포함)
rem -------------------------------------------------
rem 현재 스크립트가 위치한 디렉터리로 이동
cd /d "%~dp0"

rem 가상환경 활성화
call .venv\Scripts\activate.bat

rem bootstrap.py 실행 (패키지 설치·앱 실행 담당)
python DB_Buddy\bootstrap.py

rem 배치 파일 종료
exit /b
