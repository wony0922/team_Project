import pandas as pd
import os
import re
from sqlalchemy import create_engine, text

DEFAULT_SQLITE_URL = 'sqlite:///local_study.db'

def initialize_database():
    """초기 샘플 데이터베이스 생성 (SQLite 전용)"""
    if not os.path.exists('local_study.db'):
        engine = create_engine(DEFAULT_SQLITE_URL)
        try:
            with open('sample_data.sql', 'r', encoding='utf-8') as f:
                sql_script = f.read()
            with engine.begin() as conn:
                for statement in sql_script.split(';'):
                    if statement.strip():
                        conn.execute(text(statement))
            print("데이터베이스 초기화 완료.")
        except Exception as e:
            print(f"데이터베이스 초기화 에러: {e}")

def get_engine(db_url=None):
    """지정된 URL에 대한 SQLAlchemy 엔진 반환"""
    if not db_url:
        db_url = DEFAULT_SQLITE_URL
    return create_engine(db_url)

def is_safe_query(query: str) -> bool:
    """파괴적인 쿼리를 차단하는 간단한 검사 로직"""
    query_upper = query.upper()
    dangerous_keywords = ['DROP', 'DELETE', 'TRUNCATE', 'ALTER', 'UPDATE', 'INSERT']
    for keyword in dangerous_keywords:
        if re.search(r'\b' + keyword + r'\b', query_upper):
            return False
    return True

def execute_query(query: str, db_url=None):
    """쿼리를 실행하고 결과를 DataFrame과 에러(있을 경우)로 반환"""
    if not is_safe_query(query):
        return None, "보안 경고: 데이터를 변경하거나 삭제하는 쿼리는 실행할 수 없습니다. (SELECT 문만 허용됨)"

    engine = get_engine(db_url)
    try:
        # SQLAlchemy connection을 사용하여 pandas에서 직접 쿼리 실행
        with engine.connect() as conn:
            df = pd.read_sql_query(text(query), conn)
        return df, None
    except Exception as e:
        return None, str(e)

def get_schema_info(db_url=None) -> str:
    """데이터베이스의 스키마 정보를 반환"""
    engine = get_engine(db_url)
    try:
        with engine.connect() as conn:
            if "sqlite" in str(engine.url):
                # SQLite 스키마 조회
                result = conn.execute(text("SELECT sql FROM sqlite_master WHERE type='table';"))
                schema = "\n".join([row[0] for row in result if row[0] is not None])
            else:
                # MySQL 스키마 조회 (SHOW CREATE TABLE 활용)
                result = conn.execute(text("SHOW TABLES"))
                tables = [row[0] for row in result]
                schema_parts = []
                for table in tables:
                    create_stmt = conn.execute(text(f"SHOW CREATE TABLE `{table}`"))
                    schema_parts.append(create_stmt.fetchone()[1])
                schema = "\n\n".join(schema_parts)
            return schema
    except Exception as e:
        return f"스키마 조회 에러: {e}"

def execute_explain_plan(query: str, db_url=None) -> str:
    """EXPLAIN 실행 계획 결과를 텍스트로 반환"""
    engine = get_engine(db_url)
    try:
        with engine.connect() as conn:
            explain_prefix = "EXPLAIN " if "mysql" in str(engine.url) else "EXPLAIN QUERY PLAN "
            result = conn.execute(text(f"{explain_prefix}{query}"))
            
            # 결과를 보기 좋게 포맷팅
            explain_text = []
            keys = result.keys()
            for row in result:
                row_dict = dict(zip(keys, row))
                explain_text.append(str(row_dict))
            return "\n".join(explain_text)
    except Exception as e:
        return f"실행 계획 분석 중 에러 발생: {e}"
