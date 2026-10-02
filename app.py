"""Demo UI — a thin client of the FastAPI backend.

Run both:
    uvicorn main:app --reload --port 8000
    streamlit run app.py

All agent logic lives in main.py / agent.py; this file only makes HTTP calls.
"""
import os

import requests
import streamlit as st

API_BASE = os.getenv("SENTINEL_API_BASE", "http://localhost:8000")

st.set_page_config(page_title="Paytm Sentinel", page_icon="🛡️", layout="wide")

# ---------- Styling ----------
st.markdown("""
<style>
:root {
  --bg: #0b1220;
  --panel: #141f30;
  --panel-border: #22314a;
  --text: #f4f6f8;
  --muted: #8a93a6;
  --teal: #00d3b0;
  --amber: #ffb454;
  --red: #ff6b6b;
}
.stApp { background: var(--bg); color: var(--text); }
section[data-testid="stSidebar"] { background: var(--panel); }
h1, h2, h3 { font-family: 'Trebuchet MS', sans-serif; letter-spacing: 0.2px; }
h1 { color: var(--text) !important; }
h3 { color: var(--text) !important; }
div[data-testid="stTextArea"] textarea,
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
div[data-testid="stFileUploaderDropzone"] {
  background: var(--panel) !important;
  border: 1px solid var(--panel-border) !important;
  border-radius: 12px !important;
  color: var(--text) !important;
}
.sentinel-card {
  background: var(--panel); border: 1px solid var(--panel-border);
  border-radius: 16px; padding: 22px 24px; margin-bottom: 16px;
}
.sentinel-header { display: flex; align-items: center; gap: 14px; margin-bottom: 4px; }
.sentinel-header .emoji { font-size: 40px; }
.sentinel-sub { color: var(--muted); font-size: 15px; margin-bottom: 28px; }
.badge { display: inline-block; padding: 4px 12px; border-radius: 999px; font-size: 12px; font-weight: 700; letter-spacing: 0.5px; }
.badge-LOW, .badge-ALLOW { background: rgba(0,211,176,0.15); color: var(--teal); border: 1px solid rgba(0,211,176,0.4); }
.badge-MEDIUM, .badge-WARN { background: rgba(255,180,84,0.18); color: var(--amber); border: 1px solid rgba(255,180,84,0.4); }
.badge-HIGH, .badge-CRITICAL, .badge-BLOCK { background: rgba(255,107,107,0.18); color: var(--red); border: 1px solid rgba(255,107,107,0.4); }
.resolution-box {
  background: rgba(0,211,176,0.08); border: 1px solid rgba(0,211,176,0.35);
  border-radius: 12px; padding: 16px 20px; color: var(--text); font-size: 15px; line-height: 1.5;
}
.pillar-card {
  background: rgba(255,255,255,0.03); border: 1px solid var(--panel-border);
  border-radius: 10px; padding: 10px 12px; font-size: 12px; line-height: 1.4;
}
.stButton > button {
  background: linear-gradient(135deg, #ff6b6b, #ff8a3d); color: white;
  border: none; border-radius: 10px; padding: 10px 22px; font-weight: 700;
}
.stButton > button:hover { opacity: 0.92; color: white; }
[data-testid="stExpander"] { background: var(--panel); border: 1px solid var(--panel-border); border-radius: 12px; }
</style>
""", unsafe_allow_html=True)


def api_get(path: str):
    try:
        r = requests.get(f"{API_BASE}{path}", timeout=5)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        return {"error": str(e)}


# ---------- Header ----------
cfg = api_get("/config")
backend_up = "error" not in cfg
engine = cfg.get("engine", "unknown")
zap_on = cfg.get("zapier_notify") or cfg.get("zapier_case")

st.markdown("""
<div class="sentinel-header">
  <div class="emoji">🛡️</div>
  <div><h1 style="margin:0;">Paytm Sentinel</h1></div>
</div>
""", unsafe_allow_html=True)

if backend_up:
    st.markdown(f"""
    <div class="sentinel-sub">
      Autonomous AI teammate for merchant fraud prevention
      &nbsp;·&nbsp; Backend: 🟢 connected ({API_BASE})
      &nbsp;·&nbsp; Engine: <b>{engine}</b>
      &nbsp;·&nbsp; Zapier: {"🟢 connected" if zap_on else "⚪ not configured"}
    </div>
    """, unsafe_allow_html=True)
