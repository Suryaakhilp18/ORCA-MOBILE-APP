"""ORCA backend regression tests — covers chat, spatial, alerts, saved locs."""
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL",
                          "https://coastal-intel.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# --------------------------- health / reference -----------------------------
class TestHealth:
    def test_health(self, client):
        r = client.get(f"{API}/health", timeout=15)
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_boundaries(self, client):
        r = client.get(f"{API}/data/boundaries", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data["is_mock"] is True
        assert len(data["boundaries"]) == 3
        for b in data["boundaries"]:
            assert "geometry" in b and "name" in b

    def test_pfz(self, client):
        r = client.get(f"{API}/data/pfz", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data["source"].startswith("INCOIS")
        assert len(data["zones"]) >= 3


# ------------------------------- chat ---------------------------------------
class TestChat:
    def test_flagship_safety_unsafe(self, client):
        payload = {
            "message": "Is it safe to venture into the sea tomorrow morning?",
            "session_id": f"TEST_sess_{uuid.uuid4()}",
            "language": "en",
            "location": {"lat": 16.98, "lon": 82.30},
            "user_id": f"TEST_u_{uuid.uuid4().hex[:6]}",
        }
        r = client.post(f"{API}/chat", json=payload, timeout=90)
        assert r.status_code == 200, r.text
        data = r.json()
        am = data["assistant_message"]
        assert am["verdict"] == "UNSAFE"
        assert am["content"].strip() != ""
        assert len(am["citations"]) > 0
        agents = [t["agent"] for t in am["reasoning_trace"]]
        # 7 pipeline agents required
        assert any("Planner" in a for a in agents)
        assert any("Synthesizer" in a for a in agents)
        assert any("Data Discovery" in a for a in agents)
        assert any("Weather Intelligence" in a for a in agents)
        assert any("Geospatial" in a for a in agents)
        assert any("Reporting" in a for a in agents)
        assert any(w.get("type") == "map" for w in am["widgets"])

    def test_flagship_pfz(self, client):
        payload = {
            "message": "Where is the nearest Potential Fishing Zone today?",
            "session_id": f"TEST_sess_{uuid.uuid4()}",
            "language": "en",
            "location": {"lat": 16.98, "lon": 82.30},
            "user_id": f"TEST_u_{uuid.uuid4().hex[:6]}",
        }
        r = client.post(f"{API}/chat", json=payload, timeout=90)
        assert r.status_code == 200
        am = r.json()["assistant_message"]
        assert am["intent"] == "pfz_nearest"
        map_w = next((w for w in am["widgets"] if w["type"] == "map"), None)
        assert map_w and any(m.get("kind") == "pfz" for m in map_w["markers"])
        assert any("INCOIS" in c for c in am["citations"])

    def test_chat_telugu(self, client):
        payload = {
            "message": "రేపు ఉదయం సముద్రంలోకి వెళ్లడం సురక్షితమేనా?",
            "session_id": f"TEST_sess_{uuid.uuid4()}",
            "location": {"lat": 16.98, "lon": 82.30},
            "user_id": f"TEST_u_{uuid.uuid4().hex[:6]}",
        }
        r = client.post(f"{API}/chat", json=payload, timeout=90)
        assert r.status_code == 200
        body = r.json()
        assert body["meta"]["language"] == "te"
        assert body["assistant_message"]["verdict"] == "UNSAFE"

    def test_chat_chlorophyll_sst_two_charts(self, client):
        payload = {
            "message": "Which regions show high chlorophyll and favourable SST?",
            "session_id": f"TEST_sess_{uuid.uuid4()}",
            "user_id": f"TEST_u_{uuid.uuid4().hex[:6]}",
        }
        r = client.post(f"{API}/chat", json=payload, timeout=90)
        assert r.status_code == 200
        widgets = r.json()["assistant_message"]["widgets"]
        charts = [w for w in widgets if w["type"] == "chart"]
        assert len(charts) == 2

    def test_chat_alerts_query(self, client):
        payload = {
            "message": "Are there any lightning or cyclone alerts in my area?",
            "session_id": f"TEST_sess_{uuid.uuid4()}",
            "user_id": f"TEST_u_{uuid.uuid4().hex[:6]}",
        }
        r = client.post(f"{API}/chat", json=payload, timeout=90)
        assert r.status_code == 200
        am = r.json()["assistant_message"]
        assert am["intent"] == "alerts_query"

    def test_chat_persistence(self, client):
        sid = f"TEST_persist_{uuid.uuid4()}"
        payload = {"message": "current conditions?", "session_id": sid,
                   "user_id": f"TEST_u_{uuid.uuid4().hex[:6]}"}
        r = client.post(f"{API}/chat", json=payload, timeout=90)
        assert r.status_code == 200
        r2 = client.get(f"{API}/conversations/{sid}", timeout=15)
        assert r2.status_code == 200
        msgs = r2.json()["messages"]
        assert len(msgs) >= 2
        assert msgs[0]["role"] == "user"
        assert msgs[1]["role"] == "assistant"

    def test_rate_limit(self, client):
        """Burst 25 concurrent requests -> at least one must be 429."""
        from concurrent.futures import ThreadPoolExecutor
        uid = f"TEST_ratelimit_{uuid.uuid4().hex[:8]}"

        def fire(i):
            try:
                r = requests.post(f"{API}/chat", json={
                    "message": "ping", "session_id": f"rl-{i}", "user_id": uid,
                }, timeout=90)
                return r.status_code
            except Exception:
                return -1

        with ThreadPoolExecutor(max_workers=25) as ex:
            codes = list(ex.map(fire, range(25)))
        assert 429 in codes, f"never rate-limited: {codes}"


# ------------------------------ alerts / notifs -----------------------------
class TestAlerts:
    def test_alerts_two_active(self, client):
        r = client.get(f"{API}/alerts", timeout=15)
        assert r.status_code == 200
        alerts = r.json()["alerts"]
        assert len(alerts) == 2
        types = {a["type"] for a in alerts}
        assert types == {"cyclone", "lightning"}

    def test_notifications_exist(self, client):
        uid = f"TEST_notif_{uuid.uuid4().hex[:8]}"
        # trigger a breach to create notification
        breach = client.post(f"{API}/geofence/check", json={
            "name": "test-vessel", "lat": 16.96, "lon": 82.31, "user_id": uid
        }, timeout=15)
        assert breach.status_code == 200
        r = client.get(f"{API}/notifications", params={"user_id": uid}, timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        assert len(r.json()) >= 1


# --------------------------------- geofence ---------------------------------
class TestGeofence:
    def test_breach_true(self, client):
        r = client.post(f"{API}/geofence/check", json={
            "name": "boat-A", "lat": 16.96, "lon": 82.31,
            "user_id": f"TEST_u_{uuid.uuid4().hex[:6]}",
        }, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data["breach"] is True
        names = " ".join(z["name"] for z in data["zones"]).lower()
        assert "port" in names or "restricted" in names

    def test_breach_false_offshore(self, client):
        r = client.post(f"{API}/geofence/check", json={
            "name": "boat-B", "lat": 17.05, "lon": 82.48,
            "user_id": f"TEST_u_{uuid.uuid4().hex[:6]}",
        }, timeout=15)
        assert r.status_code == 200
        assert r.json()["breach"] is False


# ---------------------------- saved locations -------------------------------
class TestLocations:
    def test_crud(self, client):
        uid = f"TEST_u_{uuid.uuid4().hex[:6]}"
        create = client.post(f"{API}/locations", json={
            "name": "TEST_spot", "lat": 16.99, "lon": 82.30, "user_id": uid,
        }, timeout=15)
        assert create.status_code == 200
        lid = create.json()["id"]
        # list
        lst = client.get(f"{API}/locations", params={"user_id": uid}, timeout=15)
        assert lst.status_code == 200
        assert any(l["id"] == lid for l in lst.json())
        # delete
        d = client.delete(f"{API}/locations/{lid}", timeout=15)
        assert d.status_code == 200
        lst2 = client.get(f"{API}/locations", params={"user_id": uid}, timeout=15)
        assert not any(l["id"] == lid for l in lst2.json())
