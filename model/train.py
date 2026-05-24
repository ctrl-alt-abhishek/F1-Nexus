"""
model/train.py - Model training, evaluation, and persistence.
"""

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error
import joblib


def train_model(X: pd.DataFrame, y: pd.Series) -> dict:
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

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

    y_pred = model.predict(X_test)
    rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
    mae = float(mean_absolute_error(y_test, y_pred))

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
    joblib.dump(model, path)


def load_model(path: str):
    return joblib.load(path)