else:
    st.error(f"Can't reach the Sentinel backend at {API_BASE}. "
             f"Start it with: `uvicorn main:app --reload --port 8000`")
    st.stop()

left, right = st.columns([1, 1.2], gap="large")

with left:
    st.markdown('<div class="sentinel-card">', unsafe_allow_html=True)
    st.markdown("### 📥 Incoming complaint")
    text = st.text_area("Complaint", "I paid ₹500 at Sharma General Store but they say they never got it.",
                         label_visibility="collapsed")
    c1, c2 = st.columns(2)
    txn = c1.selectbox("Transaction", ["TXN1001", "TXN1002"])
    qr = c2.file_uploader("Merchant's current QR photo", type=["png", "jpg", "jpeg"])
    go = st.button("⚡ Let Sentinel handle it", type="primary", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    if go:
        with st.spinner("Sentinel is investigating..."):
            files = {"qr_image": (qr.name, qr.getvalue())} if qr else None
            data = {"text": text, "merchant_id": "M12345", "txn_id": txn}
            try:
                resp = requests.post(f"{API_BASE}/complaint", data=data, files=files, timeout=30)
                resp.raise_for_status()
                st.session_state["out"] = resp.json()
            except requests.RequestException as e:
                st.error(f"Request to backend failed: {e}")

with right:
    st.markdown('<div class="sentinel-card">', unsafe_allow_html=True)
    st.markdown("### 🧠 Agent reasoning & Risk Engine")
    out = st.session_state.get("out")
    if out:
        verify_step = next(
            (s["result"] for s in out.get("trace", []) if s.get("tool") == "verify_qr" and isinstance(s.get("result"), dict)),
            None
        )
        action = verify_step.get("action") if verify_step else None
        level = next(
            (s["result"].get("risk_level") for s in out["trace"] if isinstance(s.get("result"), dict) and "risk_level" in s["result"]),
            None
        )
        score = verify_step.get("risk_score") if verify_step else None
        if not action and level:
            action = "BLOCK" if level in ("HIGH", "CRITICAL") else ("WARN" if level == "MEDIUM" else "ALLOW")

        # Top Decision and Risk Badges
        if action or level:
            b_html = '<div style="display:flex; gap:10px; align-items:center; margin-bottom:14px;">'
            if action:
                b_html += f'<span class="badge badge-{action}" style="font-size:13px;">DECISION: {action}</span>'
            if level:
                score_str = f" ({score}/100)" if score is not None else ""
                b_html += f'<span class="badge badge-{level}">RISK: {level}{score_str}</span>'
            b_html += '</div>'
            st.markdown(b_html, unsafe_allow_html=True)

        # 3 Sentinel Risk Engine Pillars Display
        if verify_step and "pillars" in verify_step:
            pillars = verify_step["pillars"]
            st.markdown("##### 🛡️ Sentinel 3-Pillar Assessment")
            p1, p2, p3 = st.columns(3)
            with p1:
                p_qr = pillars.get("qr_ml", {})
                prob = p_qr.get("probability")
                prob_txt = f"{prob:.1%}" if prob is not None else "N/A"
                p1_flag = p_qr.get("flag", False)
                p1_color = "var(--red)" if p1_flag else "var(--teal)"
                st.markdown(
                    f'<div class="pillar-card">'
                    f'<b>Pillar 1: QR Image ML</b><br>'
                    f'XGBoost (4,105 feats)<br>'
                    f'Malicious Prob: <b style="color:{p1_color};">{prob_txt}</b><br>'
                    f'<span style="color:var(--muted); font-size:11px;">{"⚠️ Visual Anomaly" if p1_flag else "✅ Benign Pattern"}</span>'
                    f'</div>',
                    unsafe_allow_html=True
                )
            with p2:
                p_merch = pillars.get("merchant_mismatch", {})
                m_mis = p_merch.get("qr_mismatch", False)
                m_color = "var(--red)" if m_mis else "var(--teal)"
                m_det = p_merch.get("detected_qr_upi") or "None"
                st.markdown(
                    f'<div class="pillar-card">'
                    f'<b>Pillar 2: Merchant QR</b><br>'
                    f'Status: <b style="color:{m_color};">{"❌ MISMATCH" if m_mis else "✅ MATCH"}</b><br>'
                    f'Scanned: <code>{m_det}</code><br>'
                    f'<span style="color:var(--muted); font-size:11px;">{"Tampered Sticker!" if m_mis else "Registered Profile"}</span>'
                    f'</div>',
                    unsafe_allow_html=True
                )
            with p3:
                p_txn = pillars.get("transaction_anomaly", {})
                t_mis = p_txn.get("txn_mismatch", False)
                t_not_rec = p_txn.get("merchant_not_received", False)
                t_bad = t_mis or t_not_rec
                t_color = "var(--red)" if t_bad else "var(--teal)"
                st.markdown(
                    f'<div class="pillar-card">'
                    f'<b>Pillar 3: Txn Telemetry</b><br>'
                    f'Status: <b style="color:{t_color};">{"⚠️ ANOMALY" if t_bad else "✅ NORMAL"}</b><br>'
                    f'Received: {"❌ No" if t_not_rec else "✅ Yes"}<br>'
                    f'<span style="color:var(--muted); font-size:11px;">{"Destination Diverted" if t_mis else "Direct Route"}</span>'
                    f'</div>',
                    unsafe_allow_html=True
                )

            # Triggered risk factors explanation if present
            factors = verify_step.get("triggered_factors", [])
            if factors:
                with st.expander("⚠️ Triggered Risk Factors", expanded=True):
                    for f in factors:
                        st.markdown(f"- {f}")

        # Tool Execution Trace
        st.markdown("##### 🔍 Investigation Trace")
        for step in out["trace"]:
            icon = {"get_transaction": "💳", "get_merchant": "🏪", "verify_qr": "🔍",
                    "notify_merchant": "📣", "create_fraud_case": "🗂️",
                    "restrict_payment_route": "⛔"}.get(step["tool"], "🔧")
            result = step["result"]
            r_action = result.get("action") if isinstance(result, dict) else None
            r_risk = result.get("risk_level") if isinstance(result, dict) else None
            label = f"{icon} {step['tool']}"
            if r_action:
                label += f" — {r_action}"
            elif r_risk:
                label += f" — {r_risk}"
            with st.expander(label, expanded=step["tool"] == "verify_qr"):
                st.json(result)

        st.markdown(f'<div class="resolution-box">✅ {out["summary"]}</div>', unsafe_allow_html=True)
    else:
        st.caption("Submit a complaint on the left to see Sentinel's reasoning here.")
    st.markdown('</div>', unsafe_allow_html=True)

st.divider()

cases_data = api_get("/cases")
notifications = cases_data.get("notifications", [])
cases_list = cases_data.get("cases", [])
approvals = cases_data.get("pending_approvals", [])

c1, c2, c3 = st.columns(3)
with c1:
    st.markdown('<div class="sentinel-card">', unsafe_allow_html=True)
    st.markdown("#### 📨 Notifications")
    if notifications:
        for n in notifications:
            st.write(f"**{n['merchant_id']}** — {n['message']}")
    else:
        st.caption("—")
    st.markdown('</div>', unsafe_allow_html=True)

with c2:
    st.markdown('<div class="sentinel-card">', unsafe_allow_html=True)
    st.markdown("#### 🗂️ Fraud cases")
    if cases_list:
        for cs in cases_list:
            st.markdown(f'<span class="badge badge-{cs["risk_level"]}">{cs["risk_level"]}</span>'
                        f'&nbsp;&nbsp;**{cs["case_id"]}** — {cs["summary"]}', unsafe_allow_html=True)
    else:
        st.caption("—")
    st.markdown('</div>', unsafe_allow_html=True)

with c3:
    st.markdown('<div class="sentinel-card">', unsafe_allow_html=True)
    st.markdown("#### ⏳ Awaiting human approval")
    if approvals:
        for a in approvals:
            st.warning(f"{a['upi_id']} — {a['status']}")
            if a["status"] == "PENDING_HUMAN_APPROVAL" and st.button("Approve", key=a["approval_id"]):
                requests.post(f"{API_BASE}/approve/{a['approval_id']}", timeout=5)
                st.rerun()
    else:
        st.caption("—")
    st.markdown('</div>', unsafe_allow_html=True)
