# team_Project

## DB-Buddy 실행 방법

> [수정됨] 로컬에서 저장소를 받은 뒤 바로 실행할 수 있도록 실행 절차를 정리했습니다.

```bat
runFile!!!!!!!!!!!!.bat
```

위 배치 파일은 `DB_Buddy/bootstrap.py`를 실행합니다. 필요한 Python 패키지가 없으면 설치 여부를 묻고, 이후 Streamlit 앱을 실행합니다.

## localhost가 아닌 주소로 실행

> [수정됨] 기본 실행은 `0.0.0.0:8501`에 바인딩되도록 조정했습니다.

같은 네트워크의 다른 기기에서 접속하려면 실행한 PC의 IPv4 주소로 접속합니다.

```text
http://<실행한-PC-IP>:8501
```

호스트나 포트를 바꾸려면 실행 전에 환경변수를 지정할 수 있습니다.

```bat
set DB_BUDDY_HOST=0.0.0.0
set DB_BUDDY_PORT=8501
runFile!!!!!!!!!!!!.bat
```
