import os
import json
import shutil

from langchain_community.llms import Ollama
from langchain_core.prompts import PromptTemplate

from db_utils import build_mermaid_erd_from_schema, get_insertion_context, get_schema_info
import prompts


MODEL_NAME = os.environ.get("DB_BUDDY_MODEL", "qwen2.5-coder:7b")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL")
OLLAMA_AVAILABLE = os.environ.get("DB_BUDDY_OLLAMA_AVAILABLE", "1") == "1"

if OLLAMA_BASE_URL:
    llm = Ollama(model=MODEL_NAME, base_url=OLLAMA_BASE_URL)
else:
    llm = Ollama(model=MODEL_NAME)


def _friendly_ollama_error(exc: Exception) -> RuntimeError:
    message = str(exc)
    lowered = message.lower()

    if "status code 404" in lowered or "model is not found" in lowered:
        return RuntimeError(
            f"Ollama model '{MODEL_NAME}' was not found.\n"
            f"Start Ollama, then run:\n"
            f"  ollama pull {MODEL_NAME}\n"
            f"You can also change the model with DB_BUDDY_MODEL."
        )

    return RuntimeError(f"Ollama request failed: {exc}")


def _invoke(chain, payload):
    if not OLLAMA_AVAILABLE or shutil.which("ollama") is None:
        raise RuntimeError(
            "Ollama is not available on this machine. "
            "Install Ollama to use ERD/AI features."
        )
    try:
        return chain.invoke(payload)
    except Exception as exc:
        raise _friendly_ollama_error(exc) from exc


def generate_erd(user_requirements: str) -> str:
    """Generate an ERD (Mermaid) from user requirements."""
    prompt = PromptTemplate.from_template(prompts.ERD_SYSTEM_PROMPT + "\n\n[사용자 요구사항]\n{requirements}")
    chain = prompt | llm
    result = _invoke(chain, {"requirements": user_requirements})
    return _extract_mermaid(result)


def generate_sql(user_query: str, db_url: str = None) -> str:
    """Convert a natural-language request into an executable SQL statement."""
    if not user_query or not user_query.strip():
        raise ValueError("SQL로 바꿀 요청을 먼저 입력해 주세요.")

    schema = get_schema_info(db_url)
    if "오류" in schema or "error" in schema.lower():
        raise RuntimeError(f"데이터베이스 연결 또는 스키마 조회에 실패했습니다: {schema}")
    if not schema.strip():
        raise RuntimeError("현재 데이터베이스에 테이블 스키마가 없습니다. 먼저 테이블을 만들거나 올바른 DB에 연결해 주세요.")

    template = """당신은 데이터베이스 전문가입니다. 사용자의 자연어 요청을 실행 가능한 SQL 한 문장으로 변환하세요.
규칙:
- SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER 등 요청 의도에 맞는 SQL 문법을 사용할 수 있습니다.
- 반드시 아래 스키마에 존재하는 테이블과 컬럼을 우선 사용하세요.
- 스키마에 없는 테이블/컬럼을 임의로 만들지 마세요. 단, 사용자가 CREATE TABLE처럼 새 구조 생성을 명확히 요청하면 생성 SQL을 작성할 수 있습니다.
- 설명 문장 없이 반드시 ```sql ... ``` 형식으로 SQL 코드만 반환하세요.
- 여러 문장을 만들지 말고 가장 필요한 SQL 한 문장만 반환하세요.

[스키마 정보]
{schema}

[질문]
{query}
"""
    prompt = PromptTemplate.from_template(template)
    chain = prompt | llm
    result = _invoke(chain, {"schema": schema, "query": user_query})
    return _extract_sql(result)


def analyze_error(user_query: str, raw_error_message: str, db_url: str = None) -> str:
    """Analyze an error message."""
    schema = get_schema_info(db_url)
    prompt = PromptTemplate.from_template(prompts.ERROR_ANALYZER_PROMPT)
    chain = prompt | llm
    result = _invoke(
        chain,
        {
            "db_schema": schema,
            "user_query": user_query,
            "raw_error_message": raw_error_message,
        },
    )
    return result


def analyze_explain_plan(user_query: str, explain_result: str) -> str:
    """Analyze an EXPLAIN plan."""
    prompt = PromptTemplate.from_template(prompts.EXPLAIN_ANALYZER_PROMPT)
    chain = prompt | llm
    result = _invoke(
        chain,
        {
            "user_query": user_query,
            "explain_result": explain_result,
        },
    )
    return result


def generate_erd_from_schema(db_url: str = None) -> str:
    """Generate ERD (Mermaid) code from the actual database schema."""
    from db_utils import get_detailed_schema_summary

    schema_info = get_detailed_schema_summary(db_url)
    prompt = PromptTemplate.from_template(prompts.ERD_FROM_SCHEMA_PROMPT)
    chain = prompt | llm
    try:
        result = _invoke(chain, {"schema_info": schema_info})
        erd_code = _extract_mermaid(result)
        erd_code = _sanitize_mermaid_erd(erd_code)
        if not _looks_like_mermaid_erd(erd_code):
            raise RuntimeError("LLM ERD output was not valid Mermaid.")
        return erd_code
    except Exception:
        return build_mermaid_erd_from_schema(db_url)


