# 제품 요구사항 정의서 (PRD)
## 프로젝트명: AI 기반 데이터베이스 학습 및 실습 비서 (가칭: DB-Buddy)

---

## 1. 프로젝트 개요 (Project Overview)
* **목적:** 데이터베이스(DB)를 처음 배우는 학생 및 초급 개발자가 로컬 환경에서 안전하고 직관적으로 SQL 문법, DB 설계(ERD), 그리고 쿼리 최적화(실행 계획)를 학습할 수 있도록 돕는 로컬 구동형 AI 비서 시스템 구축.
* **주요 타겟:** 컴퓨터공학 전공생, 국비지원 부트캠프 수강생, SQL 초급 개발자.
* **핵심 가치:** 1. 외부 유출 없는 완전한 로컬 데이터 보안.
  2. 단순 정답 제공이 아닌 단계별 힌트 및 실패 분석을 통한 교육적 접근.
  3. 텍스트와 시각화 자료(ERD, 흐름도)의 결합을 통한 직관적 이해 유도.

---

## 2. 목표 시스템 아키텍처 및 기술 스택 (System Architecture & Tech Stack)

### 2.1 아키텍처 개요
본 시스템은 사용자의 PC 또는 노트북(대중적 사양)에서 단독 구동되는 **로컬 웹 애플리케이션** 형태를 가집니다. 외부 API 호출 없이 로컬에 설치된 LLM 엔진(Ollama) 및 로컬 DB와 직접 통신합니다.

### 2.2 기술 스택 (Tech Stack)
* **Frontend & UI:** Streamlit (Python 기반 가벼운 웹 프레임워크)
* **LLM Orchestration:** LangChain (v0.3 이상)
* **Local LLM Inference Engine:** Ollama
* **Target LLM Model:** Qwen-2.5-Coder-7B-Instruct (또는 Llama-3.1-8B-Instruct) / 초저사양 대응용: Llama-3.2-3B-Instruct
* **Database Engine:** SQLite (내장형, 실습용) 및 MySQL/PostgreSQL (로컬 인스턴스 연동 지원)
* **Visualization Engine:** Mermaid.js (Streamlit 내장 또는 컴포넌트 형태 활용)

---

## 3. 오픈소스 활용 및 라이센스 정의 (Open Source & Licenses)

본 프로젝트는 오픈소스 소프트웨어를 적극 활용하여 개발 기간을 단축하고 신뢰성을 확보합니다. 의존성 라이센스를 검토하여 상용화 및 배포에 문제가 없도록 구성합니다.

| 분류 | 오픈소스 컴포넌트 / 모델 | 라이센스 (License) | 프로젝트 내 역할 |
| :--- | :--- | :--- | :--- |
| **추론 엔진** | Ollama | MIT License | 로컬 환경에서 LLM 모델 로드 및 API 엔드포인트 제공 |
| **AI 모델** | Qwen-2.5-Coder-7B-Instruct | Apache 2.0 | 자연어->SQL 변환, 에러 분석, 실행 계획 해설 |
| **프레임워크**| LangChain | MIT License | SQLDatabase 엔티티 관리, 프롬프트 체이닝, 텍스트 파싱 |
| **UI** | Streamlit | Apache 2.0 | 사용자 채팅 인터페이스, 데이터 테이블 출력, 페이지 레이아웃 |
| **시각화** | Mermaid.js | MIT License | 텍스트 기반 코드를 읽어 ERD 및 실행 계획 흐름도 렌더링 |

### 3.1 최종 결과물 라이센스 표기
* 본 프로젝트의 오픈소스 의존성(MIT, Apache 2.0)은 서로 완벽히 호환되므로, 본 제품의 최종 소스코드 및 배포본은 **MIT License**로 배포합니다. 
* 제품의 루트 디렉토리에 `LICENSE` 파일을 포함하고 사용된 오픈소스의 저작권 공지를 명시합니다.

---

## 4. 하드웨어 사양 가이드 (Hardware Requirements)
가장 대중적인 일반 노트북 및 데스크톱 환경을 기준으로 원활한 토큰 생성 속도(최소 15~20 tokens/sec)를 보장하기 위해 모델 양자화(Quantization) 버전을 기본 채택합니다.

