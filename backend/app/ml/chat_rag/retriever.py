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
1. Always filter is_valid = TRUE on the laps table unless the user explicitly asks for all laps.
2. driver_code is a 3-letter uppercase code (e.g. 'VER', 'NOR', 'LEC').
3. compound values: 'SOFT', 'MEDIUM', 'HARD', 'INTERMEDIATE', 'WET'.
4. lap_time_s is in seconds as a float (e.g. 90.234).
5. Limit to 100 rows unless the user asks for more.
6. Return ONLY the SQL query — no explanation, no markdown fences, no comments.
7. NEVER use DELETE, UPDATE, INSERT, DROP, ALTER, TRUNCATE, or any DDL/DML.
8. Use meaningful column aliases (e.g. AVG(lap_time_s) AS avg_lap_time_s).
9. When asking about a specific driver by name (e.g. "Verstappen"), use ILIKE on full_name (e.g. d.full_name ILIKE '%Verstappen%').
10. ALWAYS filter by circuit/location when specified in the question:
    - The circuits table contains the Grand Prix name in 'name' (e.g. 'British Grand Prix', 'Belgian Grand Prix', 'Monaco Grand Prix') and the track location in 'city' (e.g. 'Silverstone', 'Spa-Francorchamps', 'Monaco', 'Monza').
    - ALWAYS match circuit locations using ILIKE with wildcards on circuits.name OR circuits.city (e.g. to query "Spa" or "Spa-Francorchamps", use `(c.name ILIKE '%Belgian%' OR c.city ILIKE '%Spa%')`; to query "Silverstone", use `(c.name ILIKE '%British%' OR c.city ILIKE '%Silverstone%')`).
    - Use simple, unaccented search keywords with wildcards for locations with accents (e.g. use `%Paulo%` for São Paulo, `%Montr%` for Montréal, `%Monaco%` for Monaco, `%Jeddah%` for Jeddah) to avoid matching issues with accented characters.
11. When filtering by constructor/team (e.g. 'Ferrari', 'Red Bull', 'McLaren'), join laps or results to driver_season and constructors using the constructor_id and season_year (e.g. `JOIN driver_season ds ON ds.driver_code = l.driver_code AND ds.season_year = r.season_year JOIN constructors co ON ds.constructor_id = co.id WHERE co.name ILIKE '%Red Bull%'`).
12. For queries comparing "tyre degradation", "degradation curves", or "pace vs tyre life":
    - If specific drivers are mentioned or implied, select and group by l.driver_code (e.g. `SELECT c.name AS circuit_name, r.season_year, l.driver_code, l.compound, l.tyre_life, AVG(l.lap_time_s) AS avg_lap_time_s FROM laps l JOIN rounds r ON l.round_id = r.id JOIN circuits c ON r.circuit_id = c.id WHERE l.is_valid = TRUE AND l.tyre_life IS NOT NULL GROUP BY c.name, r.season_year, l.driver_code, l.compound, l.tyre_life ORDER BY c.name, r.season_year, l.driver_code, l.compound, l.tyre_life`).
    - If NO specific drivers are mentioned or implied (e.g. comparing circuits or compounds overall), DO NOT select or group by l.driver_code. Average the lap times across all drivers (i.e. omit driver_code from SELECT, GROUP BY, and ORDER BY) to keep the result set compact and avoid truncation (e.g. `SELECT c.name AS circuit_name, r.season_year, l.compound, l.tyre_life, AVG(l.lap_time_s) AS avg_lap_time_s FROM laps l JOIN rounds r ON l.round_id = r.id JOIN circuits c ON r.circuit_id = c.id WHERE l.is_valid = TRUE AND l.tyre_life IS NOT NULL GROUP BY c.name, r.season_year, l.compound, l.tyre_life ORDER BY c.name, r.season_year, l.compound, l.tyre_life`).
13. CRITICAL: When the question compares different circuits, years, drivers, or tyre compounds, you MUST select the comparison columns in the SELECT clause (e.g. select c.name, r.season_year, l.driver_code, l.compound) so the LLM can distinguish them. Never omit the compared entities from the query results.
14. ALWAYS parenthesize OR conditions properly in the WHERE clause. Specifically, if you are filtering for multiple optional items (like two different drivers or two different circuits) using OR, wrap the ENTIRE set of OR conditions in outer parentheses so they are grouped together under the AND filters (e.g. `WHERE l.is_valid = TRUE AND ((c.city = 'Spa' OR c.city = 'Monaco'))` rather than `WHERE l.is_valid = TRUE AND c.city = 'Spa' OR c.city = 'Monaco'`). When comparing multiple entities, use LIMIT 500 instead of 100 so that data for all compared entities is returned.
15. When comparing circuits, drivers, or teams without a specified season year in the question, default to filtering by the most recent complete season (e.g. `AND r.season_year = 2024`) to keep data size focused and prevent truncation.
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
