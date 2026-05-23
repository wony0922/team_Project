@echo off
rem -------------------------------------------------
rem DB_Buddy Execution Batch File (including bootstrap)
rem -------------------------------------------------

rem Move to the directory where this script is located
cd /d "%~dp0"

rem -------------------------------------------------
rem Search for virtual environment (.venv / venv)
rem -------------------------------------------------
if exist ".venv\Scripts\activate.bat" (
    echo [INFO] Activating .venv virtual environment.
    call .venv\Scripts\activate.bat
) else if exist "venv\Scripts\activate.bat" (
    echo [INFO] Activating venv virtual environment.
    call venv\Scripts\activate.bat
) else if exist "DB_Buddy\venv\Scripts\activate.bat" (
    echo [INFO] Activating DB_Buddy\venv virtual environment.
    call DB_Buddy\venv\Scripts\activate.bat
) else if exist "DB_Buddy\.venv\Scripts\activate.bat" (
    echo [INFO] Activating DB_Buddy\.venv virtual environment.
    call DB_Buddy\.venv\Scripts\activate.bat
) else (
    echo [INFO] Virtual environment not found. Using system Python.
)

rem Run bootstrap.py (handles packages installation and app launch)
python DB_Buddy\bootstrap.py

rem Exit batch file
exit /b