* **최소 사양:** CPU i5 동급 이상 / RAM 16GB / 내장 그래픽 환경 (Llama-3.2-3B-Instruct 4-bit 양자화 모델 사용)
* **권장 사양:** CPU i7 동급 이상 / RAM 16GB 이상 / **NVIDIA GPU VRAM 6GB 이상 (RTX 3060 / 4050 등 노트북 GPU 포함)** (Qwen-2.5-Coder-7B-Instruct 4-bit 양자화 모델 사용)

---

## 5. 핵심 기능 상세 정의 (Functional Specifications)

### F-01: 텍스트 분석 기반 ERD 자동 시각화 (Text-to-ERD)
* **기능 개요:** 사용자가 자연어로 서술한 비즈니스 요구사항을 분석하여 DB 관계도(ERD)를 생성하고 시각화합니다.
* **유저 시나리오:** 1. 사용자가 채팅창에 *"쇼핑몰을 만들 건데 유저는 여러 개의 주문을 할 수 있고, 주문 안에는 여러 개의 상품이 담겨요."* 라고 입력 후 'ERD 생성' 버튼 클릭.
  2. AI 비서가 테이블 구조를 설계하고 Mermaid 코드를 출력.
  3. 화면 우측 탭에 시각화된 ERD 다이어그램이 즉시 렌더링됨.
* **상세 구현 로직 (Developer Guide):**
  * LangChain의 `ChatPromptTemplate`을 사용하여 LLM에게 항상 고정된 규칙의 `mermaid.js` ERD 코드 서식을 출력하도록 제안합니다.
  * **System Prompt 예시:**
    ```text
    너는 DB 모델링 전문가야. 사용자의 요구사항을 듣고 관계형 데이터베이스 스키마를 설계하여 반드시 ```mermaid ... ``` 형태의 ERD 코드만 반환해줘. 다른 설명은 생략해.
    서식:
    erDiagram
        CUSTOMER ||--o{ ORDER : places
        ORDER ||--|{ LINE-ITEM : contains
    ```
  * Streamlit 화면에서 `streamlit-mermaid` 컴포넌트 혹은 HTML iframe을 통해 마크다운 내의 mermaid 코드를 실시간 그래프로 변환합니다.

### F-02: 자연어 질의 기반 SQL 변환 및 실행 (Text-to-SQL & Run)
* **기능 개요:** 사용자가 자연어로 질문하면 해당하는 유효한 SQL 쿼리를 생성하고, 연동된 로컬 DB에서 이를 직접 실행하여 데이터 테이블 결과를 보여줍니다.
* **유저 시나리오:**
  1. 사용자가 *"우리 서비스에서 가입일이 가장 오래된 유저 5명의 이름과 이메일을 보여줘"* 라고 입력.
  2. AI 비서가 현재 로컬 DB의 스키마를 참고하여 `SELECT name, email FROM users ORDER BY created_at ASC LIMIT 5;` 코드를 생성해 화면에 표시.
  3. 하단의 '쿼리 실행' 버튼을 누르면, 로컬 DB(SQLite 등)에 쿼리가 수행되어 결과 데이터가 Grid(표) 형태로 출력됨.
* **상세 구현 로직 (Developer Guide):**
  * LangChain의 `create_sql_query_chain` 및 `SQLDatabase` 유틸리티를 활용합니다.
  * 개발자는 앱 시작 시 로컬 DB 파일 경로(예: `sqlite:///local_study.db`)를 `SQLDatabase.from_uri()`로 로드하여 인스턴스를 확보합니다.
  * DB 스키마 정보(DDL)를 프롬프트에 동적으로 주입하여 LLM이 엉뚱한 컬럼명을 지어내지 않도록 방지(Hallucination 방지)합니다.
  * **보안 필터링:** 생성된 쿼리 스트링에 `DROP`, `DELETE`, `TRUNCATE`, `ALTER` 등의 DDL/DML 파괴적 키워드가 포함되어 있는지 정규식으로 1차 검증한 후 execution을 허용합니다 (Read-Only 권한 권장).

