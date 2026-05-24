"""
app/ml/chat_rag/responder.py - Full RAG answer pipeline.

Orchestrates the two-step RAG flow:
  1. retriever.generate_sql()        → SQL string
  2. retriever.execute_safe_query()  → list[dict] results
  3. Format results as compact JSON  (capped at 2000 chars to fit LLM context)
  4. llm_client.chat_completion()    → natural language answer

answer_question() is the single public entry point — called by routers/chat.py.
"""

import json
import logging

from sqlalchemy.orm import Session

from app.ml.chat_rag import retriever
from app.ml.chat_rag.llm_client import chat_completion

logger = logging.getLogger(__name__)

# ── Answer system prompt ──────────────────────────────────────────────────────

ANSWER_SYSTEM_PROMPT = """
You are an expert F1 data analyst. Answer the user's question using only the
provided query results. Follow these guidelines:

- Be concise and direct — 2-4 sentences max unless the question requires more detail
- Format lap times as M:SS.mmm (e.g. 1:23.456) when presenting them
- Format sector times as SS.mmm (e.g. 29.123)
- Round percentages and probabilities to 1 decimal place
- If the results are empty, say so directly: "No data found for that query."
- If there is an error key in the data, explain it simply to the user
- NEVER invent data that isn't in the results
- NEVER reference the SQL query or database schema in your answer
""".strip()

MAX_DATA_CHARS = 2000  # Cap data JSON to fit within LLM context window


# ── Public API ────────────────────────────────────────────────────────────────

def answer_question(user_question: str, db: Session) -> dict:
    """
    Full RAG pipeline: question → SQL → data → natural language answer.

    Args:
        user_question: The user's natural language question about F1 data.
        db:            Active SQLAlchemy session for query execution.

    Returns:
        {
            'answer':    str   — natural language answer from LLM,
            'sql':       str   — generated SQL query,
            'row_count': int   — number of rows retrieved,
            'data':      list  — raw query results (up to 100 rows),
        }
    """
    # Step 1: Generate SQL from question
    try:
        sql = retriever.generate_sql(user_question)
    except Exception as exc:
        logger.error("SQL generation failed: %s", exc)
        return {
            "answer": f"Sorry, I couldn't generate a query for that question: {exc}",
            "sql": "",
            "row_count": 0,
            "data": [],
        }

    # Step 2: Execute the SQL safely
    data = retriever.execute_safe_query(sql, db)

    # Step 3: Format data as compact JSON for the LLM context
    data_json = _format_data(data)
    row_count = len(data)

    # Step 4: Generate the natural language answer
    context_message = f"Question: {user_question}\n\nQuery results ({row_count} rows):\n{data_json}"

    try:
        answer = chat_completion(
            system_prompt=ANSWER_SYSTEM_PROMPT,
            user_message=context_message,
            max_tokens=600,
            temperature=0.2,  # Slightly creative for fluent prose, but grounded
        )
    except Exception as exc:
        logger.error("LLM answer generation failed: %s", exc)
        answer = (
            f"I retrieved {row_count} rows but couldn't generate a response. "
            f"Error: {exc}"
        )

    return {
        "answer": answer,
        "sql": sql,
        "row_count": row_count,
        "data": data,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _format_data(data: list[dict]) -> str:
    """
    Serialize query results to compact JSON, capped at MAX_DATA_CHARS.

    If the full data exceeds the cap, truncates to as many rows as fit
    and appends a note so the LLM knows data was cut.
    """
    if not data:
        return "[]"

    # Check for error case
    if len(data) == 1 and "error" in data[0]:
        return json.dumps(data, indent=None)

    # Try full serialization first
    try:
        full = json.dumps(data, default=str)
        if len(full) <= MAX_DATA_CHARS:
            return full
    except Exception:
        pass

    # Truncate row by row until we fit
    for n_rows in range(len(data) - 1, 0, -1):
        truncated = data[:n_rows]
        try:
            body = json.dumps(truncated, default=str)
        except Exception:
            continue
        note = f' ... ({len(data) - n_rows} more rows truncated)'
        combined = body[:-1] + note + "]"  # Append note inside array brackets
        if len(combined) <= MAX_DATA_CHARS:
            return combined

    # Fallback: just the first row
    return json.dumps(data[:1], default=str)
