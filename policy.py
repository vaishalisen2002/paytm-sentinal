"""Policy engine: decides what the AI may do alone vs. what needs a human.
This is your 'Trust & Resilience' slide in code."""

AUTO_ALLOWED = {"notify_merchant", "create_fraud_case", "verify_qr",
                "get_transaction", "get_merchant"}
NEEDS_APPROVAL = {"restrict_payment_route"}

# Centralized Risk Engine Weights
WEIGHT_QR_MISMATCH = 60
WEIGHT_TXN_MISMATCH = 25
WEIGHT_MERCHANT_NOT_RECEIVED = 15
WEIGHT_ML_MAX = 20  # XGBoost visual signal adds up to 20 pts (requires mismatch to BLOCK)

# Decision Thresholds
THRESH_ALLOW_MAX = 24    # 0 - 24: ALLOW (LOW risk)
THRESH_WARN_MAX = 59     # 25 - 59: WARN (MEDIUM risk)
# 60+: BLOCK (HIGH / CRITICAL risk)


def action_for_score(score: int) -> str:
    """Target Sentinel Architecture Decision: ALLOW, WARN, or BLOCK."""
    if score >= 60:
        return "BLOCK"
    if score >= 25:
        return "WARN"
    return "ALLOW"


def risk_score(qr_mismatch: bool, txn_mismatch: bool, merchant_not_received: bool,
               ml_malicious_probability: float | None = None) -> int:
    score = 0
    if qr_mismatch:
        score += WEIGHT_QR_MISMATCH
    if txn_mismatch:
        score += WEIGHT_TXN_MISMATCH
    if merchant_not_received:
        score += WEIGHT_MERCHANT_NOT_RECEIVED
    if ml_malicious_probability is not None:
        score += int(ml_malicious_probability * WEIGHT_ML_MAX)
    return min(score, 100)


def risk_level(score: int) -> str:
    if score >= 80:
        return "CRITICAL"
    if score >= 50:
        return "HIGH"
    if score >= 25:
        return "MEDIUM"
    return "LOW"


def evaluate_risk(
    qr_mismatch: bool,
    txn_mismatch: bool,
    merchant_not_received: bool,
    ml_malicious_probability: float | None = None,
    ml_flag: bool | None = None,
    detected_qr_upi: str | None = None,
    registered_upi: str | None = None,
    txn_paid_to: str | None = None,
) -> dict:
    """Evaluates the 3 Sentinel Risk Engine Pillars:
    1. QR Malicious Probability (XGBoost image & decoder classifier)
    2. Merchant Mismatch (Tampering / Sticker replacement check)
    3. Transaction Anomaly (Payment diversion & non-receipt)
    """
    score = 0
    triggered_factors = []

    # --- Pillar 1: QR Image Malicious Probability (XGBoost) ---
    ml_points = 0
    if ml_malicious_probability is not None:
        ml_points = int(ml_malicious_probability * WEIGHT_ML_MAX)
        score += ml_points
        if ml_flag or ml_malicious_probability >= 0.5:
            triggered_factors.append(
                f"XGBoost QR Image Anomaly detected ({ml_malicious_probability:.1%} probability, +{ml_points} pts). "
                "Note: Model flagged visual/structural pattern; correlated with merchant identity."
            )

    # --- Pillar 2: Merchant QR Mismatch (Physical Sticker Tampering) ---
    if qr_mismatch:
        score += WEIGHT_QR_MISMATCH
        triggered_factors.append(
            f"Merchant QR Mismatch: Scanned QR points to '{detected_qr_upi}' but merchant is registered as '{registered_upi}' "
            f"(+{WEIGHT_QR_MISMATCH} pts). High probability of physical sticker tampering."
        )

    # --- Pillar 3: Transaction Telemetry Anomaly ---
    if txn_mismatch:
        score += WEIGHT_TXN_MISMATCH
        triggered_factors.append(
            f"Transaction Destination Anomaly: Payment sent to '{txn_paid_to}' instead of '{registered_upi}' "
            f"(+{WEIGHT_TXN_MISMATCH} pts)."
        )
    if merchant_not_received:
        score += WEIGHT_MERCHANT_NOT_RECEIVED
        triggered_factors.append(
            f"Payment Status Anomaly: Merchant confirmed funds not received for transaction (+{WEIGHT_MERCHANT_NOT_RECEIVED} pts)."
        )

    final_score = min(score, 100)
    level = risk_level(final_score)
    action = action_for_score(final_score)

    pillars = {
        "qr_ml": {
            "name": "QR Malicious Probability",
            "probability": ml_malicious_probability,
            "flag": bool(ml_flag) if ml_flag is not None else False,
            "points": ml_points,
            "status": (
                "ANOMALY_FLAGGED"
                if (ml_flag or (ml_malicious_probability or 0) >= 0.5)
                else "BENIGN"
            ) if ml_malicious_probability is not None else "UNAVAILABLE",
        },
        "merchant_mismatch": {
            "name": "Merchant QR Alignment",
            "qr_mismatch": bool(qr_mismatch),
            "detected_qr_upi": detected_qr_upi,
            "registered_upi": registered_upi,
            "points": WEIGHT_QR_MISMATCH if qr_mismatch else 0,
            "status": "MISMATCH_DETECTED" if qr_mismatch else ("MATCH" if detected_qr_upi else "NO_QR"),
        },
        "transaction_anomaly": {
            "name": "Transaction Telemetry",
            "txn_mismatch": bool(txn_mismatch),
            "merchant_not_received": bool(merchant_not_received),
            "txn_paid_to": txn_paid_to,
            "points": (WEIGHT_TXN_MISMATCH if txn_mismatch else 0) + (WEIGHT_MERCHANT_NOT_RECEIVED if merchant_not_received else 0),
            "status": "ANOMALY_DETECTED" if (txn_mismatch or merchant_not_received) else "NORMAL",
        },
    }

    return {
        "risk_score": final_score,
        "risk_level": level,
        "action": action,
        "pillars": pillars,
        "triggered_factors": triggered_factors,
    }


def is_auto_allowed(tool_name: str) -> bool:
    return tool_name in AUTO_ALLOWED
