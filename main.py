"""FastAPI backend:  uvicorn main:app --reload --port 8000

This is the real backend service. The Streamlit app (app.py) is just a
client that calls these endpoints over HTTP — it holds no agent logic
itself, so any other frontend (React, curl, Postman) can drive Sentinel
the same way.
"""
import os
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from agent import run_agent
from data import CASES, NOTIFICATIONS, PENDING_APPROVALS

app = FastAPI(title="Paytm Sentinel", version="0.1.0")

# Allow a local Streamlit / React dev server to call this API from the browser.
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/config")
def config():
    """Lets the frontend show which brain is active, without duplicating the logic."""
    if os.getenv("ANTHROPIC_API_KEY"):
        engine = "claude"
    elif os.getenv("GROQ_API_KEY"):
        engine = "groq"
    else:
        engine = "rules"
    return {
        "engine": engine,
        "zapier_notify": bool(os.getenv("ZAPIER_NOTIFY_URL")),
        "zapier_case": bool(os.getenv("ZAPIER_CASE_URL")),
    }


@app.post("/complaint")
async def complaint(text: str = Form(...), merchant_id: str = Form("M12345"),
                    txn_id: str = Form(...), qr_image: UploadFile | None = File(None)):
    img = await qr_image.read() if qr_image else None
    return run_agent(text, merchant_id, txn_id, img)


@app.get("/cases")
def cases():
    return {"cases": CASES, "notifications": NOTIFICATIONS, "pending_approvals": PENDING_APPROVALS}


@app.post("/approve/{approval_id}")
def approve(approval_id: str):
    for a in PENDING_APPROVALS:
        if a["approval_id"] == approval_id:
            a["status"] = "APPROVED_BY_HUMAN"
            return a
    return {"error": "not found"}
