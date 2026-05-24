import os
import shutil

from langchain_community.llms import Ollama
from langchain_core.prompts import PromptTemplate

from db_utils import get_schema_info
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
    """Convert a user question into SQL."""
    schema = get_schema_info(db_url)
    if "오류" in schema or "error" in schema.lower():
        raise RuntimeError(f"데이터베이스 연결 또는 스키마 조회에 실패했습니다: {schema}")

    template = """당신은 데이터베이스 전문가입니다. 사용자의 질문에 답하는 유효한 SQL 쿼리를 작성하세요.
반드시 ```sql ... ``` 형식으로 SQL 코드만 반환하세요.

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
    result = _invoke(chain, {"schema_info": schema_info})
    erd_code = _extract_mermaid(result)
    erd_code = _sanitize_mermaid_erd(erd_code)
    return erd_code


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


def _extract_sql(text: str) -> str:
    """Extract SQL code from an LLM response."""
    import re

    match = re.search(r"```sql(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text.replace("`", "").strip()
