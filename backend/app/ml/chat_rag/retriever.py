"""
app/ml/chat_rag/retriever.py - Natural language → SQL → results pipeline.

Two-step process:
  1. generate_sql()      - LLM converts user question to a PostgreSQL SELECT
  2. execute_safe_query() - Validates and executes the SQL, returns list of dicts

Security rules (spec §12 #6):
  - All queries use sqlalchemy.text() — never format user input into SQL strings
  - execute_safe_query() only accepts queries starting with SELECT
  - All exceptions caught and returned as {'error': message}
"""

import logging
import re

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ml.chat_rag.llm_client import chat_completion

logger = logging.getLogger(__name__)


# ── SQL system prompt ─────────────────────────────────────────────────────────

SQL_SYSTEM_PROMPT = """
You are a PostgreSQL expert. Convert the user's question about Formula 1 data
into a valid PostgreSQL SELECT query against the f1nexus database schema below.

Schema:
- laps(id, round_id, driver_code, lap_number, lap_time_s, sector1_s, sector2_s,
        sector3_s, compound, tyre_life, stint, is_valid, track_status, position)
- rounds(id, season_year, round_number, circuit_id, race_date, name)
- circuits(id, name, country, city, track_length_km, lap_record_s)
- drivers(code, full_name, nationality, dob)
- race_results(id, round_id, driver_code, finish_position, points, status, fastest_lap)
- qualifying(id, round_id, driver_code, q1_s, q2_s, q3_s, grid_position)
- championship_standings(id, season_year, after_round, driver_code, points, wins, position)
- constructors(id, name)
- driver_season(driver_code, season_year, constructor_id, car_number)
- ml_models(id, name, version, trained_at, artifact_path, metrics)

Rules:
1. Always filter is_valid = TRUE on the laps table unless the user explicitly asks for all laps
2. driver_code is a 3-letter uppercase code (e.g. 'VER', 'NOR', 'LEC')
3. compound values: 'SOFT', 'MEDIUM', 'HARD', 'INTERMEDIATE', 'WET'
4. lap_time_s is in seconds as a float (e.g. 90.234)
5. Limit to 100 rows unless the user asks for more
6. Return ONLY the SQL query — no explanation, no markdown fences, no comments
7. NEVER use DELETE, UPDATE, INSERT, DROP, ALTER, TRUNCATE, or any DDL/DML
8. Use meaningful column aliases (e.g. AVG(lap_time_s) AS avg_lap_time_s)
9. When asking about a specific driver by name (e.g. "Verstappen"), use ILIKE on full_name
""".strip()


# ── Public functions ──────────────────────────────────────────────────────────

def generate_sql(user_question: str) -> str:
    """
    Convert a natural language F1 question into a PostgreSQL SELECT query.

    Calls the configured LLM provider via llm_client.chat_completion().
    Returns the raw SQL string. Does NOT execute it — call execute_safe_query() for that.
    """
    logger.debug("Generating SQL for: %s", user_question)
    sql = chat_completion(
        system_prompt=SQL_SYSTEM_PROMPT,
        user_message=user_question,
        max_tokens=500,
        temperature=0.0,  # Always deterministic for SQL generation
    )
    # Strip any accidental markdown fences the LLM may add despite the prompt
    sql = _strip_markdown(sql).strip()
    logger.debug("Generated SQL: %s", sql)
    return sql


def execute_safe_query(sql: str, db: Session) -> list[dict]:
    """
    Validate and execute a SQL query against the database.

    Security:
        - Rejects any query not starting with SELECT (case-insensitive)
        - Uses sqlalchemy.text() — parameterized query, not string formatting
        - Catches all exceptions — returns {'error': message} instead of raising

    Returns:
        List of row dicts on success.
        [{'error': message}] on failure.
    """
    # Strip leading whitespace/newlines before checking
    cleaned = sql.strip()

    if not re.match(r"^\s*SELECT\b", cleaned, re.IGNORECASE):
        return [{"error": f"Rejected: query must start with SELECT, got: {cleaned[:80]}"}]

    try:
        result = db.execute(text(cleaned))
        columns = list(result.keys())
        rows = result.fetchall()
        return [dict(zip(columns, row)) for row in rows]
    except Exception as exc:
        logger.warning("SQL execution failed: %s | Query: %s", exc, cleaned[:200])
        return [{"error": str(exc)}]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _strip_markdown(text: str) -> str:
    """Remove ```sql ... ``` or ``` ... ``` fences the LLM sometimes adds."""
    # Remove opening fence with optional language tag
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text.strip())
    # Remove closing fence
    text = re.sub(r"\n?```$", "", text.strip())
    return text.strip()
