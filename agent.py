"""The AI teammate: understand -> investigate -> decide -> act -> escalate.
Tries Claude first, then Groq (free), then falls back to a rule-based run
of the same tools so your demo never dies on stage."""
import json
import os

from tools import TOOL_FUNCS, TOOL_SCHEMAS
from policy import is_auto_allowed

CLAUDE_MODEL = os.getenv("SENTINEL_MODEL", "claude-sonnet-5")
GROQ_MODEL = os.getenv("SENTINEL_GROQ_MODEL", "llama-3.3-70b-versatile")

SYSTEM_PROMPT = """You are Paytm Sentinel, an autonomous AI teammate for Paytm merchant
support. A customer or merchant has filed a complaint about a payment. Resolve it end-to-end:
1. Fetch the transaction and merchant profile.
2. Call verify_qr to inspect the 3 Sentinel pillars:
   - Pillar 1: QR Image Malicious Probability (XGBoost). This detects visual/structural patterns; it is ONE advisory signal, NOT standalone proof of fraud. Correlate it with merchant and transaction data.
   - Pillar 2: Merchant QR Mismatch (detects physical QR sticker replacement/tampering).
   - Pillar 3: Transaction Telemetry (detects payment diversion and merchant non-receipt).
3. Evaluate the result:
   - If action is ALLOW (LOW risk): explain that no fraud was found. If the image model flagged an anomaly, explain clearly that merchant identity and transaction verified safely.
   - If action is WARN (MEDIUM risk): call notify_merchant AND create_fraud_case.
   - If action is BLOCK (HIGH or CRITICAL risk): call notify_merchant, create_fraud_case, AND call restrict_payment_route (which queues for human approval).
Be concise. End with a clear plain-language resolution summary stating the decision (ALLOW, WARN, or BLOCK) and whether human review is required."""


def run_agent(complaint: str, merchant_id: str, txn_id: str,
              qr_image: bytes | None = None) -> dict:
    trace: list[dict] = []
    if os.getenv("ANTHROPIC_API_KEY"):
        summary = _run_claude(complaint, merchant_id, txn_id, qr_image, trace)
    elif os.getenv("GROQ_API_KEY"):
        summary = _run_groq(complaint, merchant_id, txn_id, qr_image, trace)
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


def _user_prompt(complaint, merchant_id, txn_id, qr_image) -> str:
    return (f"Complaint: {complaint}\nMerchant ID: {merchant_id}\nTransaction ID: {txn_id}\n"
            f"QR photo provided: {qr_image is not None}")


def _run_claude(complaint, merchant_id, txn_id, qr_image, trace) -> str:
    import anthropic
    client = anthropic.Anthropic()
    messages = [{"role": "user", "content": _user_prompt(complaint, merchant_id, txn_id, qr_image)}]
    for _ in range(8):  # hard cap on agent steps
        resp = client.messages.create(model=CLAUDE_MODEL, max_tokens=1000, system=SYSTEM_PROMPT,
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


def _to_openai_tools() -> list[dict]:
    """Groq speaks the OpenAI function-calling format, not Anthropic's tool format."""
    return [{"type": "function", "function": {
                "name": t["name"], "description": t["description"],
                "parameters": t["input_schema"]}}
            for t in TOOL_SCHEMAS]


def _run_groq(complaint, merchant_id, txn_id, qr_image, trace) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=os.environ["GROQ_API_KEY"], base_url="https://api.groq.com/openai/v1")
    messages = [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _user_prompt(complaint, merchant_id, txn_id, qr_image)}]
    tools = _to_openai_tools()
    for _ in range(8):  # hard cap on agent steps
        resp = client.chat.completions.create(model=GROQ_MODEL, messages=messages, tools=tools)
        msg = resp.choices[0].message
        messages.append(msg.model_dump(exclude_none=True))
        if not msg.tool_calls:
            return msg.content or "No summary returned."
        for call in msg.tool_calls:
            args = json.loads(call.function.arguments or "{}")
            out = _call_tool(call.function.name, args, qr_image, trace)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(out)})
    return "Stopped after max steps; escalating to a human."