### F-03: 인터랙티브 SQL 실행 및 친절한 '실패 분석기' (Error Analyzer)
* **기능 개요:** 사용자가 직접 작성한 쿼리나 AI가 추천한 쿼리를 실행하다가 DB 에러가 발생한 경우, 기계적인 에러 메시지를 초보자 눈높이에 맞게 해석하고 수정 방향을 안내합니다.
* **유저 시나리오:**
  1. 사용자가 조인 쿼리를 잘못 작성하여 DB 엔진으로부터 `unambiguous column name: id` 혹은 `Foreign Key Constraint Violated` 같은 불친절한 에러를 받음.
  2. 시스템은 화면에 붉은색 에러 박스와 함께 'AI 실패 분석 결과'를 보여줌.
  3. AI가 *"현재 `users` 테이블과 `orders` 테이블 모두에 `id`라는 컬럼이 있어서 데이터베이스가 어떤 것을 가리키는지 헷갈려하고 있어요. `users.id` 처럼 테이블 이름을 앞에 명시해주세요!"* 라고 친절히 설명함.
* **상세 구현 로직 (Developer Guide):**
  * Python의 `try-except` 블록을 활용하여 데이터베이스 실행 시 발생하는 `sqlite3.Error` 또는 `OperationalError`를 Catch합니다.
  * Catch한 에러 메시지와 사용자가 실행하려 했던 SQL 쿼리, 테이블 스키마 구조를 한데 묶어 LLM에 분석 요청을 보냅니다.
  * **프롬프트 템플릿:**
    ```text
    [스키마 정보]
    {db_schema}
    
    [사용자 쿼리]
    {user_query}
    
    [발생한 DB 에러 메시지]
    {raw_error_message}
    
    너는 친절한 데이터베이스 튜터야. 위 에러가 발생한 원인을 원리 위주로 쉽게 설명하고, 올바르게 수정한 쿼리 예시를 제공해줘.
    ```

### F-04: 실행 계획(EXPLAIN) 시각화 및 인덱스 멘토링 (Explain Analyzer)
* **기능 개요:** 작성된 SQL 쿼리가 데이터베이스 내부에서 어떻게 물리적으로 동작하는지(Full Table Scan vs Index Scan 등) 실행 계획을 뜯어서 설명해 줍니다.
* **유저 시나리오:**
  1. 사용자가 짠 복잡한 서브쿼리나 대용량 조회용 쿼리에 대해 '실행 계획 분석' 버튼을 누름.
  2. 시스템이 내부적으로 `EXPLAIN QUERY PLAN [사용자쿼리]`를 수행함.
  3. 로컬 AI가 그 원시 데이터를 기반으로 "이 쿼리는 인덱스가 없어 모든 데이터를 처음부터 끝까지 다 뒤지고 있습니다(SCAN TABLE). 성능 향상을 위해 어떤 컬럼에 인덱스를 걸면 좋을지" 가이드를 제공함.
* **상세 구현 로직 (Developer Guide):**
  * 연결된 DB 커넥터를 통해 `EXPLAIN QUERY PLAN ` 문구를 유저 쿼리 앞에 붙여 실행하고 결과 텍스트를 파싱합니다.
  * SQLite의 경우 `SCAN TABLE`, `SEARCH TABLE USING INDEX` 같은 키워드가 반환됩니다.
  * 이 결과 분석 테이블을 LLM에게 넘겨 처리 로직 흐름을 시각적 단계(Mermaid Flowchart)와 한글 해설로 변환하여 출력하게 유도합니다.

---

## 6. 개발 로드맵 및 단계별 구현 가이드

* **1단계 (환경 구성):** Ollama 다운로드 및 `qwen2.5-coder:7b` 모델 로컬 풀링(`ollama run qwen2.5-coder:7b`). Streamlit 기본 가상환경 구성.
* **2단계 (DB 가상화 및 F-02 구현):** 샘플 SQLite DB 파일 생성 및 LangChain 연동. 자연어로 던진 질문이 정상적인 SQL로 치환되어 데이터프레임으로 출력되는지 검증.
* **3단계 (F-03 에러 핸들러 도입):** 의도적으로 문법 에러 및 제약조건 위반 쿼리를 던진 후, Exception 데이터가 LLM 프롬프트로 바인딩되어 한국어 멘토링 텍스트로 치환되는 파이프라인 완성.
* **4단계 (F-01, F-04 시각화 컴포넌트 결합):** Mermaid 렌더러 모듈을 Streamlit에 임베딩하여 다이어그램 출력 레이아웃 다듬기 및 최종 QA.

---
**작성일자:** 2026년 5월 19일  
**작성자:** 시니어 IT 서비스 기획자
