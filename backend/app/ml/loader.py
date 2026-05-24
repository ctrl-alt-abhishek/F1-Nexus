"""
app/ml/loader.py - Startup-time model artifact loader.

Loads all trained .joblib files once at startup and holds them in memory.
All API endpoints import model instances from here instead of calling
joblib.load() per-request (which would add 200-500ms cold latency each time).

If a model file is missing the attribute stays None — endpoints that depend
on it must check for None and return 503 Service Unavailable.
"""

import json
import logging
from pathlib import Path

import joblib

from app.config import settings

logger = logging.getLogger(__name__)


class ModelStore:
    """
    In-memory store for all trained model artifacts.

    Attributes:
        degradation:       XGBRegressor — tyre lap time predictor (RMSE 1.29s)
        strategy:          XGBClassifier — pit stop probability classifier
        style_cluster_map: dict[driver_code -> cluster_id]  (None if not trained)
        style_pca_coords:  dict[driver_code -> [pc1, pc2]]  (None if not trained)
        style_kmeans:      fitted KMeans object              (None if not trained)
        style_scaler:      fitted StandardScaler             (None if not trained)
        style_pca:         fitted PCA                        (None if not trained)
    """

    def __init__(self):
        self.degradation = None
        self.strategy = None
        self.style_cluster_map: dict | None = None
        self.style_pca_coords: dict | None = None
        self.style_kmeans = None
        self.style_scaler = None
        self.style_pca = None

    def load(self) -> None:
        """
        Load all model artifacts from settings.MODELS_DIR.
        Called once during FastAPI lifespan startup.
        Non-fatal — missing files log warnings but don't crash the server.
        """
        models_dir = Path(settings.MODELS_DIR)

        # ── Degradation model (required for race analysis + pit window) ─────────
        self._load_joblib("degradation", models_dir / "degradation.joblib", required=True)

        # ── Strategy model (required for pit window) ─────────────────────────────
        self._load_joblib("strategy", models_dir / "strategy.joblib", required=True)

        # ── Driver style (optional — trained separately with telemetry) ───────────
        self._load_style(models_dir)

    def _load_joblib(self, attr: str, path: Path, required: bool = False) -> None:
        """Load a single joblib artifact into self.<attr>."""
        if path.exists():
            setattr(self, attr, joblib.load(path))
            logger.info("✓ Loaded %s model from %s", attr, path)
        else:
            level = logger.warning if required else logger.info
            level("✗ %s model not found at %s", attr, path)

    def _load_style(self, models_dir: Path) -> None:
        """
        Load driver style cluster artifacts.
        These are optional — only exist if train_all.py was run without --skip-style.
        Style data is stored as:
          - style_kmeans.joblib, style_scaler.joblib, style_pca.joblib
          - style_cluster_map.json  (cluster_map + pca_coords)
        """
        cluster_map_path = models_dir / "style_cluster_map.json"

        if not cluster_map_path.exists():
            logger.info(
                "Driver style model not trained — run: "
                "poetry run python scripts/train_all.py --model style"
            )
            return

        try:
            with open(cluster_map_path) as f:
                meta = json.load(f)
            self.style_cluster_map = meta.get("cluster_map", {})
            self.style_pca_coords = meta.get("pca_coords", {})

            self._load_joblib("style_kmeans", models_dir / "style_kmeans.joblib")
            self._load_joblib("style_scaler", models_dir / "style_scaler.joblib")
            self._load_joblib("style_pca", models_dir / "style_pca.joblib")

            logger.info(
                "✓ Loaded driver style model (%d drivers)", len(self.style_cluster_map)
            )
        except Exception as exc:
            logger.warning("Could not load driver style model: %s", exc)

    @property
    def style_available(self) -> bool:
        """True if the style cluster model has been trained and loaded."""
        return self.style_cluster_map is not None


# Singleton — import this everywhere.
# Usage:  from app.ml.loader import models
models = ModelStore()
