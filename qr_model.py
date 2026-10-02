"""Loads the trained XGBoost QR-fraud model and scores an uploaded QR photo.

Drop your trained file at the project root as sentinel_xgboost_qr_model.pkl
(or point SENTINEL_QR_MODEL_PATH at it). If the file isn't present, the app
keeps working — it just skips the ML signal and relies on the rule-based
UPI-mismatch check alone.
"""
import os

import joblib

from qr_features import extract_features_from_bytes

MODEL_NAME = "sentinel_xgboost_qr_model.pkl"
_DEFAULT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), MODEL_NAME)
MODEL_PATH = os.getenv("SENTINEL_QR_MODEL_PATH") or (
    _DEFAULT_PATH if os.path.exists(_DEFAULT_PATH) else MODEL_NAME
)

_model = None
_load_attempted = False


def _get_model():
    global _model, _load_attempted
    if not _load_attempted:
        _load_attempted = True
        try:
            target_path = MODEL_PATH
            if not os.path.exists(target_path) and os.path.exists(_DEFAULT_PATH):
                target_path = _DEFAULT_PATH
            if os.path.exists(target_path):
                _model = joblib.load(target_path)
        except Exception:
            _model = None
    return _model


def predict_qr_risk(image_bytes: bytes) -> dict:
    """Returns the model's malicious-QR probability, or ml_available=False if no model is loaded."""
    try:
        model = _get_model()
        if model is None:
            return {"ml_available": False, "ml_status": "model_not_found"}

        features = extract_features_from_bytes(image_bytes)
        if features is None:
            return {"ml_available": True, "error": "could not decode image for the model"}

        # Model expects (N, 4105) float32 features
        probability = float(model.predict_proba(features.reshape(1, -1))[0, 1])
        return {
            "ml_available": True,
            "ml_malicious_probability": round(probability, 4),
            "ml_flag": bool(probability >= 0.5),
            "ml_status": "scored",
        }
    except Exception as e:
        return {"ml_available": False, "ml_status": f"error: {str(e)}"}
