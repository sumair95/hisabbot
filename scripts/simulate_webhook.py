"""
Send a simulated WhatsApp webhook payload to the locally running server.

Usage:
    # First, start the server in another terminal:
    #   uvicorn app.main:app --reload --port 8000
    python scripts/simulate_webhook.py "Ahmed ko 500 udhaar diya"
"""
import json
import sys
import uuid
import httpx

URL = "http://localhost:8000/webhook/whatsapp"
FROM_PHONE = "923001234567"  # your test number, without '+'


def build_text_payload(body: str) -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "test_entry",
            "changes": [{
                "field": "messages",
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {
                        "display_phone_number": "15555551234",
                        "phone_number_id": "TEST_PHONE_NUMBER_ID",
                    },
                    "contacts": [{
                        "profile": {"name": "Test Shop"},
                        "wa_id": FROM_PHONE,
                    }],
                    "messages": [{
                        "from": FROM_PHONE,
                        "id": f"wamid.test.{uuid.uuid4().hex[:16]}",
                        "timestamp": "1712345678",
                        "type": "text",
                        "text": {"body": body},
                    }],
                },
            }],
        }],
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/simulate_webhook.py <message>")
        sys.exit(1)
    body = " ".join(sys.argv[1:])
    payload = build_text_payload(body)
    r = httpx.post(URL, json=payload, timeout=30)
    print(f"HTTP {r.status_code}")
    print(r.text)


if __name__ == "__main__":
    main()
