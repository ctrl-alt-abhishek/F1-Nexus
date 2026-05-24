"""
app/ml/strategy/train.py - Pit stop strategy classifier training.

Binary classification: will driver pit on this lap (1) or not (0)?
Highly imbalanced - ~1 pit per 20 laps. scale_pos_weight corrects for this.
"""

import numpy as np
import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    classification_report, roc_auc_score, precision_score, recall_score, f1_score
)
from xgboost import XGBClassifier


def train_model(X: pd.DataFrame, y: pd.Series) -> dict:
    """
    Train the pit stop strategy XGBoost classifier.

    Handles class imbalance with scale_pos_weight = neg_count / pos_count.
    80/20 train/test split, random_state=42 for reproducibility.

    Returns:
        {
            'model':             trained XGBClassifier,
            'roc_auc':           float,
            'f1':                float,
            'precision':         float,
            'recall':            float,
            'feature_importance': pd.Series (sorted descending),
            'class_balance':     dict {'pit_laps': int, 'no_pit_laps': int},
        }
    """
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # Compute imbalance ratio for scale_pos_weight
    neg_count = int((y_train == 0).sum())
    pos_count = int((y_train == 1).sum())
    scale_pos_weight = neg_count / max(pos_count, 1)

    model = XGBClassifier(
        n_estimators=300,
        learning_rate=0.05,
        max_depth=5,
        scale_pos_weight=scale_pos_weight,  # corrects for pit stop rarity
        random_state=42,
        verbosity=0,
        n_jobs=-1,
        eval_metric="logloss",
    )

    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]

    importance = pd.Series(
        model.feature_importances_, index=X.columns
    ).sort_values(ascending=False)

    return {
        "model": model,
        "roc_auc": float(roc_auc_score(y_test, y_prob)),
        "f1": float(f1_score(y_test, y_pred, zero_division=0)),
        "precision": float(precision_score(y_test, y_pred, zero_division=0)),
        "recall": float(recall_score(y_test, y_pred, zero_division=0)),
        "feature_importance": importance,
        "class_balance": {"pit_laps": pos_count, "no_pit_laps": neg_count},
    }


def save_model(model, path: str) -> None:
    joblib.dump(model, path)


def load_model(path: str):
    return joblib.load(path)
