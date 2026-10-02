"""Tools the agent can call. Each returns a plain dict (JSON-safe)."""
import re
import uuid
from urllib.parse import urlparse, parse_qs

import cv2
import numpy as np

from data import MERCHANTS, TRANSACTIONS, CASES, NOTIFICATIONS, PENDING_APPROVALS
from policy import risk_score, risk_level


def get_transaction(txn_id: str) -> dict:
    txn = TRANSACTIONS.get(txn_id)
    return {"txn_id": txn_id, **txn} if txn else {"error": f"{txn_id} not found"}


def get_merchant(merchant_id: str) -> dict:
    m = MERCHANTS.get(merchant_id)
    return {"merchant_id": merchant_id, **m} if m else {"error": "merchant not found"}


def decode_qr_upi_id(image_bytes: bytes) -> str | None:
    """Decode a QR photo and pull the UPI ID (pa=...) out of the upi:// link."""
    img = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return None
    text, _, _ = cv2.QRCodeDetector().detectAndDecode(img)
    if not text:
        return None
    if text.startswith("upi://"):
        return parse_qs(urlparse(text).query).get("pa", [None])[0]
    m = re.search(r"[\w.\-]+@[\w]+", text)
    return m.group(0) if m else None


def verify_qr(merchant_id: str, image_bytes: bytes | None = None,
              txn_id: str | None = None) -> dict:
    """Compare the QR photo (and the txn destination) with the registered UPI ID."""
    m = MERCHANTS.get(merchant_id)
    if not m:
        return {"error": "merchant not found"}
    registered = m["registered_upi"]

    detected = decode_qr_upi_id(image_bytes) if image_bytes else None
    qr_mismatch = detected is not None and detected != registered

    txn = TRANSACTIONS.get(txn_id) if txn_id else None
    txn_mismatch = bool(txn) and txn["paid_to_upi"] != registered
    not_received = bool(txn) and not txn["merchant_received"]

    score = risk_score(qr_mismatch, txn_mismatch, not_received)
    return {
        "registered_upi": registered,
        "detected_qr_upi": detected,
        "qr_mismatch": qr_mismatch,
        "txn_paid_to": txn["paid_to_upi"] if txn else None,
        "txn_destination_mismatch": txn_mismatch,
        "risk_score": score,
        "risk_level": risk_level(score),
    }


def notify_merchant(merchant_id: str, message: str) -> dict:
    NOTIFICATIONS.append({"merchant_id": merchant_id, "message": message})
    return {"status": "sent"}


def create_fraud_case(merchant_id: str, txn_id: str, risk_level: str, summary: str) -> dict:
    case = {"case_id": f"CASE-{uuid.uuid4().hex[:6].upper()}", "merchant_id": merchant_id,
            "txn_id": txn_id, "risk_level": risk_level, "summary": summary,
            "status": "OPEN"}
    CASES.append(case)
    return case


def restrict_payment_route(upi_id: str, reason: str) -> dict:
    """High-impact action: NEVER executes automatically. Queues for human approval."""
    item = {"approval_id": f"APR-{uuid.uuid4().hex[:6].upper()}", "upi_id": upi_id,
            "reason": reason, "status": "PENDING_HUMAN_APPROVAL"}
    PENDING_APPROVALS.append(item)
    return item


TOOL_FUNCS = {
    "get_transaction": get_transaction,
    "get_merchant": get_merchant,
    "verify_qr": verify_qr,
    "notify_merchant": notify_merchant,
    "create_fraud_case": create_fraud_case,
    "restrict_payment_route": restrict_payment_route,
}

TOOL_SCHEMAS = [
    {"name": "get_transaction", "description": "Fetch a transaction by ID.",
     "input_schema": {"type": "object", "properties": {"txn_id": {"type": "string"}}, "required": ["txn_id"]}},
    {"name": "get_merchant", "description": "Fetch merchant profile and registered UPI ID.",
     "input_schema": {"type": "object", "properties": {"merchant_id": {"type": "string"}}, "required": ["merchant_id"]}},
    {"name": "verify_qr", "description": "Compare the merchant's QR photo and the transaction destination against the registered UPI ID; returns a risk score. The QR photo is attached automatically if provided.",
     "input_schema": {"type": "object", "properties": {"merchant_id": {"type": "string"}, "txn_id": {"type": "string"}}, "required": ["merchant_id"]}},
    {"name": "notify_merchant", "description": "Send the merchant a notification.",
     "input_schema": {"type": "object", "properties": {"merchant_id": {"type": "string"}, "message": {"type": "string"}}, "required": ["merchant_id", "message"]}},
    {"name": "create_fraud_case", "description": "Open a fraud case for human fraud-ops review.",
     "input_schema": {"type": "object", "properties": {"merchant_id": {"type": "string"}, "txn_id": {"type": "string"}, "risk_level": {"type": "string"}, "summary": {"type": "string"}}, "required": ["merchant_id", "txn_id", "risk_level", "summary"]}},
    {"name": "restrict_payment_route", "description": "Request restriction of a suspicious UPI ID. Queues for human approval; does not execute automatically.",
     "input_schema": {"type": "object", "properties": {"upi_id": {"type": "string"}, "reason": {"type": "string"}}, "required": ["upi_id", "reason"]}},
]
