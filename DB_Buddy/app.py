import streamlit as st
from streamlit_mermaid import st_mermaid
import db_utils
import llm_chain
import os

st.set_page_config(page_title="DB-Buddy", layout="wide", page_icon="🤖")

st.title("🤖 DB-Buddy: 데이터베이스 학습 비서")
st.markdown("자연어로 ERD를 설계하고, SQL을 자동 생성하며, 쿼리 분석 및 에러 멘토링까지 제공합니다.")

# DB 초기화 (기본 SQLite)
if not os.path.exists('local_study.db'):
    db_utils.initialize_database()

# 세션 상태 초기화
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'current_query' not in st.session_state:
    st.session_state.current_query = ""
if 'erd_code' not in st.session_state:
    st.session_state.erd_code = ""
if 'db_url' not in st.session_state:
    st.session_state.db_url = db_utils.DEFAULT_SQLITE_URL

# 사이드바: 설정
with st.sidebar:
    st.header("⚙️ 데이터베이스 연결 설정")
    db_type = st.radio("데이터베이스 유형", ["SQLite (기본/실습용)", "MySQL (로컬 연동)"])
    
    if db_type == "MySQL (로컬 연동)":
        mysql_host = st.text_input("Host", value="localhost")
        mysql_port = st.text_input("Port", value="3306")
        mysql_user = st.text_input("User", value="root")
        mysql_pwd = st.text_input("Password", type="password")
        mysql_db = st.text_input("Database Name", value="test_db")
        
        if st.button("MySQL 연결 적용"):
            url = f"mysql+pymysql://{mysql_user}:{mysql_pwd}@{mysql_host}:{mysql_port}/{mysql_db}"
            try:
                # 연결 테스트
                engine = db_utils.get_engine(url)
                with engine.connect() as conn:
                    conn.execute(db_utils.text("SELECT 1"))
                st.session_state.db_url = url
                st.success("✅ MySQL 접속 및 연결에 성공하였습니다!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ MySQL 연결 실패: {e}\n\n입력한 접속 정보를 다시 확인해 주세요.")
    else:
        st.session_state.db_url = db_utils.DEFAULT_SQLITE_URL
        st.info("기본 SQLite 실습 데이터베이스를 사용합니다.")

    st.markdown("---")
    st.subheader("📌 현재 DB 스키마")
    schema_info = db_utils.get_schema_info(st.session_state.db_url)
    st.code(schema_info, language='sql')

# 탭으로 기능 분리
import pandas as pd

# 라이센스 공지 표시 (사이드바 하단)
with st.sidebar:
    st.markdown("---")
    st.markdown(
        "### 📜 Open Source Licenses\n"
        "본 프로젝트는 **MIT License**로 배포됩니다.\n"
        "사용된 주요 오픈소스:\n"
        "- **Streamlit**: Apache 2.0\n"
        "- **LangChain**: MIT\n"
        "- **Mermaid.js**: MIT\n"
        "- **Faker**: MIT\n"
        "- **PyMySQL**: MIT\n"
    )

