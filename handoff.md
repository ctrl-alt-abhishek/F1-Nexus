# F1 Nexus — Handoff Document
_Last updated: 2026-05-12_

---

## Goal

Build the **F1 Nexus** platform — a full-stack F1 analytics web app powered by a 100% free-tier stack:

| Layer | Service |
|---|---|
| Database | Neon.tech (PostgreSQL 16, 0.5 GB free) |
| Backend API | FastAPI on Render (free tier) |
| Auth | Firebase Auth + Firestore |
| ML | XGBoost models served via API |
| Frontend | Next.js / React (not started yet) |
| Keep-alive | GitHub Actions cron (every 13 min) |

The 5-week plan: **Week 1** = infra + DB schema. **Week 2** = ML models. **Week 3** = API endpoints. **Week 4** = Frontend. **Week 5** = Deploy + polish.

---

## Current State

**Week 2 complete.** Infrastructure, database, data seeding, and ML training are all done.

### ✅ Done

| Area | Status |
|---|---|
| Poetry project scaffold (`backend/`) | ✅ |
| Pydantic settings (`config.py`) | ✅ |
| SQLAlchemy ORM — 11 tables | ✅ |
| Alembic migrations — applied to Neon | ✅ |
| FastAPI app (`main.py`) with `/health` endpoint | ✅ |
| Firebase Admin SDK integration | ✅ |
| Auth routers (`/auth/sync`, `/users/me`) | ✅ |
| FastF1 loader + data cleaning pipeline | ✅ |
| **Database seeded: 2022 + 2023 + 2024** | ✅ 47,606 clean laps |
| **Degradation model trained** | ✅ RMSE=1.29s, R²=0.983 |
| **Strategy model trained** | ✅ ROC-AUC=0.686 |
| `models/degradation.joblib` | ✅ |
| `models/strategy.joblib` | ✅ |
| `models/metrics.json` | ✅ |

### ⏳ Not Started Yet

| Area | Week |
|---|---|
| Driver style model (KMeans + PCA, needs telemetry) | Week 2 |
| API route implementations (predictions, races, drivers) | Week 3 |
| LLM RAG chat (`/chat`) | Week 3 |
| Live timing worker (`LiveTimingWorker`) | Week 3 |
| Web Push notifications (VAPID) | Week 3 |
| Frontend (Next.js) | Week 4 |
| Render deploy + GitHub Actions | Week 5 |

---

## Database State

**Neon project:** `f1nexus` | **Branch:** `production` | **Size:** ~15 MB / 500 MB

| Year | Rounds | Laps |
|---|---|---|
| 2024 | 24/24 | 22,700 |
| 2023 | 22/22 | 20,047 |
| 2022 | ~5 rounds | ~4,859 |

> **Note:** 2022 was seeded but the internet dropped mid-run. Total is ~47,606 laps. Re-running `seed_data.py --year 2022` is safe (idempotent).

---

## Trained Model Metrics

| Model | RMSE | MAE | R² | ROC-AUC |
|---|---|---|---|---|
| Degradation (XGBRegressor) | **1.287s** | 0.960s | **0.983** | — |
| Strategy (XGBClassifier) | — | — | — | 0.686 |

**Degradation top features:** `round_enc` (0.364) → `lap_number` (0.162) → `track_temp_proxy` (0.160) → `fuel_proxy` (0.158)

---

## Files In Flight / Key Files