def translate_sql(sql_query: str, db_url: str = None) -> str:
    """Translate SQL into a more detailed explanation."""
    from db_utils import get_detailed_schema_summary

    schema_info = get_detailed_schema_summary(db_url)
    prompt = PromptTemplate.from_template(prompts.SQL_TRANSLATOR_PROMPT)
    chain = prompt | llm
    result = _invoke(
        chain,
        {
            "schema_info": schema_info,
            "sql_query": sql_query,
        },
    )
    return result


def generate_db_documentation(db_url: str = None) -> str:
    """Generate detailed database documentation."""
    from db_utils import get_detailed_schema_summary

    schema_info = get_detailed_schema_summary(db_url)
    prompt = PromptTemplate.from_template(prompts.DB_DOCS_PROMPT)
    chain = prompt | llm
    result = _invoke(chain, {"schema_info": schema_info})
    return result


def assist_db_normalization(request: str, db_url: str = None) -> str:
    """Assist with database normalization and refactoring."""
    from db_utils import get_detailed_schema_summary

    schema_info = get_detailed_schema_summary(db_url)
    prompt = PromptTemplate.from_template(prompts.NORMALIZATION_PROMPT)
    chain = prompt | llm
    result = _invoke(
        chain,
        {
            "schema_info": schema_info,
            "request": request,
        },
    )
    return result


def plan_data_insertion(request: str, db_url: str = None) -> dict:
    """Analyze a natural-language request and return an insertion plan."""
    insertion_context = get_insertion_context(db_url)
    prompt = PromptTemplate.from_template(prompts.DATA_INSERTION_PROMPT)
    chain = prompt | llm
    result = _invoke(
        chain,
        {
            "insertion_context": insertion_context,
            "request": request,
        },
    )
    return _extract_json_object(result)


def _extract_mermaid(text: str) -> str:
    """Extract Mermaid code from an LLM response."""
    import re

    match = re.search(r"```mermaid(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()


def _sanitize_mermaid_erd(code: str) -> str:
    """Fix common Mermaid ERD formatting issues."""
    import re

    code = code.replace("{{", "{").replace("}}", "}")
    code = code.replace("o{{", "o{").replace("o}}", "o}")
    lines = code.split("\n")
    sanitized = []

    for line in lines:
        stripped = line.strip()

        if not stripped or stripped.startswith("%%"):
            continue

        if stripped.startswith("```"):
            continue

        line = re.sub(r"\b([A-Z]+)\(\d+(?:,\s*\d+)?\)", r"\1", line)
        line = re.sub(r"\b(PK|FK)\s*$", r'"\1"', line)
        line = re.sub(r"\b(PK)\s+(FK)\s*$", r'"\1, \2"', line)

        rel_match = re.match(r"^(\s*\S+\s+[\|}{o\-]+\s+\S+\s*:\s*)(.+)$", line)
        if rel_match:
            prefix = rel_match.group(1)
            label = rel_match.group(2).strip()
            if not (label.startswith('"') and label.endswith('"')):
                label = label.strip('"').strip("'")
                label = f'"{label}"'
            line = prefix + label

        sanitized.append(line)

    result = "\n".join(sanitized)
    if "erDiagram" not in result:
        result = "erDiagram\n" + result

    return result


def _looks_like_mermaid_erd(code: str) -> bool:
    """Check whether the ERD output has the expected Mermaid shape."""
    if not code or "erDiagram" not in code:
        return False
    if "{" not in code or "}" not in code:
        return False
    if "||--" not in code and "}o--" not in code and "o{" not in code:
        return False
    return True


def _extract_sql(text: str) -> str:
    """Extract SQL code from an LLM response."""
    import re

    match = re.search(r"```sql(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()

    cleaned = text.replace("`", "").strip()
    sql_match = re.search(
        r"((?:SELECT|WITH|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|TRUNCATE|REPLACE|MERGE|PRAGMA|SHOW|DESCRIBE|DESC)\b.*?)(?:;|$)",
        cleaned,
        re.DOTALL | re.IGNORECASE,
    )
    if sql_match:
        return sql_match.group(1).strip()
    return cleaned


def _extract_json_object(text: str) -> dict:
    """Extract a JSON object from an LLM response."""
    import re

    candidates = [
        text.strip(),
    ]

    fenced = re.search(r"```json(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fenced:
        candidates.insert(0, fenced.group(1).strip())

    last_error = None
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except Exception as exc:
            last_error = exc

    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except Exception as exc:
            last_error = exc

    raise RuntimeError(f"LLM 응답에서 JSON 계획을 읽지 못했습니다: {last_error}")
