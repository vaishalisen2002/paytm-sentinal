"""Policy engine: decides what the AI may do alone vs. what needs a human.
This is your 'Trust & Resilience' slide in code."""

AUTO_ALLOWED = {"notify_merchant", "create_fraud_case", "verify_qr",
                "get_transaction", "get_merchant"}
NEEDS_APPROVAL = {"restrict_payment_route"}


def risk_score(qr_mismatch: bool, txn_mismatch: bool, merchant_not_received: bool) -> int:
    score = 0
    if qr_mismatch:
        score += 60
    if txn_mismatch:
        score += 25
    if merchant_not_received:
        score += 15
    return score


def risk_level(score: int) -> str:
    if score >= 80:
        return "CRITICAL"
    if score >= 50:
        return "HIGH"
    if score >= 25:
        return "MEDIUM"
    return "LOW"


def is_auto_allowed(tool_name: str) -> bool:
    return tool_name in AUTO_ALLOWED
