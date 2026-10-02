# Paytm Sentinel (hackathon MVP)

    pip install -r requirements.txt
    python make_demo_qrs.py            # creates real_qr.png + fake_qr.png
    export ANTHROPIC_API_KEY=...       # optional; without it, a rule-based fallback runs
    streamlit run app.py               # demo UI
    uvicorn main:app --reload          # optional REST API

Demo: pick TXN1001, upload fake_qr.png -> CRITICAL, notify + case + approval queue.
      pick TXN1002, upload real_qr.png -> LOW, no false alarm.
