"""The AI teammate: understand -> investigate -> decide -> act -> escalate.
Uses Claude tool-calling. If no API key is set, falls back to a rule-based
run of the same tools so your demo never dies on stage."""
import json
import os

import anthropic

from tools import TOOL_FUNCS, TOOL_SCHEMAS, verify_qr
from policy import is_auto_allowed

MODEL = os.getenv("SENTINEL_MODEL", "claude-sonnet-5")

SYSTEM_PROMPT = """You are Paytm Sentinel, an autonomous AI teammate for Paytm merchant
support. A customer or merchant has filed a complaint about a payment. Resolve it end-to-end:
1. Fetch the transaction and merchant.
2. Call verify_qr to check for QR tampering / wrong destination.
3. If risk is LOW: explain to the merchant that no fraud was found.
4. If MEDIUM or higher: notify_merchant AND create_fraud_case.
5. If HIGH or CRITICAL: also call restrict_payment_route (it will queue for human approval).
Be concise. End with a short plain-language resolution summary and state clearly
whether a human must review anything."""


def run_agent(complaint: str, merchant_id: str, txn_id: str,
              qr_image: bytes | None = None) -> dict:
    trace: list[dict] = []
    if os.getenv("ANTHROPIC_API_KEY"):
        summary = _run_llm(complaint, merchant_id, txn_id, qr_image, trace)
    else:
        summary = _run_rules(merchant_id, txn_id, qr_image, trace)
    return {"trace": trace, "summary": summary}


def _call_tool(name: str, args: dict, qr_image, trace: list) -> dict:
    if not is_auto_allowed(name) and name != "restrict_payment_route":
        result = {"error": "tool not permitted by policy"}
    else:
        if name == "verify_qr":
            args = {**args, "image_bytes": qr_image}
        result = TOOL_FUNCS[name](**args)
    shown_args = {k: v for k, v in args.items() if k != "image_bytes"}
    trace.append({"tool": name, "args": shown_args, "result": result})
    return result


def _run_llm(complaint, merchant_id, txn_id, qr_image, trace) -> str:
    import anthropic
    client = anthropic.Anthropic()
    messages = [{"role": "user", "content":
                 f"Complaint: {complaint}\nMerchant ID: {merchant_id}\nTransaction ID: {txn_id}\n"
                 f"QR photo provided: {qr_image is not None}"}]
    for _ in range(8):  # hard cap on agent steps
        resp = client.messages.create(model=MODEL, max_tokens=1000, system=SYSTEM_PROMPT,
                                      tools=TOOL_SCHEMAS, messages=messages)
        messages.append({"role": "assistant", "content": resp.content})
        if resp.stop_reason != "tool_use":
            return "".join(b.text for b in resp.content if b.type == "text")
        results = []
        for block in resp.content:
            if block.type == "tool_use":
                out = _call_tool(block.name, block.input, qr_image, trace)
                results.append({"type": "tool_result", "tool_use_id": block.id,
                                "content": json.dumps(out)})
        messages.append({"role": "user", "content": results})
    return "Stopped after max steps; escalating to a human."


def _run_rules(merchant_id, txn_id, qr_image, trace) -> str:
    """Offline fallback: same tools, deterministic decisions."""
    _call_tool("get_transaction", {"txn_id": txn_id}, qr_image, trace)
    _call_tool("get_merchant", {"merchant_id": merchant_id}, qr_image, trace)
    v = _call_tool("verify_qr", {"merchant_id": merchant_id, "txn_id": txn_id}, qr_image, trace)
    level = v.get("risk_level", "LOW")
    if level == "LOW":
        return "No fraud indicators found. Ticket resolved; no human review needed."
    msg = (f"Payment may have gone to {v.get('txn_paid_to')} instead of "
           f"{v.get('registered_upi')}. Please check your QR sticker.")
    _call_tool("notify_merchant", {"merchant_id": merchant_id, "message": msg}, qr_image, trace)
    _call_tool("create_fraud_case", {"merchant_id": merchant_id, "txn_id": txn_id,
               "risk_level": level, "summary": msg}, qr_image, trace)
    if level in ("HIGH", "CRITICAL"):
        _call_tool("restrict_payment_route", {"upi_id": v["txn_paid_to"],
                   "reason": "QR tampering suspected"}, qr_image, trace)
        return f"{level} risk: QR tampering. Merchant notified, case opened. Route restriction awaits human approval."
    return f"{level} risk: merchant notified and case opened for review."
