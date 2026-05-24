"""Reproduce the /drivers?year=2024 error locally."""
import sys
from pathlib import Path
backend_dir = Path(__file__).parent.resolve()
parent_dir = backend_dir.parent.resolve()
sys.path = [str(backend_dir)] + [p for p in sys.path if Path(p).resolve() != parent_dir]

from sqlalchemy.orm import Session as DBSession
from app.database import SessionLocal
from app.models.sql import Driver, DriverSeason, Constructor

db = SessionLocal()
try:
    rows = (
        db.query(Driver, DriverSeason, Constructor)
        .outerjoin(DriverSeason, (
            DriverSeason.driver_code == Driver.code,
        ))
        .outerjoin(Constructor, Constructor.id == DriverSeason.constructor_id)
        .filter(DriverSeason.season_year == 2024)
        .order_by(Driver.full_name)
        .all()
    )
    print(f"Got {len(rows)} rows")
    for driver, ds, constructor in rows:
        print(f"  {driver.code}: {driver.full_name} -> {constructor.name if constructor else 'NO TEAM'}")
except Exception as e:
    import traceback
    traceback.print_exc()
finally:
    db.close()
