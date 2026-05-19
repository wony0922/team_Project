@echo off
echo ===================================================
echo   Ollama GGUF 모델 수동 임포트 스크립트
echo ===================================================
echo.
echo [!] 먼저 브라우저에서 아래 링크의 GGUF 파일을 다운로드 해주세요:
echo https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct-GGUF/resolve/main/qwen2.5-coder-7b-instruct-q4_k_m.gguf
echo.
echo [!] 다운로드 받은 파일 이름이 'qwen2.5-coder-7b-instruct-q4_k_m.gguf' 인지 확인하고,
echo     이 배치 파일과 같은 폴더(DB_Buddy)에 넣어주세요.
echo.
pause

if not exist qwen2.5-coder-7b-instruct-q4_k_m.gguf (
    echo [ERROR] qwen2.5-coder-7b-instruct-q4_k_m.gguf 파일이 현재 폴더에 존재하지 않습니다!
    echo 파일을 같은 폴더에 넣고 다시 실행해주세요.
    pause
    exit
)

echo.
echo [1/2] 기존 백그라운드 다운로드 작업이 있다면 중단하는 것을 권장합니다.
echo [2/2] 임포트(Importing)를 시작합니다. 잠시만 기다려주세요...
echo.

"C:\Users\leeah\AppData\Local\Programs\Ollama\ollama.exe" create qwen2.5-coder:7b -f Modelfile

if %ERRORLEVEL% equ 0 (
    echo.
    echo ===================================================
    echo  SUCCESS: 모델 임포트가 완료되었습니다!
    echo  이제 DB-Buddy 웹앱에서 정상적으로 작동합니다.
    echo ===================================================
) else (
    echo.
    echo [ERROR] 모델 등록 중 오류가 발생했습니다. Ollama가 켜져 있는지 확인해주세요.
)

pause
