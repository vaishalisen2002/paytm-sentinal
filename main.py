"""Optional REST API:  uvicorn main:app --reload"""
from fastapi import FastAPI, File, Form, UploadFile

from agent import run_agent
from data import CASES, NOTIFICATIONS, PENDING_APPROVALS

app = FastAPI(title="Paytm Sentinel")


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
