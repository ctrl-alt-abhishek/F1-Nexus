"""
model/train.py
Model training, evaluation, and persistence.
"""

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error
import joblib


def train_model(X: pd.DataFrame, y: pd.Series) -> dict:
    """
    Train a regression model to predict lap times.

    - 80/20 train/test split with random_state=42
    - Tries XGBRegressor first, falls back to RandomForestRegressor
    - Returns dict with model, metrics, and feature importance

    Parameters
    ----------
    X : pd.DataFrame
        Feature matrix.
    y : pd.Series
        Target vector (lap time in seconds).

    Returns
    -------
    dict with keys:
        'model'              : trained model object
        'rmse'               : float, root mean squared error on test set
        'mae'                : float, mean absolute error on test set
        'feature_importance' : pd.Series, feature importances
    """
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # Try XGBRegressor first
    try:
        from xgboost import XGBRegressor

        model = XGBRegressor(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.1,
            random_state=42,
            verbosity=0,
        )
    except ImportError:
        from sklearn.ensemble import RandomForestRegressor

        model = RandomForestRegressor(
            n_estimators=200,
            max_depth=10,
            random_state=42,
        )

    model.fit(X_train, y_train)

    # Evaluate
    y_pred = model.predict(X_test)
    rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
    mae = float(mean_absolute_error(y_test, y_pred))

    # Feature importance
    importance = pd.Series(
        model.feature_importances_, index=X.columns
    ).sort_values(ascending=False)

    return {
        "model": model,
        "rmse": rmse,
        "mae": mae,
        "feature_importance": importance,
    }


def save_model(model, path: str):
    """Save a trained model to disk using joblib."""
    joblib.dump(model, path)


def load_model(path: str):
    """Load a trained model from disk using joblib."""
    return joblib.load(path)
