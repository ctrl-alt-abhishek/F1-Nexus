"""
scripts/train_all.py - Train all F1 Nexus ML models from the seeded Neon database.

Trains in order (degradation first, strategy uses it as a feature):
  1. Degradation model  (XGBRegressor) ~2-5 min
  2. Strategy model     (XGBClassifier) ~3-8 min
  3. Driver Style       (KMeans + PCA)  -- skipped with --skip-style (requires telemetry)

Season prediction (Monte Carlo) is pure statistics - no training artifact needed.

All artifacts saved to backend/models/ as .joblib files.
Metrics logged to terminal and written to backend/models/metrics.json.

Usage:
  poetry run python scripts/train_all.py                       # train all
  poetry run python scripts/train_all.py --skip-style          # skip slow telemetry step
  poetry run python scripts/train_all.py --year 2024           # single year only
  poetry run python scripts/train_all.py --model degradation   # single model
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Ensure ONLY backend/ is on path - not the project root (which has old Streamlit app.py)
backend_dir = Path(__file__).parent.parent.resolve()
parent_dir = backend_dir.parent.resolve()
sys.path = [str(backend_dir)] + [p for p in sys.path if Path(p).resolve() != parent_dir]

import fastf1
import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import create_script_engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).parent.parent / "models"
MODELS_DIR.mkdir(exist_ok=True)

# NullPool engine for scripts
_engine = create_script_engine()
_Session = sessionmaker(bind=_engine)


def get_db():
    db = _Session()
    try:
        yield db
    finally:
        db.close()


def load_laps_from_db(years: list[int]) -> pd.DataFrame:
    """Load cleaned laps from Neon, formatted to match feature engineering expectations."""
    year_list = ", ".join(str(y) for y in years)
    query = text(f"""
        SELECT
            l.lap_time_s        AS "lap_time_s",
            l.lap_number        AS "LapNumber",
            l.compound          AS "Compound",
            l.tyre_life         AS "TyreLife",
            l.stint             AS "Stint",
            l.position          AS "Position",
            l.track_status      AS "TrackStatus",
            l.driver_code       AS "Driver",
            r.round_number      AS "RoundNumber",
            r.season_year       AS "Year"
        FROM laps l
        JOIN rounds r ON r.id = l.round_id
        WHERE r.season_year IN ({year_list})
          AND l.is_valid = TRUE
          AND l.lap_time_s IS NOT NULL
          AND l.tyre_life IS NOT NULL
          AND l.compound IS NOT NULL
          AND l.compound != 'UNKNOWN'
    """)
    with _Session() as db:
        result = db.execute(query)
        df = pd.DataFrame(result.fetchall(), columns=result.keys())
    logger.info("Loaded %d laps from Neon (years: %s)", len(df), years)
    return df


# ── 1. Degradation ────────────────────────────────────────────────────────────

def train_degradation(laps_df: pd.DataFrame) -> dict:
    from app.ml.degradation.features import build_features
    from app.ml.degradation.train import train_model, save_model

    logger.info("Building degradation features...")
    X, y = build_features(laps_df)
    logger.info("Feature matrix: %d rows x %d cols", len(X), len(X.columns))

    logger.info("Training XGBoost degradation model...")
    t0 = time.time()
    result = train_model(X, y)
    elapsed = time.time() - t0

    path = str(MODELS_DIR / "degradation.joblib")
    save_model(result["model"], path)

    logger.info(
        "Degradation: RMSE=%.3fs  MAE=%.3fs  R2=%.3f  [%.0fs]",
        result["rmse"], result["mae"], result["r2"], elapsed,
    )
    logger.info("Top features:\n%s", result["feature_importance"].head(7).to_string())

    return {
        "model_type": "degradation",
        "rmse": result["rmse"],
        "mae": result["mae"],
        "r2": result["r2"],
        "rows": len(X),
        "artifact_path": path,
        "trained_at": datetime.now(timezone.utc).isoformat(),
    }


# ── 2. Strategy ───────────────────────────────────────────────────────────────

def train_strategy(laps_df: pd.DataFrame, deg_model) -> dict:
    from app.ml.strategy.features import build_strategy_features
    from app.ml.strategy.train import train_model, save_model

    logger.info("Building strategy features...")
    X, y = build_strategy_features(laps_df, deg_model=deg_model)
    pit_count = int(y.sum())
    logger.info("Strategy matrix: %d rows  (pit laps: %d, ratio: %.1f%%)",
                len(X), pit_count, 100 * pit_count / max(len(X), 1))

    logger.info("Training XGBoost strategy classifier...")
    t0 = time.time()
    result = train_model(X, y)
    elapsed = time.time() - t0

    path = str(MODELS_DIR / "strategy.joblib")
    save_model(result["model"], path)

    logger.info(
        "Strategy: ROC-AUC=%.3f  F1=%.3f  Precision=%.3f  Recall=%.3f  [%.0fs]",
        result["roc_auc"], result["f1"], result["precision"], result["recall"], elapsed,
    )

    return {
        "model_type": "strategy",
        "roc_auc": result["roc_auc"],
        "f1": result["f1"],
        "precision": result["precision"],
        "recall": result["recall"],
        "rows": len(X),
        "artifact_path": path,
        "trained_at": datetime.now(timezone.utc).isoformat(),
    }


# ── 3. Driver style ───────────────────────────────────────────────────────────

def train_driver_style(years: list[int]) -> dict | None:
    from app.ml.driver_style.features import build_style_matrix
    from app.ml.driver_style.cluster import train_style_clusters, save_cluster_model, CLUSTER_LABELS

    fastf1.Cache.enable_cache(settings.FASTF1_CACHE_DIR)

    sessions_to_analyze = []
    all_drivers = set()
    sample_rounds = [5, 12, 18]

    logger.info("Loading qualifying telemetry (slow - 2-5 min per session)...")
    for year in years:
        for rnd in sample_rounds:
            try:
                session = fastf1.get_session(year, rnd, "Q")
                try:
                    session.load(laps=True, telemetry=True, weather=False, track_status=False)
                except Exception as e:
                    logger.warning("  Failed loading %d R%d Q with cache, trying without cache: %s", year, rnd, e)
                    with fastf1.Cache.disabled():
                        session.load(laps=True, telemetry=True, weather=False, track_status=False)
                sessions_to_analyze.append(session)
                drivers = [str(d)[:3] for d in session.drivers]
                all_drivers.update(drivers)
                logger.info("  Loaded %d R%d Q (%d drivers)", year, rnd, len(drivers))
            except Exception as e:
                logger.warning("  Could not load %d R%d Q: %s", year, rnd, e)

    if not sessions_to_analyze:
        logger.warning("No sessions loaded. Skipping driver style.")
        return None

    driver_codes = list(all_drivers)
    logger.info("Extracting style features for %d drivers...", len(driver_codes))
    style_matrix = build_style_matrix(sessions_to_analyze, driver_codes)

    if style_matrix.empty or len(style_matrix) < 4:
        logger.warning("Not enough drivers (%d). Skipping.", len(style_matrix))
        return None

    logger.info("Clustering %d drivers...", len(style_matrix))
    result = train_style_clusters(style_matrix)
    save_cluster_model(result, str(MODELS_DIR))
    style_matrix.to_parquet(str(MODELS_DIR / "style_matrix.parquet"))

    logger.info("Driver style clusters:")
    for driver, cid in sorted(result["cluster_map"].items()):
        logger.info("  %-4s -> %s", driver, CLUSTER_LABELS.get(cid, cid))

    return {
        "model_type": "driver_style",
        "n_drivers": len(style_matrix),
        "inertia": result["inertia"],
        "artifact_path": str(MODELS_DIR),
        "trained_at": datetime.now(timezone.utc).isoformat(),
    }


# ── Metrics save ─────────────────────────────────────────────────────────────

def save_metrics(metrics_list: list[dict]) -> None:
    path = MODELS_DIR / "metrics.json"
    with open(path, "w") as f:
        json.dump(metrics_list, f, indent=2)
    logger.info("Metrics saved to %s", path)

    # Log to Neon ml_models table (non-critical - .joblib files are the real output)
    try:
        with _Session() as db:
            for m in metrics_list:
                if not m:
                    continue
                db.execute(text("""
                    INSERT INTO ml_models (name, model_type, version, trained_at, rmse, mae, artifact_path)
                    VALUES (:name, :mt, '1.0', :ta, :rmse, :mae, :ap)
                """), {
                    "name": m.get("model_type"),   # name = model_type (e.g. "degradation")
                    "mt": m.get("model_type"),
                    "ta": m.get("trained_at"),
                    "rmse": m.get("rmse"),
                    "mae": m.get("mae"),
                    "ap": m.get("artifact_path"),
                })
            db.commit()
        logger.info("ml_models table updated.")
    except Exception as e:
        logger.warning("Could not write to ml_models (schema needs migration): %s", e)
        logger.warning("Models are saved to disk - this is non-critical.")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, help="Train on single year only")
    parser.add_argument("--skip-style", action="store_true", help="Skip driver style (no telemetry)")
    parser.add_argument("--model", choices=["degradation", "strategy", "style"], help="Train single model")
    args = parser.parse_args()

    # Determine years
    if args.year:
        years = [args.year]
    else:
        with _Session() as db:
            result = db.execute(text("SELECT DISTINCT season_year FROM rounds ORDER BY season_year"))
            years = [row[0] for row in result.fetchall()]
    logger.info("Training years: %s  |  Models dir: %s", years, MODELS_DIR)

    laps_df = load_laps_from_db(years)
    if laps_df.empty:
        logger.error("No laps found. Run seed_data.py first.")
        sys.exit(1)

    all_metrics = []

    if args.model == "style":
        m = train_driver_style(years)
        if m:
            all_metrics.append(m)
        save_metrics(all_metrics)
        return

    # ── Step 1: Degradation ──────────────────────────────────────────────────
    if not args.model or args.model == "degradation":
        logger.info("\n%s\nSTEP 1/2: Degradation Model\n%s", "=" * 60, "=" * 60)
        deg_metrics = train_degradation(laps_df)
        all_metrics.append(deg_metrics)
    else:
        deg_metrics = None

    # Load trained degradation model for strategy features
    deg_model = None
    if deg_metrics:
        from app.ml.degradation.train import load_model
        deg_model = load_model(deg_metrics["artifact_path"])

    # ── Step 2: Strategy ─────────────────────────────────────────────────────
    if not args.model or args.model == "strategy":
        logger.info("\n%s\nSTEP 2/2: Strategy Model\n%s", "=" * 60, "=" * 60)
        strat_metrics = train_strategy(laps_df, deg_model)
        all_metrics.append(strat_metrics)

    # ── Step 3: Driver style (optional) ──────────────────────────────────────
    if not args.skip_style and not args.model:
        logger.info("\n%s\nSTEP 3/3: Driver Style (telemetry)\n%s", "=" * 60, "=" * 60)
        style_metrics = train_driver_style(years)
        if style_metrics:
            all_metrics.append(style_metrics)
    elif args.skip_style:
        logger.info("Skipping driver style (--skip-style)")

    save_metrics(all_metrics)

    logger.info("\n%s", "=" * 60)
    logger.info("ALL MODELS TRAINED. Artifacts in: %s", MODELS_DIR)
    logger.info("Next: poetry run uvicorn app.main:app --reload")


if __name__ == "__main__":
    main()
