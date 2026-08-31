"""PFZ (Potential Fishing Zone) regression tests across all 6 regions.
Investigates user complaint: 'not even able to locate one PFZ'.
Covers: GET /api/data/pfz per region, POST /api/chat pfz_nearest intent per region,
and region_id threading verification.
"""
import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "").rstrip("/")
REGIONS = ["kakinada", "chennai", "kochi", "mumbai", "paradip", "veraval"]


@pytest.fixture
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


class TestPFZDataEndpoint:
    """GET /api/data/pfz?region_id=X for each of the 6 regions."""

    @pytest.mark.parametrize("region_id", REGIONS)
    def test_pfz_data_non_empty_per_region(self, api_client, region_id):
        resp = api_client.get(f"{BASE_URL}/api/data/pfz", params={"region_id": region_id})
        assert resp.status_code == 200, f"{region_id}: {resp.status_code} {resp.text}"
        data = resp.json()
        assert data["region_id"] == region_id
        assert isinstance(data["zones"], list) and len(data["zones"]) > 0, f"{region_id} has no zones"
        z = data["zones"][0]
        assert "lat" in z and "lon" in z and "name" in z


class TestPFZChatIntent:
    """POST /api/chat with a PFZ query, per region, verifying real (non-empty,
    non-error) zone info threads through region_id correctly."""

    @pytest.mark.parametrize("region_id", REGIONS)
    def test_pfz_nearest_chat_per_region(self, api_client, region_id):
        session_id = f"TEST_pfz_{region_id}_{uuid.uuid4().hex[:6]}"
        # Get region center to send as location, mirroring frontend behavior
        region_resp = api_client.get(f"{BASE_URL}/api/region", params={"region_id": region_id})
        assert region_resp.status_code == 200
        center = region_resp.json()["center"]

        payload = {
            "message": "Where is the nearest Potential Fishing Zone today?",
            "session_id": session_id,
            "language": "en",
            "location": {"name": region_id, "lat": center["lat"], "lon": center["lon"]},
            "region_id": region_id,
            "user_id": "TEST_pfz_user",
        }
        resp = api_client.post(f"{BASE_URL}/api/chat", json=payload)
        assert resp.status_code == 200, f"{region_id}: {resp.status_code} {resp.text}"
        body = resp.json()
        ai_msg = body["assistant_message"]
        assert ai_msg["content"], f"{region_id}: empty AI answer"
        # Should not be an error/fallback pipeline response
        assert body["meta"]["region"]["id"] == region_id, (
            f"{region_id}: response region mismatch -> {body['meta']['region']}"
        )
        # widgets should include a map widget with pfz markers
        widgets = ai_msg.get("widgets", [])
        map_widgets = [w for w in widgets if w.get("type") == "map"]
        assert map_widgets, f"{region_id}: no map widget returned"
        markers = map_widgets[0].get("markers", [])
        pfz_markers = [m for m in markers if m.get("kind") == "pfz"]
        assert pfz_markers, f"{region_id}: no PFZ markers in map widget -> markers={markers}"
        print(f"{region_id}: PFZ markers found = {[m['label'] for m in pfz_markers]}")


class TestRegionIdThreading:
    """Confirm switching region_id changes returned region data (no hardcoded
    default fallback silently overriding user's selection)."""

    def test_alerts_region_id_threading(self, api_client):
        r1 = api_client.get(f"{BASE_URL}/api/alerts", params={"region_id": "mumbai"})
        r2 = api_client.get(f"{BASE_URL}/api/alerts", params={"region_id": "kochi"})
        assert r1.status_code == 200 and r2.status_code == 200
        assert r1.json()["region_id"] == "mumbai"
        assert r2.json()["region_id"] == "kochi"
        assert r1.json()["region_id"] != r2.json()["region_id"]

    def test_chat_region_id_not_hardcoded_to_default(self, api_client):
        """Sends region_id=veraval (non-default) and confirms response region
        is veraval, not silently falling back to kakinada (DEFAULT_REGION_ID)."""
        session_id = f"TEST_regioncheck_{uuid.uuid4().hex[:6]}"
        center = {"lat": 20.9159, "lon": 70.3629}  # veraval center
        payload = {
            "message": "What is the weather today?",
            "session_id": session_id,
            "language": "en",
            "location": {"name": "veraval", **center},
            "region_id": "veraval",
            "user_id": "TEST_regioncheck_user",
        }
        resp = api_client.post(f"{BASE_URL}/api/chat", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["region"]["id"] == "veraval", (
            f"Expected veraval, got {body['meta']['region']}"
        )