### Backend scaffold
```
backend/
├── .env                          ← All credentials (Neon, Firebase, Groq)
├── pyproject.toml                ← Poetry deps
├── alembic.ini                   ← Alembic config (points to .env DATABASE_URL)
├── alembic/versions/             ← Two migrations applied
│   ├── f7355e36e42f_initial_schema.py
│   └── 67aa6d1f8081_fix_ml_models_columns.py
├── app/
│   ├── config.py                 ← Pydantic settings (reads .env)
│   ├── database.py               ← SQLAlchemy engine + NullPool script engine
│   ├── firebase.py               ← Firebase Admin SDK init + auth dependency
│   ├── main.py                   ← FastAPI app, lifespan, CORS, router mounts
│   ├── models/
│   │   ├── sql.py                ← 11 ORM models
│   │   └── schemas.py            ← Pydantic response schemas
│   ├── routers/
│   │   ├── auth.py               ← POST /auth/sync
│   │   ├── users.py              ← GET/PUT /users/me, POST /users/push-subscription
│   │   ├── chat.py               ← stub only
│   │   ├── drivers.py            ← stub only
│   │   ├── live.py               ← stub only
│   │   ├── predictions.py        ← stub only
│   │   └── races.py              ← stub only
│   ├── ml/
│   │   ├── degradation/
│   │   │   ├── features.py       ← ✅ FIXED (round_enc + per-round fuel_proxy)
│   │   │   ├── train.py          ← XGBRegressor training
│   │   │   └── predict.py        ← inference + curve generation
│   │   ├── strategy/
│   │   │   ├── features.py       ← binary pit label, forward-looking deg signal
│   │   │   ├── train.py          ← XGBClassifier, scale_pos_weight
│   │   │   └── predict.py        ← pit window recommendation (5-lap lookahead)
│   │   ├── driver_style/
│   │   │   ├── features.py       ← telemetry corner analysis (NOT YET TRAINED)
│   │   │   └── cluster.py        ← KMeans + PCA (NOT YET TRAINED)
│   │   └── season_prediction/
│   │       └── monte_carlo.py    ← 10k Monte Carlo simulator (no training needed)
│   └── services/
│       └── fastf1_loader.py      ← FastF1 fetch + clean + seed_round_to_db()
├── scripts/
│   ├── seed_data.py              ← ✅ FIXED (NullPool, retry logic, --start-round)
│   └── train_all.py              ← ✅ FIXED (correct column names, graceful DB write)
├── models/                       ← Trained artifacts
│   ├── degradation.joblib        ← ✅ TRAINED
│   ├── strategy.joblib           ← ✅ TRAINED
│   └── metrics.json              ← training metrics log
└── check_tables.py               ← utility script to check DB state
```

---

## What Was Changed (vs. original repo)

The original repo was a Streamlit prototype (`app.py`, `model/`, `features/`). Everything below is new:

| File | Change |
|---|---|
| `backend/` | Entire directory — new Poetry monorepo |
| `backend/app/models/sql.py` | 11 SQLAlchemy ORM tables (circuits, drivers, laps, rounds, seasons, race_results, qualifying, constructors, driver_season, championship_standings, ml_models) |
| `backend/app/ml/degradation/features.py` | **Rewrote twice.** V2 adds `round_enc` (circuit identifier) and fixes `fuel_proxy` to be per-round. Dropped RMSE from 8.6s → 1.29s. |
| `backend/app/database.py` | Added TCP keepalives, `connect_timeout=10`, and `create_script_engine()` (NullPool) |
| `backend/scripts/seed_data.py` | Fixed exception handling (moved try/except outside context manager), added NullPool per-round connections, retry logic with backoff |
| `backend/.env` | `FASTF1_CACHE_DIR=../cache` (reuses existing cache from Streamlit prototype) |
| `backend/alembic/versions/67aa6d1f8081_fix_ml_models_columns.py` | Manually wrote ALTER TABLE statements after Alembic autogenerate produced an empty `pass` migration |

---

## Failed Attempts / Bugs Encountered

### 1. `PendingRollbackError` crashing seed mid-season
**What:** Internet dropped mid-transaction → Neon closed TCP → SQLAlchemy tried to `commit()` on dead connection → `PendingRollbackError` propagated and crashed the entire script.

**Why:** The `try/except` in `seed_season()` was *inside* the `with get_db_context()` block, so the context manager saw a clean exit and attempted `commit()` on a broken session.

**Fix:** Moved `try/except` *outside* the context manager. Each round now gets a fresh `NullPool` connection. Added 3-retry backoff for transient connection errors.

---

### 2. Neon hanging indefinitely (no connect timeout)
**What:** After 8+ days of inactivity, Neon's free tier went fully cold. Python hung with no output for 5+ minutes.

