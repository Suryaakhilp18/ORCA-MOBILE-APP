"""Manual verification script for Hindi/romanized-Telugu localization (not part of pytest CI, run standalone)."""
import os
import uuid
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"

def chat(message, language=None):
    payload = {
        "message": message,
        "session_id": f"TEST_loc_{uuid.uuid4()}",
        "user_id": f"TEST_u_{uuid.uuid4().hex[:6]}",
        "location": {"lat": 16.98, "lon": 82.30},
    }
    if language:
        payload["language"] = language
    r = requests.post(f"{API}/chat", json=payload, timeout=90)
    print(f"\n=== Q: {message} ===")
    print("status:", r.status_code)
    if r.status_code == 200:
        d = r.json()
        am = d["assistant_message"]
        print("meta.language:", d.get("meta", {}).get("language"))
        print("verdict:", am.get("verdict"))
        print("content:", am.get("content"))
    else:
        print(r.text)

if __name__ == "__main__":
    chat("Is it safe to go to the sea tomorrow?", "hi")
    chat("Repu sea loki vellacha?")
