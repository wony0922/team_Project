import pandas as pd
import os
import re
import tempfile
from pathlib import Path
from sqlalchemy import MetaData, Table, create_engine, inspect, text

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

def replace_local_database_from_bytes(db_bytes: bytes):
    """업로드한 SQLite DB 파일로 로컬 실습 DB를 교체"""
    if not db_bytes:
        raise ValueError("업로드된 DB 파일이 비어 있습니다.")

    LOCAL_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
        tmp.write(db_bytes)
        tmp_path = Path(tmp.name)

    try:
        test_engine = create_engine(f"sqlite:///{tmp_path.as_posix()}")
        inspector = inspect(test_engine)
        _ = inspector.get_table_names()
        test_engine.dispose()
        os.replace(tmp_path, LOCAL_DB_PATH)
    except Exception as exc:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception:
            pass
        raise RuntimeError(f"SQLite DB 파일로 확인되지 않았습니다: {exc}") from exc

def export_local_database_copy(output_path=None):
    """현재 로컬 DB를 지정 경로로 복사해서 저장"""
    if not LOCAL_DB_PATH.exists():
        raise FileNotFoundError("저장할 로컬 DB 파일이 없습니다.")

    if output_path is None:
        output_path = BASE_DIR / "exports" / "local_study_backup.db"

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(LOCAL_DB_PATH.read_bytes())
    return output_path

def get_engine(db_url=None):
    """지정된 URL에 대한 SQLAlchemy 엔진 반환"""
    if not db_url:
        db_url = DEFAULT_SQLITE_URL
    return create_engine(db_url)

def is_safe_query(query: str) -> bool:
    """SQL 작업실은 사용자가 확인 후 실행하므로 빈 쿼리만 차단합니다."""
    return bool(normalize_sql_query(query))

def normalize_sql_query(query: str) -> str:
    """AI 응답/업로드 내용에서 실행할 SQL 한 문장을 추출"""
    if not query:
        return ""

    cleaned = query.strip()
    fenced = re.search(r"```(?:sql)?\s*(.*?)```", cleaned, re.DOTALL | re.IGNORECASE)
    if fenced:
        cleaned = fenced.group(1).strip()
    cleaned = cleaned.replace("```", "").strip()

    statements = [statement.strip() for statement in cleaned.split(";") if statement.strip()]
    if statements:
        cleaned = statements[0]

    return cleaned.rstrip(";").strip()

def execute_query(query: str, db_url=None):
    """SQL을 실행하고 결과 DataFrame과 에러(있을 경우)를 반환"""
    query = normalize_sql_query(query)
    if not is_safe_query(query):
        return None, "실행할 SQL 문을 입력해 주세요."

    engine = get_engine(db_url)
    try:
        with engine.begin() as conn:
            result = conn.execute(text(query))
            if result.returns_rows:
                rows = result.fetchall()
                df = pd.DataFrame(rows, columns=result.keys())
            else:
                df = pd.DataFrame(
                    [
                        {
                            "status": "실행 완료",
                            "affected_rows": result.rowcount if result.rowcount is not None else "unknown",
                        }
                    ]
                )
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

def build_mermaid_erd_from_schema(db_url=None) -> str:
    """실제 DB 스키마를 기반으로 Mermaid ERD를 생성"""
    engine = get_engine(db_url)
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    if not tables:
        raise ValueError("ERD를 생성할 테이블이 없습니다.")

    lines = ["erDiagram"]

    for table in tables:
        columns = inspector.get_columns(table)
        pk_constraint = inspector.get_pk_constraint(table)
        pks = set(pk_constraint.get("constrained_columns", []) or [])
        fks = inspector.get_foreign_keys(table)
        fk_columns = {
            col
            for fk in fks
            for col in fk.get("constrained_columns", [])
        }

        lines.append(f"    {table} {{")
        for col in columns:
            col_name = col["name"]
            col_type = _mermaid_type_name(str(col["type"]))
            attrs = []
            if col_name in pks:
                attrs.append("PK")
            if col_name in fk_columns:
                attrs.append("FK")
            attr_text = f' "{", ".join(attrs)}"' if attrs else ""
            lines.append(f"        {col_type} {col_name}{attr_text}")
        lines.append("    }")

    seen_relations = set()
    for table in tables:
        fks = inspector.get_foreign_keys(table)
        for fk in fks:
            referred_table = fk.get("referred_table")
            constrained_columns = fk.get("constrained_columns", [])
            referred_columns = fk.get("referred_columns", [])
            if not referred_table or not constrained_columns or not referred_columns:
                continue
            relation_key = (referred_table, table, tuple(constrained_columns), tuple(referred_columns))
            if relation_key in seen_relations:
                continue
            seen_relations.add(relation_key)
            label = ", ".join(constrained_columns)
            lines.append(f'    {referred_table} ||--o{{ {table} : "{label}"')

    return "\n".join(lines)

