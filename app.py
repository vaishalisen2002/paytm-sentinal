"""Demo UI:  streamlit run app.py"""
import streamlit as st  # type: ignore

from agent import run_agent
from data import CASES, NOTIFICATIONS, PENDING_APPROVALS

st.set_page_config(page_title="Paytm Sentinel", layout="wide")
st.title("🛡️ Paytm Sentinel")
st.caption("Autonomous AI teammate for merchant fraud prevention")

left, right = st.columns(2)
with left:
    st.subheader("Incoming complaint")
    text = st.text_area("Complaint", "I paid ₹500 at Sharma General Store but they say they never got it.")
    txn = st.selectbox("Transaction", ["TXN1001", "TXN1002"])
    qr = st.file_uploader("Merchant's current QR photo", type=["png", "jpg", "jpeg"])
    if st.button("Let Sentinel handle it", type="primary"):
        with st.spinner("Sentinel is investigating..."):
            st.session_state["out"] = run_agent(text, "M12345", txn, qr.read() if qr else None)

with right:
    st.subheader("Agent reasoning")
    out = st.session_state.get("out")
    if out:
        for step in out["trace"]:
            with st.expander(f"🔧 {step['tool']}", expanded=step["tool"] == "verify_qr"):
                st.json(step["result"])
        st.success(out["summary"])

st.divider()
c1, c2, c3 = st.columns(3)
c1.subheader("Notifications"); c1.write(NOTIFICATIONS or "—")
c2.subheader("Fraud cases"); c2.write(CASES or "—")
c3.subheader("Awaiting human approval")
for a in PENDING_APPROVALS:
    c3.warning(f"{a['upi_id']} — {a['status']}")
    if a["status"] == "PENDING_HUMAN_APPROVAL" and c3.button("Approve", key=a["approval_id"]):
        a["status"] = "APPROVED_BY_HUMAN"
        st.rerun()
if not PENDING_APPROVALS:
    c3.write("—")
