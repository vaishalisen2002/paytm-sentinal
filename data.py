"""Mock Paytm data. Swap for real APIs later; for the hackathon this is enough."""

MERCHANTS = {
    "M12345": {
        "name": "Sharma General Store",
        "registered_upi": "sharmageneral@paytm",
        "location": "Andheri, Mumbai",
        "typical_txn_range": (300, 1500),
    }
}

TRANSACTIONS = {
    # Customer paid a tampered QR: money went to a different UPI ID
    "TXN1001": {
        "merchant_id": "M12345",
        "amount": 500,
        "paid_to_upi": "sharmageneral@xyz",
        "merchant_received": False,
    },
    # Normal transaction (use to show Sentinel does NOT cry wolf)
    "TXN1002": {
        "merchant_id": "M12345",
        "amount": 800,
        "paid_to_upi": "sharmageneral@paytm",
        "merchant_received": True,
    },
}

# In-memory stores the tools write to (shown in the dashboard)
CASES: list[dict] = []
NOTIFICATIONS: list[dict] = []
PENDING_APPROVALS: list[dict] = []
