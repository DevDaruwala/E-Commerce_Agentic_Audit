"""
train.py — trains the risk classifier on data/mock_list.json and
saves it to app/classifier/model.pkl.

Phase 1, build task 4: start with the DUMBEST possible version —
logistic regression on 3-4 numeric features. Get real numbers,
even bad ones, before trying to improve anything.
"""

import json
import joblib
from pathlib import Path
from sklearn.linear_model import LogisticRegression

DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "mock_list.json"
MODEL_PATH = Path(__file__).resolve().parent / "model.pkl"


def load_training_data():
    """TODO: load mock_list.json and turn it into (features, labels)."""
    with open(DATA_PATH) as f:
        listings = json.load(f)
    raise NotImplementedError("Turn `listings` into feature vectors + labels here.")


def train():
    """TODO: fit a LogisticRegression and save it with joblib."""
    raise NotImplementedError


if __name__ == "__main__":
    train()
