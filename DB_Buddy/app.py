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
            st.session_state.db_url = url
            st.success("MySQL 접속 정보가 적용되었습니다.")
    else:
        st.session_state.db_url = db_utils.DEFAULT_SQLITE_URL
        st.info("기본 SQLite 실습 데이터베이스를 사용합니다.")

    st.markdown("---")
    st.subheader("📌 현재 DB 스키마")
    schema_info = db_utils.get_schema_info(st.session_state.db_url)
    st.code(schema_info, language='sql')

# 탭으로 기능 분리
tab1, tab2, tab3 = st.tabs(["F-01: ERD 시각화", "F-02 & F-03: SQL 실행 및 에러 분석", "F-04: 실행 계획 분석"])

with tab1:
    st.header("요구사항을 ERD로 변환")
    req_input = st.text_area("비즈니스 요구사항을 자연어로 입력하세요.", height=150, placeholder="쇼핑몰을 만들 건데 유저는 여러 개의 주문을 할 수 있고, 주문 안에는 여러 개의 상품이 담겨요.")
    if st.button("ERD 생성"):
        with st.spinner("AI가 ERD를 설계 중입니다..."):
            try:
                erd_result = llm_chain.generate_erd(req_input)
                st.session_state.erd_code = erd_result
                st.success("ERD 생성 완료!")
            except Exception as e:
                st.error(f"ERD 생성 실패: {e}")
    
    if st.session_state.erd_code:
        st.subheader("생성된 ERD (Mermaid)")
        st_mermaid(st.session_state.erd_code, height=500)
        with st.expander("Mermaid 코드 보기"):
            st.code(st.session_state.erd_code, language='mermaid')

with tab2:
    st.header("SQL 자동 생성 및 실행")
    
    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("🗣️ 자연어로 질문하기")
        user_q = st.text_input("DB에 대해 궁금한 점을 자연어로 질문하세요.", placeholder="가입일이 가장 오래된 유저 5명의 이름과 이메일을 보여줘")
        if st.button("AI SQL 생성"):
            with st.spinner("AI가 쿼리를 작성 중입니다..."):
                try:
                    sql_result = llm_chain.generate_sql(user_q, st.session_state.db_url)
                    st.session_state.current_query = sql_result
                    st.success("SQL 쿼리가 생성되었습니다.")
                except Exception as e:
                    st.error(f"SQL 생성 실패: {e}")
                    
    with col2:
        st.subheader("📂 SQL 파일 불러오기 (MySQL Workbench 등)")
        uploaded_file = st.file_uploader(".sql 파일을 업로드하면 텍스트 에디터로 불러옵니다.", type=["sql"])
        if uploaded_file is not None:
            # 파일 읽기
            string_data = uploaded_file.getvalue().decode("utf-8")
            st.session_state.current_query = string_data
            st.success("파일 내용을 성공적으로 불러왔습니다.")
            
    st.markdown("---")
    # 생성되었거나 파일에서 불러온 쿼리를 편집할 수 있는 영역
    st.session_state.current_query = st.text_area("🚀 실행할 SQL 쿼리", value=st.session_state.current_query, height=150)
    
    if st.button("쿼리 실행", type="primary"):
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

with tab3:
    st.header("실행 계획(EXPLAIN) 최적화 분석")
    st.markdown("복잡한 쿼리나 대용량 조회용 쿼리가 DB 내부에서 어떻게 동작하는지 분석해드립니다.")
    
    opt_query = st.text_area("분석할 쿼리를 입력하세요.", value=st.session_state.current_query, height=100, key="explain_input")
    
    if st.button("실행 계획 분석 및 AI 멘토링"):
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
                            
                            # 응답 텍스트에 mermaid 코드가 포함되어 있을 경우 렌더링 시도
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