if db_type == "SQLite (기본/실습용)":
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📁 실습 DB 관리 및 더미데이터",
        "📊 스키마 ERD 시각화",
        "🗣️ SQL 생성 및 실행",
        "🔍 SQL 구문 해석기",
        "⚡ 실행 계획 분석"
    ])
    
    with tab1:
        st.header("📁 실습용 DB 관리 & Faker 더미데이터 생성")
        st.markdown("현재 로컬 SQLite 실습 데이터베이스의 테이블 목록 및 각 테이블의 저장된 레코드 수를 보여줍니다.")
        
        try:
            engine = db_utils.get_engine(st.session_state.db_url)
            from sqlalchemy import inspect
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            
            if not tables:
                st.info("데이터베이스에 생성된 테이블이 없습니다.")
            else:
                table_counts = []
                with engine.connect() as conn:
                    for t in tables:
                        try:
                            count = conn.execute(db_utils.text(f"SELECT COUNT(*) FROM `{t}`")).scalar()
                            table_counts.append({"테이블명": t, "저장된 레코드 수 (Rows)": count})
                        except Exception:
                            table_counts.append({"테이블명": t, "저장된 레코드 수 (Rows)": "조회 실패"})
                df_counts = pd.DataFrame(table_counts)
                st.dataframe(df_counts, use_container_width=True)
        except Exception as e:
            st.error(f"테이블 조회 실패: {e}")
            tables = []
            
        st.markdown("---")
        st.subheader("🤖 Faker 기반 한글 더미데이터 생성")
        st.markdown("외래키 참조 관계를 고려하여(부모 테이블 우선) 무결성을 깨뜨리지 않고 실감나는 한글 더미데이터를 삽입합니다.")
        row_count = st.slider("테이블당 생성할 데이터 수", min_value=5, max_value=50, value=10, step=5)
        
        if st.button("더미 데이터 생성 실행", type="primary", use_container_width=True):
            if not tables:
                st.warning("데이터베이스에 테이블이 존재하지 않습니다. 먼저 스키마를 생성해주세요.")
            else:
                with st.spinner("외래키 참조 관계 분석 및 더미 데이터 삽입 중..."):
                    try:
                        ordered_tables = db_utils.get_tables_in_topological_order(st.session_state.db_url)
                        for t in ordered_tables:
                            db_utils.insert_dummy_data(st.session_state.db_url, t, row_count)
                        st.success(f"성공적으로 모든 테이블에 {row_count}개씩의 더미 데이터를 생성하여 삽입했습니다!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"더미 데이터 생성 실패: {e}")
                        
        st.markdown("---")
        st.subheader("🗑️ 데이터 초기화 및 복원")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("⚠️ 모든 테이블 레코드만 삭제", help="테이블 구조(스키마)는 유지하고 데이터만 삭제합니다.", use_container_width=True):
                with st.spinner("테이블 데이터를 지우는 중..."):
                    try:
                        db_utils.clear_all_tables(st.session_state.db_url)
                        st.success("모든 테이블의 데이터를 성공적으로 지웠습니다.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"데이터 삭제 실패: {e}")
        with col2:
            if st.button("🔄 실습 DB 초기 상태로 복원", help="모든 테이블을 DROP하고 기본 샘플 데이터셋으로 다시 채웁니다.", use_container_width=True):
                with st.spinner("초기 샘플 데이터 복원 중..."):
                    try:
                        db_utils.reset_database_to_default()
                        st.session_state.erd_code = ""
                        st.success("SQLite 실습 DB가 초기 샘플 스키마 및 레코드로 완전히 리셋되었습니다.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"복원 실패: {e}")
                        
    with tab2:
        st.header("📊 현재 테이블 기반 ERD 생성")
        st.markdown("현재 데이터베이스에 실제로 존재하는 테이블 구조와 관계(외래키)를 판독하여 시각화합니다.")
        
        if st.button("현재 DB 스펙으로 ERD 자동 생성", key="sqlite_erd_gen_btn", use_container_width=True):
            with st.spinner("데이터베이스 스키마 및 제약 조건 파싱 중..."):
                try:
                    erd_result = llm_chain.generate_erd_from_schema(st.session_state.db_url)
                    st.session_state.erd_code = erd_result
                    if "erDiagram" in erd_result:
                        st.success("ERD 생성 성공!")
                    else:
                        st.warning("⚠️ AI가 올바른 ERD 형식을 반환하지 못했습니다. 다시 시도해 주세요.")
                except Exception as e:
                    st.error(f"ERD 생성 실패: {e}")
                    
        if st.session_state.erd_code:
            if "erDiagram" in st.session_state.erd_code:
                st.subheader("생성된 ERD (Mermaid)")
                try:
                    st_mermaid(st.session_state.erd_code, height=500)
                except Exception:
                    st.error("ERD 렌더링 중 오류가 발생했습니다. Mermaid 코드를 확인해 주세요.")
            else:
                st.warning("⚠️ 올바른 ERD 다이어그램 코드가 생성되지 않았습니다. AI가 다이어그램 구조를 반환할 수 있도록 다시 시도해 주세요.")
            with st.expander("Mermaid 코드 보기"):
                st.code(st.session_state.erd_code, language='mermaid')

    with tab3:
        st.header("SQL 자동 생성 및 실행")
        
        col1, col2 = st.columns([1, 1])
        with col1:
            st.subheader("🗣️ 자연어로 질문하기")
            user_q = st.text_input("DB에 대해 궁금한 점을 자연어로 질문하세요.", placeholder="가입일이 가장 오래된 유저 5명의 이름과 이메일을 보여줘", key="sqlite_q")
            if st.button("AI SQL 생성", key="sqlite_sql_gen_btn"):
                with st.spinner("AI가 쿼리를 작성 중입니다..."):
                    try:
                        sql_result = llm_chain.generate_sql(user_q, st.session_state.db_url)
                        st.session_state.current_query = sql_result
                        st.success("SQL 쿼리가 생성되었습니다.")
                    except Exception as e:
                        st.error(f"SQL 생성 실패: {e}")
                        
        with col2:
            st.subheader("📂 SQL 파일 불러오기")
            uploaded_file = st.file_uploader(".sql 파일을 업로드하면 텍스트 에디터로 불러옵니다.", type=["sql"], key="sqlite_upload")
            if uploaded_file is not None:
                string_data = uploaded_file.getvalue().decode("utf-8")
                st.session_state.current_query = string_data
                st.success("파일 내용을 성공적으로 불러왔습니다.")
                
        st.markdown("---")
        st.session_state.current_query = st.text_area("🚀 실행할 SQL 쿼리", value=st.session_state.current_query, height=150, key="sqlite_query_area")
        
        if st.button("쿼리 실행", type="primary", use_container_width=True):
            query = st.session_state.current_query
            if not query.strip():
                st.warning("실행할 쿼리를 입력해주세요.")
            else:
                with st.spinner("데이터베이스 쿼리 실행 중..."):
                    df, error = db_utils.execute_query(query, st.session_state.db_url)
                    
                    if error:
                        st.error("🚨 쿼리 실행 중 에러가 발생했습니다.")
                        st.code(error, language='text')
                        
                        st.info("AI 비서가 에러 원인을 분석합니다...")
                        with st.spinner("에러 원인 분석 중..."):
                            try:
                                analysis_result = llm_chain.analyze_error(query, error, st.session_state.db_url)
                                st.markdown("### 💡 AI 실패 분석 결과")
                                st.markdown(analysis_result)
                            except Exception as ai_e:
                                st.error(f"AI 분석 중 문제 발생: {ai_e}")
                    else:
                        st.success("✅ 쿼리 실행 성공!")
                        st.dataframe(df, use_container_width=True)

    with tab4:
        st.header("🔍 SQL 구문 해석기")
        st.markdown("작성된 SQL 쿼리를 입력하면 AI가 작동 원리와 데이터 결과를 한국어로 알기 쉽게 번역해 줍니다.")
        
        sql_to_translate = st.text_area("해석할 SQL 쿼리문을 입력하세요.", height=150, placeholder="SELECT name, COUNT(orders.id) FROM users LEFT JOIN orders ON users.id = orders.user_id GROUP BY users.name HAVING COUNT(orders.id) > 1;", key="translate_sql_input")
        if st.button("구문 해석 및 번역 실행", type="primary", use_container_width=True):
            if not sql_to_translate.strip():
                st.warning("해석할 SQL 쿼리문을 입력해주세요.")
            else:
                with st.spinner("AI가 구문을 해설하는 중..."):
                    try:
                        translated_text = llm_chain.translate_sql(sql_to_translate, st.session_state.db_url)
                        st.markdown("### 💡 AI SQL 해석 결과")
                        st.markdown(translated_text)
                    except Exception as e:
                        st.error(f"구문 해석 실패: {e}")

    with tab5:
        st.header("실행 계획(EXPLAIN) 최적화 분석")
        st.markdown("복잡한 쿼리나 대용량 조회용 쿼리가 DB 내부에서 어떻게 동작하는지 분석해드립니다.")
        
        opt_query = st.text_area("분석할 쿼리를 입력하세요.", value=st.session_state.current_query, height=100, key="explain_input")
        
        if st.button("실행 계획 분석 및 AI 멘토링", use_container_width=True):
            if not opt_query.strip():
                st.warning("분석할 쿼리를 입력해주세요.")
            else:
                with st.spinner("EXPLAIN 실행 및 분석 중..."):
                    explain_text = db_utils.execute_explain_plan(opt_query, st.session_state.db_url)
                    if "에러 발생" in explain_text:
                        st.error(explain_text)
                    else:
                        st.subheader("EXPLAIN QUERY PLAN 원본 결과")
                        st.code(explain_text, language='text')
                        
                        with st.spinner("AI가 실행 계획을 해석하고 있습니다..."):
                            try:
                                explain_analysis = llm_chain.analyze_explain_plan(opt_query, explain_text)
                                st.markdown("### 💡 AI 실행 계획 멘토링")
                                
                                if "```mermaid" in explain_analysis:
                                    parts = explain_analysis.split("```mermaid")
                                    st.markdown(parts[0])
                                    for part in parts[1:]:
                                        sub_parts = part.split("```", 1)
                                        if len(sub_parts) > 1:
                                            mermaid_code = sub_parts[0].strip()
                                            st_mermaid(mermaid_code)
                                            st.markdown(sub_parts[1])
                                        else:
                                            st.code(part, language='mermaid')
                                else:
                                    st.markdown(explain_analysis)
                                    
                            except Exception as ai_e:
                                st.error(f"AI 분석 중 문제 발생: {ai_e}")

else: # MySQL
    if not st.session_state.db_url.startswith("mysql"):
        st.warning("🚨 MySQL 접속 정보가 적용되지 않았습니다. 왼쪽 사이드바에서 접속 정보를 입력한 후 'MySQL 연결 적용' 버튼을 눌러주세요.")
        st.stop()
        
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 MySQL ERD 시각화",
        "🗣️ 자연어 쿼리 변환기",
        "📖 DB 사전 및 문서화",
        "⚙️ DB 정규화 & 리팩토링",
        "⚡ 실행 계획 분석"
    ])
    
    # 세션 상태 초기화
    if 'mysql_erd_code' not in st.session_state:
        st.session_state.mysql_erd_code = ""
    if 'mysql_query' not in st.session_state:
        st.session_state.mysql_query = ""
    if 'mysql_docs' not in st.session_state:
        st.session_state.mysql_docs = ""
        
    with tab1:
        st.header("📊 MySQL 스키마 ERD 시각화")
        st.markdown("연동된 MySQL 데이터베이스의 실제 테이블과 외래키 관계를 판독하여 실시간으로 ERD 다이어그램을 시각화합니다.")
        
        if st.button("MySQL 스펙으로 ERD 자동 생성", key="mysql_erd_gen_btn", use_container_width=True):
            with st.spinner("MySQL 데이터베이스 스키마 파싱 중..."):
                try:
                    erd_result = llm_chain.generate_erd_from_schema(st.session_state.db_url)
                    st.session_state.mysql_erd_code = erd_result
                    if "erDiagram" in erd_result:
                        st.success("MySQL ERD 생성 완료!")
                    else:
                        st.warning("⚠️ AI가 올바른 ERD 형식을 반환하지 못했습니다. 다시 시도해 주세요.")
                except Exception as e:
                    st.error(f"ERD 생성 실패: {e}")
                    
        if st.session_state.mysql_erd_code:
            if "erDiagram" in st.session_state.mysql_erd_code:
                st.subheader("생성된 ERD (Mermaid)")
                try:
                    st_mermaid(st.session_state.mysql_erd_code, height=500)
                except Exception:
                    st.error("ERD 렌더링 중 오류가 발생했습니다. Mermaid 코드를 확인해 주세요.")
            else:
                st.warning("⚠️ 올바른 ERD 다이어그램 코드가 생성되지 않았습니다. AI가 다이어그램 구조를 반환할 수 있도록 다시 시도해 주세요.")
            with st.expander("Mermaid 코드 보기"):
                st.code(st.session_state.mysql_erd_code, language='mermaid')
                
    with tab2:
        st.header("🗣️ 자연어 쿼리 변환기 (MySQL)")
        st.markdown("자연어로 요청하면 연동된 MySQL의 실제 스키마 구조를 분석하여 최적화된 SQL을 자동 생성하고 즉시 실행해 줍니다.")
        
        col1, col2 = st.columns([1, 1])
        with col1:
            st.subheader("🗣️ 자연어로 질문하기")
            user_q_mysql = st.text_input("MySQL 데이터베이스에 대해 자연어로 질문하세요.", placeholder="결제 금액이 가장 큰 상위 3명의 회원 이메일을 보여줘", key="mysql_q_input")
            if st.button("AI SQL 생성 (MySQL)", key="mysql_sql_gen_btn"):
                with st.spinner("AI가 MySQL 쿼리를 작성 중입니다..."):
                    try:
                        sql_result = llm_chain.generate_sql(user_q_mysql, st.session_state.db_url)
                        st.session_state.mysql_query = sql_result
                        st.success("MySQL 쿼리가 생성되었습니다.")
                    except Exception as e:
                        st.error(f"SQL 생성 실패: {e}")
                        
        with col2:
            st.subheader("📂 SQL 파일 불러오기")
            uploaded_file_mysql = st.file_uploader(".sql 파일을 업로드하여 텍스트 에디터로 불러옵니다.", type=["sql"], key="mysql_upload")
            if uploaded_file_mysql is not None:
                string_data = uploaded_file_mysql.getvalue().decode("utf-8")
                st.session_state.mysql_query = string_data
                st.success("파일 내용을 성공적으로 불러왔습니다.")
                
        st.markdown("---")
        st.session_state.mysql_query = st.text_area("🚀 실행할 MySQL 쿼리", value=st.session_state.mysql_query, height=150, key="mysql_query_area")
        
        if st.button("MySQL 쿼리 실행", type="primary", use_container_width=True):
            query = st.session_state.mysql_query
            if not query.strip():
                st.warning("실행할 쿼리를 입력해주세요.")
            else:
                with st.spinner("MySQL 쿼리 실행 중..."):
                    df, error = db_utils.execute_query(query, st.session_state.db_url)
                    
                    if error:
                        st.error("🚨 쿼리 실행 중 에러가 발생했습니다.")
                        st.code(error, language='text')
                        
                        st.info("AI 비서가 에러 원인을 분석합니다...")
                        with st.spinner("에러 원인 분석 중..."):
                            try:
                                analysis_result = llm_chain.analyze_error(query, error, st.session_state.db_url)
                                st.markdown("### 💡 AI 실패 분석 결과")
                                st.markdown(analysis_result)
                            except Exception as ai_e:
                                st.error(f"AI 분석 중 문제 발생: {ai_e}")
                    else:
                        st.success("✅ 쿼리 실행 성공!")
                        st.dataframe(df, use_container_width=True)
                        
    with tab3:
        st.header("📖 DB 사전 및 스키마 자동 문서화")
        st.markdown("현재 MySQL 데이터베이스에 등록된 테이블과 컬럼 속성을 일목요연하게 표와 텍스트로 정리한 데이터 사전을 자동 작성합니다.")
        
        if st.button("스펙 문서 자동 빌드", type="primary", key="mysql_doc_gen_btn", use_container_width=True):
            with st.spinner("MySQL 구조 및 메타데이터를 수집하여 기술 문서를 생성하는 중..."):
                try:
                    docs = llm_chain.generate_db_documentation(st.session_state.db_url)
                    st.session_state.mysql_docs = docs
                    st.success("DB 문서 빌드 성공!")
                except Exception as e:
                    st.error(f"문서 생성 실패: {e}")
                    
        if st.session_state.mysql_docs:
            st.markdown("---")
            st.markdown("### 📝 생성된 데이터 사전 및 스펙 문서")
            st.markdown(st.session_state.mysql_docs)
            st.download_button(
                label="📥 마크다운 파일로 내보내기",
                data=st.session_state.mysql_docs,
                file_name="mysql_db_dictionary.md",
                mime="text/markdown",
                use_container_width=True
            )
            
    with tab4:
        st.header("⚙️ DB 정규화 & 구조 리팩토링 어시스턴트")
        st.markdown("자연어로 정규화(1NF/2NF/3NF) 요구사항이나 성능 향상을 위한 구조 변경 요청을 입력하면 AI가 데이터 구조 설계안과 마이그레이션 DDL을 추천해 드립니다.")
        
        refactor_req = st.text_area("정규화 또는 구조 개선안 요구사항 입력", height=150, placeholder="예시:\n- 상품 결제 정보와 구매자 상세 정보가 한 테이블에 섞여 있는데, 이를 3정규형(3NF)으로 분리하는 DDL 및 개선 제안을 알려줘.\n- 대용량 트래픽 처리를 위해 연관된 주문 내역 테이블들을 어떻게 성능 개선해야 할지 추천해줘.", key="mysql_refactor_input")
        if st.button("구조 개선 설계안 및 DDL 제안 요청", type="primary", key="mysql_refactor_btn", use_container_width=True):
            if not refactor_req.strip():
                st.warning("요구사항을 상세히 작성해 주세요.")
            else:
                with st.spinner("구조 분석 및 리팩토링 방안 수립 중..."):
                    try:
                        refactor_result = llm_chain.assist_db_normalization(refactor_req, st.session_state.db_url)
                        st.markdown("### 💡 AI 정규화 및 리팩토링 제안 결과")
                        st.markdown(refactor_result)
                    except Exception as e:
                        st.error(f"구조 리팩토링 제안 실패: {e}")
                        
    with tab5:
        st.header("⚡ 실행 계획(EXPLAIN) 최적화 분석")
        st.markdown("MySQL 실행 계획 분석 결과를 파싱하여 Full Scan 유무 및 인덱스 튜닝 권장사항을 한글로 제시해 드립니다.")
        
        opt_query_mysql = st.text_area("분석할 MySQL 쿼리를 입력하세요.", value=st.session_state.mysql_query, height=100, key="explain_input_mysql")
        
        if st.button("MySQL 실행 계획 분석 및 AI 멘토링", key="mysql_explain_run_btn", use_container_width=True):
            if not opt_query_mysql.strip():
                st.warning("분석할 쿼리를 입력해주세요.")
            else:
                with st.spinner("MySQL EXPLAIN 실행 및 수집 중..."):
                    explain_text = db_utils.execute_explain_plan(opt_query_mysql, st.session_state.db_url)
                    if "에러 발생" in explain_text:
                        st.error(explain_text)
                    else:
                        st.subheader("EXPLAIN 결과 원본")
                        st.code(explain_text, language='text')
                        
                        with st.spinner("AI가 실행 계획을 해석하고 있습니다..."):
                            try:
                                explain_analysis = llm_chain.analyze_explain_plan(opt_query_mysql, explain_text)
                                st.markdown("### 💡 AI 실행 계획 멘토링")
                                
                                if "```mermaid" in explain_analysis:
                                    parts = explain_analysis.split("```mermaid")
                                    st.markdown(parts[0])
                                    for part in parts[1:]:
                                        sub_parts = part.split("```", 1)
                                        if len(sub_parts) > 1:
                                            mermaid_code = sub_parts[0].strip()
                                            st_mermaid(mermaid_code)
                                            st.markdown(sub_parts[1])
                                        else:
                                            st.code(part, language='mermaid')
                                else:
                                    st.markdown(explain_analysis)
                                    
                            except Exception as ai_e:
                                st.error(f"AI 분석 중 문제 발생: {ai_e}")

