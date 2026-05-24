import pandas as pd
import os
import re
from pathlib import Path
from sqlalchemy import create_engine, text

# [수정됨] 실행 위치가 루트/DB_Buddy 어디든 동일하게 DB_Buddy 폴더의 파일을 사용합니다.
BASE_DIR = Path(__file__).resolve().parent
LOCAL_DB_PATH = BASE_DIR / "local_study.db"
SAMPLE_DATA_PATH = BASE_DIR / "sample_data.sql"
DEFAULT_SQLITE_URL = f"sqlite:///{LOCAL_DB_PATH.as_posix()}"

def initialize_database():
    """초기 샘플 데이터베이스 생성 (SQLite 전용)"""
    if not LOCAL_DB_PATH.exists():
        engine = create_engine(DEFAULT_SQLITE_URL)
        try:
            # [수정됨] sample_data.sql 경로를 현재 작업 디렉터리가 아닌 파일 위치 기준으로 고정했습니다.
            with SAMPLE_DATA_PATH.open('r', encoding='utf-8') as f:
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

from sqlalchemy import inspect
from faker import Faker
import random

def get_detailed_schema_summary(db_url=None) -> str:
    """데이터베이스 스키마의 상세 정보를 텍스트로 요약해서 반환 (LLM 입력용)"""
    engine = get_engine(db_url)
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    if not tables:
        raise ValueError("데이터베이스에 생성된 테이블이 존재하지 않습니다. 테이블을 먼저 생성한 후 다시 시도해 주세요.")
        
    summary = []
    for table in tables:
        columns = inspector.get_columns(table)
        fks = inspector.get_foreign_keys(table)
        pk_constraint = inspector.get_pk_constraint(table)
        pks = pk_constraint.get('constrained_columns', []) if pk_constraint else []
        
        summary.append(f"Table: {table}")
        summary.append("  Columns:")
        for col in columns:
            col_name = col['name']
            col_type = str(col['type'])
            is_pk = " (PK)" if col_name in pks else ""
            nullable_str = "" if col.get('nullable', True) else " NOT NULL"
            default_val = col.get('default')
            default_str = f" DEFAULT {default_val}" if default_val is not None else ""
            summary.append(f"    - {col_name} ({col_type}){is_pk}{nullable_str}{default_str}")
        
        if fks:
            summary.append("  Foreign Keys:")
            for fk in fks:
                referred_table = fk['referred_table']
                for col, ref_col in zip(fk['constrained_columns'], fk['referred_columns']):
                    summary.append(f"    - {col} references {referred_table}({ref_col})")
        summary.append("")
    return "\n".join(summary)

def get_tables_in_topological_order(db_url=None):
    """외래키 의존성을 고려하여 테이블을 위상 정렬 순서로 반환"""
    engine = get_engine(db_url)
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    dependencies = {}
    for table in tables:
        fks = inspector.get_foreign_keys(table)
        referred_tables = {fk['referred_table'] for fk in fks if fk['referred_table'] != table}
        dependencies[table] = referred_tables
        
    ordered = []
    visited = set()
    
    def visit(table):
        if table in visited:
            return
        visited.add(table)
        for dep in dependencies.get(table, []):
            if dep in tables:
                visit(dep)
        ordered.append(table)
        
    for table in tables:
        visit(table)
        
    return ordered