**Fix:** Added `connect_timeout=10` and TCP keepalives (`keepalives_idle=30`) to psycopg2 `connect_args`. Dead connections now detected within ~45s.

---

### 3. RMSE=8.6s (terrible degradation model)
**What:** Two bugs in `features.py`:
- `total_laps = df["LapNumber"].max()` was a **global** max across all circuits. Monaco (78 laps) and Monza (57 laps) were computed against the same denominator → `fuel_proxy` was wrong for every race.
- No circuit identifier → the model had no way to distinguish a 75s Monaco lap from a 108s Spa lap. `fuel_proxy` and `track_temp_proxy` both got 0 feature importance.

**Fix:** Per-round `fuel_proxy` via `groupby("Year", "RoundNumber")`. Added `round_enc` feature (label-encodes `Year*100 + RoundNumber`). RMSE dropped from 8.6s → 1.29s, R²=0.983.

---

### 4. Alembic autogenerate produced empty migration
**What:** `alembic revision --autogenerate` generated `upgrade() -> None: pass` for `ml_models` because the table already existed (just with missing columns). Alembic doesn't detect column-level drift when the table was originally created with fewer columns.

**Fix:** Manually wrote `ALTER TABLE ml_models ADD COLUMN IF NOT EXISTS ...` in the migration file.

---

### 5. `sys.path` collision with old Streamlit `app.py`
**What:** Running scripts from `backend/` caused Python to find `d:\ML Project\f1_degradation_app\app.py` (the old Streamlit prototype) when importing `app.database`, because `sys.path.insert(0, parent_dir)` added the project root before `backend/`.

**Fix:** Replaced `sys.path.insert(0, ...)` with `sys.path = [str(backend_dir)] + [p for p in sys.path if "f1_degradation_app" not in p]` in all scripts.

---

## Next Steps (Week 3)

### Immediate (resume here)
1. **Verify `train_all.py` runs clean end-to-end** (the `name` column fix should eliminate the last warning)
2. **Start the API server locally:**
   ```powershell
   cd backend
   poetry run uvicorn app.main:app --reload
   ```
3. **Test `/health` endpoint:** `curl http://localhost:8000/health`

### Week 3 — API Implementation
Implement the stub routers with real logic. Dependency order:

| Router | File | Depends On |
|---|---|---|
| `GET /races/{year}` | `routers/races.py` | Neon `rounds` table |
| `GET /drivers/{year}` | `routers/drivers.py` | Neon `driver_season` table |
| `GET /predictions/degradation` | `routers/predictions.py` | `degradation.joblib` |
| `GET /predictions/strategy` | `routers/predictions.py` | `strategy.joblib` |
| `GET /predictions/championship` | `routers/predictions.py` | `monte_carlo.py` |
| `POST /chat` | `routers/chat.py` | Groq API + RAG |
| `WebSocket /live` | `routers/live.py` | `LiveTimingWorker` |

### Week 3 — LLM RAG Chat
Create `app/services/llm_client.py` — provider-agnostic wrapper switching between Groq / Gemini / Anthropic via `LLM_PROVIDER` env var. Then implement `/chat` endpoint with FastF1 context injection.

### Optional (can defer)
- Driver style model: run `scripts/train_all.py --model style` (slow — loads qualifying telemetry for 9 sessions, ~20-40 min)
- Seed more 2022 data: `scripts/seed_data.py --year 2022 --start-round 6`

---

## Credentials & Services

| Service | Status | Notes |
|---|---|---|
| Neon.tech | ✅ Active | `ep-patient-heart-amcphnkt.c-5.us-east-1.aws.neon.tech` |
| Firebase | ✅ Active | Project: `f1-nexus-8b023` |
| Groq API | ✅ Key in `.env` | Model: `llama-3.1-70b-versatile` |
| Render | ❌ Not deployed yet | Week 5 |
| GitHub Actions keep-alive | ❌ Not active yet | `backend/.github/workflows/keep-alive.yml` exists |

> **IMPORTANT:** The `.env` file contains all credentials and is gitignored. Never commit it.
