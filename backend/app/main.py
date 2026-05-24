"""
app/main.py - FastAPI application entry point.

Startup sequence (via lifespan):
  1. init_cache()    - FastF1 local disk cache (mandatory before any session load)
  2. init_db()       - Create missing tables (Alembic handles migrations)
  3. init_firebase() - Firebase Admin SDK
  4. live_worker.start() - Background live timing worker (in-memory state)

All routers are mounted under /api/v1.
GET /health is unauthenticated and used by the GitHub Actions keep-alive cron.
"""

from contextlib import asynccontextmanager

import fastf1
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.firebase import init_firebase


# ── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────────

    # 1. FastF1 cache - MUST be called before any session load.
    #    Without this every API call re-downloads raw timing data (~50MB/race).
    fastf1.Cache.enable_cache(settings.FASTF1_CACHE_DIR)

    # 2. Database - create tables that don't exist yet.
    #    Alembic handles schema migrations; this is a safety net for fresh installs.
    init_db()

    # 3. Firebase Admin SDK - token verification + Firestore access.
    #    Only initializes if credentials are configured (skipped in local dev without Firebase).
    if settings.FIREBASE_PROJECT_ID:
        init_firebase()

    # 4. Live timing worker (imported here to avoid circular imports at module load)
    from app.services.live_timing import live_worker
    await live_worker.start()

    # 5. ML model artifacts - load .joblib files once into memory at startup.
    #    Endpoints import `models` from app.ml.loader and use models.degradation etc.
    from app.ml.loader import models
    models.load()

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────────
    from app.services.live_timing import live_worker
    await live_worker.stop()


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="F1 Nexus API",
    description="Formula 1 intelligence platform — race data, ML predictions, and live timing.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# ── CORS ──────────────────────────────────────────────────────────────────────

# Allow the Next.js frontend to make cross-origin requests.
# In production, FRONTEND_ORIGIN should be the Vercel deployment URL.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN, "http://localhost:3001", "http://localhost:3002"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────

from app.routers import auth, races, drivers, predictions, live, chat, users

app.include_router(auth.router, prefix="/api/v1")
app.include_router(races.router, prefix="/api/v1")
app.include_router(drivers.router, prefix="/api/v1")
app.include_router(predictions.router, prefix="/api/v1")
app.include_router(live.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")

# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/health", tags=["health"])
async def health_check():
    """
    Unauthenticated health endpoint.
    Used by GitHub Actions keep-alive cron to prevent Render cold starts.
    Must return 200 in under 100ms - no DB queries, no external calls.
    """
    return {"status": "ok"}
