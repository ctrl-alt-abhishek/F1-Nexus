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
1. Always filter is_valid = TRUE on the laps table unless the user explicitly asks for all laps or queries safety cars, Virtual Safety Cars (VSC), red flags, or pit stops (these non-green-flag/outlier laps have is_valid = FALSE in the database).
2. driver_code is a 3-letter uppercase code (e.g. 'VER', 'NOR', 'LEC').
3. compound values: 'SOFT', 'MEDIUM', 'HARD', 'INTERMEDIATE', 'WET'.
4. lap_time_s is in seconds as a float (e.g. 90.234).
5. Limit to 100 rows unless the user asks for more.
6. Return ONLY the SQL query — no explanation, no markdown fences, no comments.
7. NEVER use DELETE, UPDATE, INSERT, DROP, ALTER, TRUNCATE, or any DDL/DML.
8. Use meaningful column aliases (e.g. AVG(lap_time_s) AS avg_lap_time_s).
9. When asking about a specific driver by name (e.g. "Verstappen"), use ILIKE on full_name (e.g. d.full_name ILIKE '%Verstappen%').
10. ALWAYS filter by circuit/location when specified in the question using ILIKE on BOTH circuits.name AND circuits.city using OR. Example: `(c.name ILIKE '%Silverstone%' OR c.city ILIKE '%Silverstone%')`. This is CRITICAL because the name is often "British Grand Prix" while the city is "Silverstone".
11. When filtering by constructor/team, join laps or results to driver_season and constructors.
12. For queries comparing "tyre degradation", "degradation curves", or "pace vs tyre life":
    - If specific drivers are mentioned or implied, select and group by l.driver_code.
    - If NO specific drivers are mentioned, DO NOT select or group by l.driver_code.
13. CRITICAL: When the question compares different circuits, years, drivers, or tyre compounds, you MUST select the comparison columns in the SELECT clause.
14. ALWAYS parenthesize OR conditions properly in the WHERE clause.
15. When comparing circuits, drivers, or teams without a specified season year in the question, default to filtering by the most recent complete season (e.g. `AND r.season_year = 2024`).
16. track_status is a string of digit characters representing track conditions. The codes are: '1' = Green flag, '2' = Yellow flag, '4' = Safety Car (SC), '5' = Virtual Safety Car (VSC), '6' = Red flag. To query safety car periods, laps under safety car, or count safety cars, you MUST check if track_status contains '4' or '5'.
17. CRITICAL: Every column in the SELECT clause that is not an aggregate function MUST be included in the GROUP BY clause. Never select a column and fail to group by it.
18. When asked for "consistency", "most consistent", or similar, use STDDEV (standard deviation) on lap_time_s or qualifying times (e.g., `STDDEV(q.q1_s)`) and order ascending. Do NOT use SUM or AVG for consistency.
20. The `race_results`, `qualifying`, and `laps` tables DO NOT have a `season_year` column. You MUST join the `rounds` table (e.g., `JOIN rounds r ON laps.round_id = r.id`) to filter by `season_year`.
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
