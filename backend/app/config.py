"""
app/config.py - Environment variable loading via pydantic-settings.

All environment variables are defined here. Import `settings` in any module
that needs a config value - never read os.environ directly.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── Database ────────────────────────────────────────────────────────────
    # Neon.tech PostgreSQL connection string. Must include ?sslmode=require.
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/f1nexus"

    # ── Firebase ────────────────────────────────────────────────────────────
    FIREBASE_PROJECT_ID: str = ""
    FIREBASE_PRIVATE_KEY: str = ""
    FIREBASE_CLIENT_EMAIL: str = ""

    # ── LLM provider ────────────────────────────────────────────────────────
    # Options: groq | gemini | anthropic
    # Swap provider by changing this env var - zero code changes needed.
    LLM_PROVIDER: str = "groq"

    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"

    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"

    # ── Telegram ────────────────────────────────────────────────────────────
    TELEGRAM_BOT_TOKEN: str = ""

    # ── Web Push (VAPID) ────────────────────────────────────────────────────
    # Generate once with: python -m py_vapid --applicationServerKey
    # Never regenerate after first deployment - existing subscriptions will break.
    VAPID_PRIVATE_KEY: str = ""
    VAPID_PUBLIC_KEY: str = ""
    VAPID_CLAIMS_EMAIL: str = ""

    # ── FastF1 cache ────────────────────────────────────────────────────────
    FASTF1_CACHE_DIR: str = "./cache"

    # ── ML model artifacts ───────────────────────────────────────────────────
    # Directory where trained .joblib files are saved and loaded from.
    MODELS_DIR: str = "./models"

    # ── Live Timing Simulation ──────────────────────────────────────────────
    SIMULATE_LIVE_TIMING: bool = False

    # ── App settings ────────────────────────────────────────────────────────
    # CORS origin for the Next.js frontend
    FRONTEND_ORIGIN: str = "http://localhost:3000"


# Singleton instance - import this everywhere
settings = Settings()
