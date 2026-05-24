"""
app/ml/degradation/train.py - Model training, evaluation, and serialization.

Ported and upgraded from model/train.py. Key changes:
- Exact hyperparameters from spec (n_estimators=300, lr=0.05, max_depth=5)
- Added r2 to returned metrics
- XGBoost is now a hard dependency (no sklearn fallback) since we control the environment
"""

import pandas as pd
import numpy as np
import joblib
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from xgboost import XGBRegressor


def train_model(X: pd.DataFrame, y: pd.Series) -> dict:
    """
    Train the tyre degradation XGBoost regressor.

    Split: 80% train / 20% test, random_state=42 (reproducible).
    Hyperparameters are fixed per spec - do not change without updating the version tag.

    Returns:
        {
            'model':              trained XGBRegressor,
            'rmse':               float (test set),
            'mae':                float (test set),
            'r2':                 float (test set),
            'feature_importance': pd.Series (sorted descending by importance),
        }
    """
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    model = XGBRegressor(
        n_estimators=300,
        learning_rate=0.05,
        max_depth=5,
        random_state=42,
        verbosity=0,
        n_jobs=-1,   # use all CPU cores during training
    )

    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
    mae = float(mean_absolute_error(y_test, y_pred))
    r2 = float(r2_score(y_test, y_pred))

    importance = pd.Series(
        model.feature_importances_, index=X.columns
    ).sort_values(ascending=False)

    return {
        "model": model,
        "rmse": rmse,
        "mae": mae,
        "r2": r2,
        "feature_importance": importance,
    }


def save_model(model, path: str) -> None:
    """Serialize the trained model to disk with joblib."""
    joblib.dump(model, path)


def load_model(path: str):
    """Deserialize a previously saved model from disk."""
    return joblib.load(path)
