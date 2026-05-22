import os
from langchain_community.llms import Ollama
from langchain_core.prompts import PromptTemplate
from db_utils import get_schema_info
import prompts

# 기본 모델 설정 (사용자 요청에 따라 qwen2.5-coder:7b 사용)
MODEL_NAME = "qwen2.5-coder:7b"

# Ollama LLM 인스턴스
llm = Ollama(model=MODEL_NAME)

def generate_erd(user_requirements: str) -> str:
    """사용자의 요구사항을 받아 ERD(Mermaid)를 반환"""
    prompt = PromptTemplate.from_template(prompts.ERD_SYSTEM_PROMPT + "\n\n[사용자 요구사항]\n{requirements}")
    chain = prompt | llm
    result = chain.invoke({"requirements": user_requirements})
    
    # Mermaid 코드 블럭만 추출
    return _extract_mermaid(result)

def generate_sql(user_query: str, db_url: str = None) -> str:
    """사용자의 자연어 질문을 SQL로 변환"""
    # LangChain의 create_sql_query_chain 대신 직접 구현 (Ollama와의 호환성을 높이기 위함)
    schema = get_schema_info(db_url)
    if schema.startswith("스키마 조회 에러"):
        raise RuntimeError(f"데이터베이스 연결 또는 스키마 조회에 실패했습니다: {schema}")
    template = """너는 데이터베이스 전문가야. 사용자의 질문을 해결하는 단일 SQL 쿼리를 작성해줘. 
    반드시 ```sql 과 ``` 로 감싸서 SQL 코드만 반환해.
    
    [스키마 정보]
    {schema}
    
    [질문]
    {query}
    """
    prompt = PromptTemplate.from_template(template)
    chain = prompt | llm
    result = chain.invoke({"schema": schema, "query": user_query})
    
    # SQL 코드 블럭만 추출
    return _extract_sql(result)

def analyze_error(user_query: str, raw_error_message: str, db_url: str = None) -> str:
    """에러 메시지 분석"""
    schema = get_schema_info(db_url)
    prompt = PromptTemplate.from_template(prompts.ERROR_ANALYZER_PROMPT)
    chain = prompt | llm
    result = chain.invoke({
        "db_schema": schema,
        "user_query": user_query,
        "raw_error_message": raw_error_message
    })
    return result

def analyze_explain_plan(user_query: str, explain_result: str) -> str:
    """실행 계획 분석"""
    prompt = PromptTemplate.from_template(prompts.EXPLAIN_ANALYZER_PROMPT)
    chain = prompt | llm
    result = chain.invoke({
        "user_query": user_query,
        "explain_result": explain_result
    })
    return result

def generate_erd_from_schema(db_url: str = None) -> str:
    """데이터베이스 실제 스키마로부터 ERD(Mermaid) 코드 생성"""
    from db_utils import get_detailed_schema_summary
    schema_info = get_detailed_schema_summary(db_url)
    prompt = PromptTemplate.from_template(prompts.ERD_FROM_SCHEMA_PROMPT)
    chain = prompt | llm
    result = chain.invoke({"schema_info": schema_info})
    return _extract_mermaid(result)

def translate_sql(sql_query: str, db_url: str = None) -> str:
    """SQL 구문을 상세히 한글로 번역 및 해설"""
    from db_utils import get_detailed_schema_summary
    schema_info = get_detailed_schema_summary(db_url)
    prompt = PromptTemplate.from_template(prompts.SQL_TRANSLATOR_PROMPT)
    chain = prompt | llm
    result = chain.invoke({
        "schema_info": schema_info,
        "sql_query": sql_query
    })
    return result

def generate_db_documentation(db_url: str = None) -> str:
    """데이터베이스의 상세 스키마 정의 및 데이터 사전 생성"""
    from db_utils import get_detailed_schema_summary
    schema_info = get_detailed_schema_summary(db_url)
    prompt = PromptTemplate.from_template(prompts.DB_DOCS_PROMPT)
    chain = prompt | llm
    result = chain.invoke({"schema_info": schema_info})
    return result

def assist_db_normalization(request: str, db_url: str = None) -> str:
    """자연어 요구사항에 따라 데이터베이스 정규화 및 리팩토링 제안 수행"""
    from db_utils import get_detailed_schema_summary
    schema_info = get_detailed_schema_summary(db_url)
    prompt = PromptTemplate.from_template(prompts.NORMALIZATION_PROMPT)
    chain = prompt | llm
    result = chain.invoke({
        "schema_info": schema_info,
        "request": request
    })
    return result

def _extract_mermaid(text: str) -> str:
    """결과 문자열에서 mermaid 블럭만 추출"""
    import re
    match = re.search(r'```mermaid(.*?)```', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    # 블럭이 없으면 원본 그대로 반환
    return text.strip()

def _extract_sql(text: str) -> str:
    """결과 문자열에서 sql 블럭만 추출"""
    import re
    match = re.search(r'```sql(.*?)```', text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text.replace("`", "").strip()
