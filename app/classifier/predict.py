"""
predict.py — loads the trained model and scores a single listing.

This is what main.py calls to get a risk score between 0 and 1.
"""

import joblib
from pathlib import Path
from app.schemas import ProductListing

MODEL_PATH = Path(__file__).resolve().parent / "model.pkl"

_model = None  # loaded lazily so importing this file doesn't require model.pkl to exist yet


def risk_score(listing: ProductListing) -> float:
    """
    Returns a risk score from 0.0 (definitely safe) to 1.0 (definitely risky).

    TODO: extract the same features used in train.py, then call
    _model.predict_proba(...) on them.
    """
    global _model
    if _model is None:
        _model = joblib.load(MODEL_PATH)
    raise NotImplementedError
