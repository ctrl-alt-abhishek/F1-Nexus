# F1 Degradation App — Code Audit

## 🔴 Critical Issues

### 1. `.env` committed to repo
The `.env` file is inside the archive — meaning it's tracked by git. This exposes `DATABASE_URL`, `FIREBASE_*` credentials, and API keys.

**Fix:** Add `.env` to `.gitignore` immediately. Rotate all exposed secrets.

---

### 2. No input validation on `year`/`round` path params
**Files:** `races.py`, `drivers.py`

`year` and `round` are accepted as integers directly and interpolated into FastF1 calls without range checks. FastF1 will throw unhandled exceptions for nonsense values (e.g. `year=1800`).

**Fix:**
```python
from fastapi import Path
year: int = Path(..., ge=2018, le=2030)
round_number: int = Path(..., ge=1, le=24)
```

---

### 3. Bare `except Exception` swallowing errors silently
**File:** `live_timing.py`

Multiple WebSocket handler loops use `except Exception: pass` or just log and continue, meaning connection corruption goes undetected.

**Fix:** At minimum log with `logger.exception(...)` to capture tracebacks.

---

### 4. No rate limiting on `/chat` endpoint
**File:** `chat.py`

Calls an LLM API on every POST with no throttling per user. A single authenticated user can drain API quota.

**Fix:** Add `slowapi` limiter:
```python
@limiter.limit("10/minute")
```

---

## 🟠 Data Flow Robustness

### 5. No cache invalidation strategy
**File:** `fastf1_loader.py`

`fastf1.Cache.enable_cache(...)` is called globally. If the cache directory fills or contains stale/corrupt Parquet files, all endpoints silently return bad data or crash. No TTL is set.

**Fix:** Wrap cache-read paths in try/except and add a cache size cap config option.

---

### 6. `session.load()` called without timeout
**File:** `fastf1_loader.py`

FastF1 HTTP calls have no timeout. On a slow network, the entire FastAPI worker thread blocks indefinitely (FastF1 is synchronous and runs via `asyncio.to_thread` — correct — but no timeout is set).

**Fix:**
```python
await asyncio.wait_for(asyncio.to_thread(session.load, ...), timeout=60)
```

---

### 7. `NoneType` attribute access on FastF1 DataFrames
**Files:** `races.py`, `predictions.py`

Several routes do `laps["LapTime"].dt.total_seconds()` or similar without checking if the column exists or if the session returned data. Crashes with `KeyError` or `AttributeError` on incomplete sessions.

**Fix:**
```python
if laps is None or laps.empty or "LapTime" not in laps.columns:
    raise HTTPException(status_code=404, detail="No lap data available")
```

---

### 8. No connection pool tuning for NeonDB
**File:** `database.py`

Using SQLAlchemy defaults (`pool_size=5`, no `pool_pre_ping`). NeonDB (serverless Postgres) aggressively closes idle connections. Without `pool_pre_ping=True`, you'll get `psycopg2.OperationalError: SSL connection has been closed unexpectedly` on cold requests.

**Fix:**
```python
engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_recycle=300,  # recycle before NeonDB's ~5min idle timeout
)
```

---

## 🟡 FastF1 Compliance

### 9. Deprecated `session.load()` kwarg
**File:** `fastf1_loader.py`

`session.load(weather=True, messages=True)` — in FastF1 3.x, `messages` was renamed to `track_status`. Passing `messages=True` silently does nothing.

**Fix:**
```python
session.load(weather=True, track_status=True)
```

---

### 10. `pick_driver()` deprecated in FastF1 3.3+
FastF1 3.3 deprecated `pick_driver()` in favour of `pick_drivers()` (plural). Still works but will become an error in a future version.

**Fix:** Replace `laps.pick_driver(code)` → `laps.pick_drivers(code)`

---

### 11. Missing `include_testing=False` on schedule fetch
When `fastf1.get_event_schedule()` is called without `include_testing=False`, pre-season testing rounds appear in race lists and cause downstream failures (no lap data).

**Fix:** Always pass `include_testing=False`.

---

## 🟡 NeonDB / SQLAlchemy Compliance

### 12. Sync engine in `alembic/env.py` for async app
**File:** `alembic/env.py`

The alembic env uses `create_engine` (sync) while the app uses `create_async_engine`. Fine for migration tooling, but the connection string must not use `postgresql+asyncpg://` for alembic — ensure `env.py` uses a separate sync URL or `postgresql://`.

---

### 13. f-string SQL injection in `seed_data.py`
**File:** `scripts/seed_data.py`

Uses `conn.execute(text("INSERT INTO ..."))` with f-string interpolation — direct SQL injection risk in a script that runs with admin credentials.

**Fix:** Use parameterized queries:
```python
conn.execute(text("INSERT INTO ... VALUES (:val)"), {"val": x})
```

---

## 🔵 Code Quality

### 14. Non-reproducible Monte Carlo simulations
**File:** `monte_carlo.py`

No `np.random.seed()` or `rng = np.random.default_rng(seed)`. Results are non-reproducible across runs.

**Fix:** Accept optional `seed: int = None` param:
```python
rng = np.random.default_rng(seed)
```

---

### 15. Manual `os.getenv()` instead of `pydantic-settings`
**File:** `config.py`

`os.getenv("X", default)` is used everywhere manually. The project already has `pydantic` — use `pydantic-settings` `BaseSettings` for typed, validated config with automatic `.env` loading.

---

### 16. CORS `allow_origins=["*"]` too permissive
**File:** `main.py`

Allows any origin. If `allow_credentials=True` is ever added, this becomes a security hole. Restrict to your frontend domain now before it becomes a problem.

---

### 17. `live_timing.py` is a 48KB monolith
Handles WebSocket management, data parsing, lap interpolation, and broadcasting in one file. Hard to maintain and test.

**Suggested split:**
- `ws_manager.py` — connection lifecycle
- `timing_parser.py` — raw data parsing
- `broadcaster.py` — fan-out logic

---

## Summary

| # | Severity | File | Issue |
|---|----------|------|-------|
| 1 | 🔴 Critical | `.env` | Committed to repo — rotate secrets |
| 2 | 🔴 Critical | `races.py`, `drivers.py` | No path param range validation |
| 3 | 🔴 Critical | `live_timing.py` | Silent exception swallowing |
| 4 | 🔴 Critical | `chat.py` | No rate limiting on LLM calls |
| 5 | 🟠 High | `fastf1_loader.py` | No cache TTL/corruption handling |
| 6 | 🟠 High | `fastf1_loader.py` | No timeout on `session.load()` |
| 7 | 🟠 High | `races.py`, `predictions.py` | No null checks on FastF1 DataFrames |
| 8 | 🟠 High | `database.py` | Missing `pool_pre_ping` for NeonDB |
| 9 | 🟡 Medium | `fastf1_loader.py` | `messages=` kwarg deprecated → `track_status=` |
| 10 | 🟡 Medium | any using `pick_driver()` | Use `pick_drivers()` |
| 11 | 🟡 Medium | schedule fetching | Missing `include_testing=False` |
| 12 | 🟡 Medium | `alembic/env.py` | Sync vs async engine mismatch risk |
| 13 | 🟡 Medium | `seed_data.py` | f-string SQL injection in `text()` |
| 14 | 🔵 Low | `monte_carlo.py` | Non-reproducible simulations |
| 15 | 🔵 Low | `config.py` | Use `pydantic-settings` |
| 16 | 🔵 Low | `main.py` | CORS `*` too permissive |
| 17 | 🔵 Low | `live_timing.py` | 48KB monolith, needs splitting |
