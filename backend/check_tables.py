import sys
import os
from pathlib import Path

# Ensure ONLY backend/ is on the path - never the project root (which has old app.py)
backend_dir = Path(__file__).parent.resolve()
parent_dir = backend_dir.parent.resolve()
sys.path = [str(backend_dir)] + [p for p in sys.path if Path(p).resolve() != parent_dir]

from sqlalchemy import text
from app.database import create_script_engine
from sqlalchemy.orm import sessionmaker

engine = create_script_engine()
Session = sessionmaker(bind=engine)

with Session() as db:
    rows = db.execute(text("""
        SELECT r.season_year, r.round_number, r.name,
               COUNT(l.id) AS laps
        FROM rounds r
        LEFT JOIN laps l ON l.round_id = r.id
        GROUP BY r.season_year, r.round_number, r.name
        ORDER BY r.season_year DESC, r.round_number
    """)).fetchall()

    total_laps = db.execute(text("SELECT COUNT(*) FROM laps")).scalar()
    size = db.execute(text("SELECT pg_size_pretty(pg_database_size(current_database()))")).scalar()

print(f"DB size: {size}   Total laps: {total_laps:,}\n")
by_year = {}
for year, rnd, name, laps in rows:
    by_year.setdefault(year, []).append((rnd, name or "?", laps))

for year in sorted(by_year.keys(), reverse=True):
    rounds = by_year[year]
    year_laps = sum(r[2] for r in rounds)
    print(f"=== {year}  ({len(rounds)} rounds, {year_laps:,} laps) ===")
    for rnd, name, laps in rounds:
        flag = "  <- EMPTY" if laps == 0 else ""
        print(f"  R{rnd:02d}  {name:<40} {laps:>5} laps{flag}")
    print()
