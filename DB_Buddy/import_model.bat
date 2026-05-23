@echo off
echo ===================================================
echo   Ollama GGUF Model Manual Import Script
echo ===================================================
echo.
echo [!] Please download the GGUF file from the following link first:
echo https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct-GGUF/resolve/main/qwen2.5-coder-7b-instruct-q4_k_m.gguf
echo.
echo [!] Make sure the downloaded file name is 'qwen2.5-coder-7b-instruct-q4_k_m.gguf',
echo     and place it in the same folder as this batch file (DB_Buddy).
echo.
pause

if not exist qwen2.5-coder-7b-instruct-q4_k_m.gguf (
    echo [ERROR] qwen2.5-coder-7b-instruct-q4_k_m.gguf not found in this directory!
    echo Please place the file in this folder and try again.
    pause
    exit /b 1
)

echo.
echo [1/2] Stopping existing background downloads if any is recommended.
echo [2/2] Importing the model. Please wait...
echo.

"C:\Users\leeah\AppData\Local\Programs\Ollama\ollama.exe" create qwen2.5-coder:7b -f Modelfile

if %ERRORLEVEL% equ 0 (
    echo.
    echo ===================================================
    echo  SUCCESS: Model import completed!
    echo  The model is now ready to use in DB-Buddy.
    echo ===================================================
) else (
    echo.
    echo [ERROR] Failed to import model. Please check if Ollama is running.
)

pause
