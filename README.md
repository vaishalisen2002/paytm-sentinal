# Paytm Sentinel (hackathon MVP)

    pip install -r requirements.txt
    python make_demo_qrs.py            # creates real_qr.png + fake_qr.png
    streamlit run app.py               # demo UI

The agent picks its brain in this order:
1. `ANTHROPIC_API_KEY` set -> real Claude tool-calling
2. else `GROQ_API_KEY` set -> free Groq tool-calling (llama-3.3-70b-versatile)
3. else -> deterministic rule-based fallback (same tools, no LLM, zero cost,
   never fails from a bad connection — good for live demos)

## Using Groq (free, no card)

1. Get a free key at https://console.groq.com/keys
2. `export GROQ_API_KEY=gsk_...`
3. `streamlit run app.py`

Override the model with `SENTINEL_GROQ_MODEL` (default: `llama-3.3-70b-versatile`).
Free-tier rate limits are generous enough for a hackathon demo but are
requests/tokens-per-minute caps, not unlimited — don't hammer it in a loop
right before you go on stage.

Demo: pick TXN1001, upload fake_qr.png -> HIGH/CRITICAL risk, notify + case + approval queue.
      pick TXN1002, upload real_qr.png -> LOW, no false alarm.

## Wiring up Zapier -> Gmail

1. In Zapier, create a Zap:
   - Trigger: **Webhooks by Zapier -> Catch Hook**. Copy the URL it gives you.
   - Action: **Gmail -> Send Email**. Map `{{subject}}` and `{{message}}` (or
     `{{summary}}` for the fraud-case Zap) from the webhook's test payload into
     the email's subject/body, and set the "To" address to wherever you want
     alerts to land.
   - Turn the Zap on.
2. Make a second Zap the same way for fraud cases if you want case alerts
   separated from merchant notifications (optional — you can reuse one URL
   for both).
3. Set the webhook URL(s) before running the app:

       export ZAPIER_NOTIFY_URL="https://hooks.zapier.com/hooks/catch/XXXX/yyyy/"
       export ZAPIER_CASE_URL="https://hooks.zapier.com/hooks/catch/XXXX/zzzz/"
       streamlit run app.py

4. The header shows "Zapier: 🟢 connected" once at least one URL is set.
   Submit a complaint for TXN1001 with fake_qr.png uploaded — you should
   see a real Gmail land within a few seconds.

If a webhook call fails (bad Wi-Fi, wrong URL), the app does not crash —
it just logs the notification/case locally and keeps going, so the demo
is never blocked on Zapier being reachable.

## Using your trained XGBoost QR model

1. Train your model as you already did — but import feature extraction from
   `qr_features.py` in this project instead of keeping a separate copy in
   your training script, so training and inference features can't drift apart:

       from qr_features import extract_features   # instead of defining it locally

2. Drop the saved file at the project root:

       sentinel_xgboost_qr_model.pkl

   (or set `SENTINEL_QR_MODEL_PATH` to point elsewhere)

3. That's it — `verify_qr` automatically loads it and adds
   `ml_malicious_probability` / `ml_flag` to its output, and `policy.py`
   folds the probability into the overall risk score (up to +40 points).
   If the file isn't present, the app keeps working on the rule-based
   checks alone — no model required to run the demo.