def _mermaid_type_name(type_name: str) -> str:
    """Mermaid ERD에서 쓸 수 있도록 타입명을 단순화"""
    clean = re.sub(r"\(.*?\)", "", type_name).strip().upper()
    if not clean:
        return "TEXT"
    if "INT" in clean:
        return "INT"
    if any(token in clean for token in ["CHAR", "TEXT", "CLOB", "VARCHAR"]):
        return "VARCHAR"
    if any(token in clean for token in ["DATE", "TIME"]):
        return "DATETIME" if "TIME" in clean else "DATE"
    if any(token in clean for token in ["DECIMAL", "NUMERIC", "FLOAT", "DOUBLE", "REAL"]):
        return "DECIMAL"
    return clean.split()[0]

def get_insertion_context(db_url=None, sample_limit=3) -> str:
    """LLM이 데이터 삽입 대상을 고를 수 있도록 스키마와 샘플을 함께 반환"""
    engine = get_engine(db_url)
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    if not tables:
        raise ValueError("데이터베이스에 테이블이 없습니다.")

    parts = []
    with engine.connect() as conn:
        for table in tables:
            columns = inspector.get_columns(table)
            fks = inspector.get_foreign_keys(table)
            pk_constraint = inspector.get_pk_constraint(table)
            pks = pk_constraint.get('constrained_columns', []) if pk_constraint else []

            parts.append(f"Table: {table}")
            parts.append("  Columns:")
            for col in columns:
                col_name = col['name']
                col_type = str(col['type'])
                flags = []
                if col_name in pks:
                    flags.append("PK")
                for fk in fks:
                    if col_name in fk.get('constrained_columns', []):
                        flags.append(f"FK->{fk['referred_table']}.{fk['referred_columns'][0]}")
                flag_text = f" [{' '.join(flags)}]" if flags else ""
                parts.append(f"    - {col_name} ({col_type}){flag_text}")

            try:
                result = conn.execute(text(f"SELECT * FROM `{table}` LIMIT {int(sample_limit)}"))
                rows = result.fetchall()
                if rows:
                    parts.append("  Sample Rows:")
                    keys = result.keys()
                    for idx, row in enumerate(rows, start=1):
                        row_dict = dict(zip(keys, row))
                        parts.append(f"    - row{idx}: {row_dict}")
                else:
                    parts.append("  Sample Rows: none")
            except Exception as exc:
                parts.append(f"  Sample Rows: error ({exc})")
            parts.append("")

    return "\n".join(parts)

def insert_rows(db_url, table_name, rows):
    """지정한 테이블에 여러 행을 삽입"""
    if not rows:
        return 0

    engine = get_engine(db_url)
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    if table_name not in tables:
        raise ValueError(f"테이블 '{table_name}' 이(가) 존재하지 않습니다.")

    metadata = MetaData()
    table = Table(table_name, metadata, autoload_with=engine)
    column_info = {col["name"]: col for col in inspector.get_columns(table_name)}
    pk_columns = set(inspector.get_pk_constraint(table_name).get("constrained_columns", []) or [])

    normalized_rows = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        clean_row = {}
        for key, value in row.items():
            col_info = column_info.get(key)
            if not col_info or value is None:
                continue
            col_type = str(col_info["type"]).upper()
            if col_info.get("autoincrement") or (key in pk_columns and "INT" in col_type):
                continue
            if key in column_info:
                clean_row[key] = value
        if clean_row:
            normalized_rows.append(clean_row)

    if not normalized_rows:
        raise ValueError("삽입할 유효한 데이터가 없습니다.")

    with engine.begin() as conn:
        conn.execute(table.insert(), normalized_rows)

    return len(normalized_rows)

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

def _is_identifier_column(col_name: str) -> bool:
    """id 또는 *_id 형태의 식별자 컬럼인지 판별"""
    return bool(re.fullmatch(r"id|.+_id", col_name.lower()))

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

    existing_next_int = {}
    with engine.connect() as conn:
        for col in columns:
            col_name = col['name']
            col_type = str(col['type']).upper()
            is_int_like = 'INT' in col_type or 'NUMERIC' in col_type
            is_id_like = _is_identifier_column(col_name)
            if is_int_like and is_id_like:
                try:
                    result = conn.execute(text(f"SELECT COALESCE(MAX(`{col_name}`), 0) FROM `{table_name}`"))
                    existing_next_int[col_name] = (result.scalar() or 0) + 1
                except Exception:
                    existing_next_int[col_name] = 1
            
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
            is_int_type = any(token in col_type for token in ['INT', 'DECIMAL', 'NUMERIC', 'FLOAT', 'DOUBLE'])
            is_id_like = _is_identifier_column(col_name)
            
            # Auto-increment 컬럼 건너뛰기
            if col.get('autoincrement') or (col_name in pks and 'INT' in col_type and col_name not in fk_map):
                continue
                
            # 외래키 처리
            if col_name in fk_map:
                vals = fk_values.get(col_name, [])
                if vals:
                    row_data[col_name] = random.choice(vals)
                else:
                    row_data[col_name] = existing_next_int.get(col_name, 1)
                    existing_next_int[col_name] = row_data[col_name] + 1
                continue

            # 식별자 컬럼은 텍스트 대신 정수형 순번으로 채움
            if is_id_like:
                row_data[col_name] = existing_next_int.get(col_name, 1)
                existing_next_int[col_name] = row_data[col_name] + 1
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