def _format_alert_message(v: dict) -> str:
    registered = v.get("registered_upi", "registered UPI")
    detected = v.get("detected_qr_upi")
    txn_paid = v.get("txn_paid_to")
    qr_mismatch = v.get("qr_mismatch", False)
    txn_mismatch = v.get("txn_destination_mismatch", False)

    if qr_mismatch and txn_mismatch:
        if detected == txn_paid:
            return (
                f"🚨 Critical Fraud Alert: Scanned QR code and customer payment both point to "
                f"unauthorized UPI '{detected}' instead of your registered UPI '{registered}'. "
                f"Please inspect and replace your counter QR stand immediately."
            )
        else:
            return (
                f"🚨 Critical Fraud Alert: Scanned QR directs to unauthorized UPI '{detected}', "
                f"and payment was diverted to '{txn_paid}' instead of registered UPI '{registered}'. "
                f"Please check your physical counter QR stand immediately."
            )
    elif qr_mismatch:
        return (
            f"🚨 Tampered QR Detected: The physical QR code at your counter directs payments to "
            f"unauthorized UPI '{detected}' instead of your registered UPI '{registered}'. "
            f"Please inspect and replace your counter QR sticker immediately."
        )
    elif txn_mismatch:
        return (
            f"⚠️ Payment Diversion Alert: Transaction was paid to unauthorized UPI '{txn_paid}' "
            f"instead of your registered UPI '{registered}'. Funds were diverted away from your store."
        )
    else:
        return (
            f"⚠️ Payment Status Anomaly: Customer transaction funds were not received by '{registered}'. "
            f"Please verify your recent settlement records."
        )


def _run_rules(merchant_id, txn_id, qr_image, trace) -> str:
    """Offline fallback: same tools, deterministic decisions."""
    _call_tool("get_transaction", {"txn_id": txn_id}, qr_image, trace)
    _call_tool("get_merchant", {"merchant_id": merchant_id}, qr_image, trace)
    v = _call_tool("verify_qr", {"merchant_id": merchant_id, "txn_id": txn_id}, qr_image, trace)
    action = v.get("action", "ALLOW")
    level = v.get("risk_level", "LOW")
    score = v.get("risk_score", 0)

    if action == "ALLOW" or level == "LOW":
        ml_prob = v.get("ml_malicious_probability")
        if ml_prob and ml_prob >= 0.5:
            return (
                f"Decision: ALLOW ({level} risk, {score}/100). Merchant identity and transaction destination "
                f"are verified with registered UPI '{v.get('registered_upi')}'. Note: XGBoost image model flagged an anomaly "
                f"({ml_prob:.1%}), but no identity mismatch or payment diversion occurred. Ticket resolved safely."
            )
        return f"Decision: ALLOW ({level} risk, {score}/100). No fraud indicators found. Ticket resolved; no human review needed."

    registered = v.get("registered_upi", "sharmageneral@paytm")
    msg = f"Payment may have gone to someone else instead of {registered}. Please check your QR sticker."
    _call_tool("notify_merchant", {"merchant_id": merchant_id, "message": msg}, qr_image, trace)
    _call_tool("create_fraud_case", {"merchant_id": merchant_id, "txn_id": txn_id,
               "risk_level": level, "summary": msg}, qr_image, trace)

    suspicious_upi = (
        v.get("detected_qr_upi") if v.get("qr_mismatch") else v.get("txn_paid_to")
    ) or v.get("txn_paid_to") or "unknown_destination"

    if action == "BLOCK" or level in ("HIGH", "CRITICAL"):
        _call_tool("restrict_payment_route", {"upi_id": suspicious_upi,
                   "reason": "QR tampering / payment diversion suspected"}, qr_image, trace)
        return (
            f"Decision: BLOCK ({level} risk, {score}/100). QR tampering detected. "
            f"Merchant notified, fraud case opened, and route restriction for '{suspicious_upi}' submitted for human approval."
        )

    return f"Decision: WARN ({level} risk, {score}/100). Merchant notified and fraud case opened for review."