def generate_dummy_data_for_table(db_url, table_name, num_rows=10):
    """지정한 테이블에 대한 더미 데이터 INSERT 쿼리문 및 매핑 파라미터 생성"""
    engine = get_engine(db_url)
    inspector = inspect(engine)
    columns = inspector.get_columns(table_name)
    fks = inspector.get_foreign_keys(table_name)
    pk_constraint = inspector.get_pk_constraint(table_name)
    pks = pk_constraint.get('constrained_columns', []) if pk_constraint else []
    
    fk_map = {}
    for fk in fks:
        for col, ref_col in zip(fk['constrained_columns'], fk['referred_columns']):
            fk_map[col] = (fk['referred_table'], ref_col)
            
    fake = Faker('ko_KR')
    
    # 외래키 참조 데이터 조회
    fk_values = {}
    with engine.connect() as conn:
        for col, (ref_table, ref_col) in fk_map.items():
            try:
                res = conn.execute(text(f"SELECT `{ref_col}` FROM `{ref_table}` LIMIT 100"))
                fk_values[col] = [row[0] for row in res]
            except Exception:
                fk_values[col] = []
                
    insert_queries = []
    for _ in range(num_rows):
        row_data = {}
        for col in columns:
            col_name = col['name']
            col_type = str(col['type']).upper()
            
            # Auto-increment 컬럼 건너뛰기
            if col.get('autoincrement') or (col_name in pks and 'INT' in col_type and col_name not in fk_map):
                continue
                
            # 외래키 처리
            if col_name in fk_map:
                vals = fk_values.get(col_name, [])
                if vals:
                    row_data[col_name] = random.choice(vals)
                else:
                    row_data[col_name] = random.randint(1, 10)
                continue
                
            # 컬럼 이름 및 타입 매칭 데이터 생성
            val = None
            col_name_lower = col_name.lower()
            
            if 'email' in col_name_lower:
                val = fake.unique.email() if col.get('unique') else fake.email()
            elif 'name' in col_name_lower:
                if 'product' in col_name_lower or 'goods' in col_name_lower:
                    val = random.choice(['노트북', '스마트폰', '무선 마우스', '기계식 키보드', '게이밍 헤드셋', '4K 모니터', '보조 배터리', 'C타입 케이블', '무선 충전기', 'USB 메모리'])
                else:
                    val = fake.name()
            elif 'phone' in col_name_lower or 'tel' in col_name_lower:
                val = fake.phone_number()
            elif 'address' in col_name_lower or 'addr' in col_name_lower:
                val = fake.address()
            elif 'date' in col_name_lower or 'time' in col_name_lower or 'created' in col_name_lower or 'updated' in col_name_lower:
                val = fake.date_time_this_decade().strftime('%Y-%m-%d %H:%M:%S')
            elif 'price' in col_name_lower or 'amount' in col_name_lower or 'money' in col_name_lower or 'cost' in col_name_lower:
                val = random.randint(10, 1000) * 100
            elif 'stock' in col_name_lower or 'quantity' in col_name_lower or 'qty' in col_name_lower or 'count' in col_name_lower:
                val = random.randint(1, 100)
            else:
                if 'INT' in col_type:
                    val = random.randint(1, 100)
                elif 'CHAR' in col_type or 'TEXT' in col_type:
                    val = fake.sentence(nb_words=3)
                elif 'DATE' in col_type or 'TIME' in col_type:
                    val = fake.date_time_this_decade().strftime('%Y-%m-%d %H:%M:%S')
                elif 'FLOAT' in col_type or 'DECIMAL' in col_type or 'NUMERIC' in col_type:
                    val = round(random.uniform(10.0, 1000.0), 2)
                else:
                    val = fake.word()
            row_data[col_name] = val
            
        cols_str = ", ".join([f"`{c}`" for c in row_data.keys()])
        vals_str = ", ".join([f":{c}" for c in row_data.keys()])
        query = f"INSERT INTO `{table_name}` ({cols_str}) VALUES ({vals_str})"
        insert_queries.append((query, row_data))
        
    return insert_queries

def insert_dummy_data(db_url, table_name, num_rows=10):
    """테이블에 더미 데이터를 대입"""
    engine = get_engine(db_url)
    queries = generate_dummy_data_for_table(db_url, table_name, num_rows)
    with engine.begin() as conn:
        for query_str, params in queries:
            conn.execute(text(query_str), params)

def clear_all_tables(db_url=None):
    """모든 테이블의 데이터를 지우고 시퀀스 초기화"""
    engine = get_engine(db_url)
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    is_sqlite = "sqlite" in str(engine.url)
    
    with engine.begin() as conn:
        if is_sqlite:
            conn.execute(text("PRAGMA foreign_keys = OFF;"))
            for table in tables:
                conn.execute(text(f"DELETE FROM `{table}`;"))
                try:
                    conn.execute(text(f"DELETE FROM sqlite_sequence WHERE name='{table}';"))
                except Exception:
                    pass
            conn.execute(text("PRAGMA foreign_keys = ON;"))
        else:
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
            for table in tables:
                conn.execute(text(f"TRUNCATE TABLE `{table}`;"))
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))

def reset_database_to_default():
    """SQLite 실습 DB의 모든 테이블을 드롭하고 초기 스키마 및 더미데이터로 복원"""
    db_url = DEFAULT_SQLITE_URL
    engine = get_engine(db_url)
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    with engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys = OFF;"))
        for table in tables:
            conn.execute(text(f"DROP TABLE IF EXISTS `{table}`;"))
        conn.execute(text("PRAGMA foreign_keys = ON;"))
        
    try:
        # [수정됨] 복원 시에도 sample_data.sql을 DB_Buddy 폴더 기준으로 읽습니다.
        with SAMPLE_DATA_PATH.open('r', encoding='utf-8') as f:
            sql_script = f.read()
        with engine.begin() as conn:
            for statement in sql_script.split(';'):
                if statement.strip():
                    conn.execute(text(statement))
    except Exception as e:
        raise RuntimeError(f"데이터베이스 재초기화 실패: {e}")

