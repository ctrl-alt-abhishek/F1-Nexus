"""
app/ml/driver_style/cluster.py - KMeans clustering + PCA for driver style archetypes.

Identifies 4 driving style archetypes from the style feature matrix:
  0: Late Braker   - aggressive braking, high entry speed
  1: Smooth Tyres  - early braking, gentle corner entry
  2: High Downforce - high lateral G, slower corner speeds
  3: Balanced      - near-average on all metrics

PCA reduces the 8 style features to 2 components for radar chart visualization.
"""

import numpy as np
import pandas as pd
import joblib
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA


N_CLUSTERS = 4

CLUSTER_LABELS = {
    0: "Late Braker",
    1: "Smooth Operator",
    2: "High Cornering Load",
    3: "Balanced",
}


def train_style_clusters(style_matrix: pd.DataFrame) -> dict:
    """
    Fit KMeans + PCA on the driver style feature matrix.

    Args:
        style_matrix: DataFrame with driver_code as index and STYLE_FEATURE_COLS as columns.

    Returns:
        {
            'kmeans':         fitted KMeans,
            'scaler':         fitted StandardScaler,
            'pca':            fitted PCA (2 components),
            'cluster_map':    {driver_code: cluster_id},
            'pca_coords':     {driver_code: [pc1, pc2]},
            'inertia':        float,
        }
    """
    if style_matrix.empty or len(style_matrix) < N_CLUSTERS:
        raise ValueError(
            f"Need at least {N_CLUSTERS} drivers for clustering, got {len(style_matrix)}"
        )

    X = style_matrix.fillna(0.0)
    driver_codes = style_matrix.index.tolist()

    # ── Normalize ─────────────────────────────────────────────────────────────
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # ── KMeans clustering ─────────────────────────────────────────────────────
    kmeans = KMeans(
        n_clusters=N_CLUSTERS,
        random_state=42,
        n_init=20,   # multiple initialisations for stability
        max_iter=500,
    )
    cluster_labels = kmeans.fit_predict(X_scaled)
    cluster_map = {code: int(label) for code, label in zip(driver_codes, cluster_labels)}

    # ── PCA for 2D visualization ──────────────────────────────────────────────
    pca = PCA(n_components=2, random_state=42)
    X_pca = pca.fit_transform(X_scaled)
    pca_coords = {
        code: [float(coords[0]), float(coords[1])]
        for code, coords in zip(driver_codes, X_pca)
    }

    return {
        "kmeans": kmeans,
        "scaler": scaler,
        "pca": pca,
        "cluster_map": cluster_map,
        "pca_coords": pca_coords,
        "inertia": float(kmeans.inertia_),
    }


def predict_driver_cluster(
    kmeans: KMeans,
    scaler: StandardScaler,
    pca: PCA,
    features: dict,
) -> dict:
    """
    Predict cluster for a new driver given their extracted style features.

    Returns:
        {
            'cluster_id':          int (0-3),
            'cluster_description': str,
            'pca_x':               float,
            'pca_y':               float,
        }
    """
    from app.ml.driver_style.features import STYLE_FEATURE_COLS
    X = np.array([[features.get(col, 0.0) for col in STYLE_FEATURE_COLS]])
    X_scaled = scaler.transform(X)

    cluster_id = int(kmeans.predict(X_scaled)[0])
    pca_coords = pca.transform(X_scaled)[0]

    return {
        "cluster_id": cluster_id,
        "cluster_description": CLUSTER_LABELS.get(cluster_id, "Unknown"),
        "pca_x": float(pca_coords[0]),
        "pca_y": float(pca_coords[1]),
    }


def save_cluster_model(cluster_result: dict, base_path: str) -> None:
    """Save KMeans, scaler, and PCA to disk."""
    joblib.dump(cluster_result["kmeans"], f"{base_path}/style_kmeans.joblib")
    joblib.dump(cluster_result["scaler"], f"{base_path}/style_scaler.joblib")
    joblib.dump(cluster_result["pca"], f"{base_path}/style_pca.joblib")
    # Save cluster_map and pca_coords as a small json-friendly dict
    import json
    with open(f"{base_path}/style_cluster_map.json", "w") as f:
        json.dump({
            "cluster_map": cluster_result["cluster_map"],
            "pca_coords": cluster_result["pca_coords"],
        }, f, indent=2)


def load_cluster_model(base_path: str) -> dict:
    """Load KMeans, scaler, and PCA from disk."""
    import json
    kmeans = joblib.load(f"{base_path}/style_kmeans.joblib")
    scaler = joblib.load(f"{base_path}/style_scaler.joblib")
    pca = joblib.load(f"{base_path}/style_pca.joblib")
    with open(f"{base_path}/style_cluster_map.json") as f:
        meta = json.load(f)
    return {
        "kmeans": kmeans,
        "scaler": scaler,
        "pca": pca,
        "cluster_map": meta["cluster_map"],
        "pca_coords": meta["pca_coords"],
    }
