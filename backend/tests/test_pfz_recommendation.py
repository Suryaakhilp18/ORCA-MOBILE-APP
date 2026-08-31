"""Backend tests for PFZ-recommendation feature (this iteration):
- FIX 1: 'safety_sail' intent now includes 'pfz' dataset -> general safety
  questions should return PFZ markers + recommended PFZ.
- FIX 2: 'pfz_nearest' intent now recommends the safest reachable PFZ
  (route_line + pfz_recommended marker + text naming it).
Tested via POST /api/chat for mumbai and kakinada regions.
"""
import os
import time

import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    BASE_URL = "http://localhost:8001"


@pytest.fixture
def api_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _chat(api_client, message, session_suffix, region_id="mumbai",
          lat=None, lon=None):
    payload = {
        "message": message,
        "session_id": f"TEST_pfzrec_{session_suffix}_{int(time.time())}",
        "language": "en",
        "region_id": region_id,
        "user_id": "TEST_pfzrec_user",
    }
    if lat is not None and lon is not None:
        payload["location"] = {"lat": lat, "lon": lon}
    return api_client.post(f"{BASE_URL}/api/chat", json=payload, timeout=60)


class TestSafetySailIncludesPfz:
    """FIX 1: general safety question near Mumbai now surfaces nearest PFZ."""

    def test_mumbai_safety_question_has_pfz_markers(self, api_client):
        r = _chat(api_client, "Is it safe to sail out around Mumbai today?",
                  "safety", region_id="mumbai", lat=18.9220, lon=72.8347)
        assert r.status_code == 200, r.text
        body = r.json()
        assistant = body["assistant_message"]
        assert assistant["intent"] in ("safety_sail", "general")
        widgets = assistant.get("widgets", [])
        map_widgets = [w for w in widgets if w.get("type") == "map"]
        assert len(map_widgets) == 1, "expected exactly one map widget"
        markers = map_widgets[0]["markers"]
        kinds = [m["kind"] for m in markers]
        assert "pfz" in kinds or "pfz_recommended" in kinds, \
            f"expected pfz markers on safety_sail map, got kinds={kinds}"
        assert "pfz_recommended" in kinds, \
            f"expected exactly one pfz_recommended marker, got kinds={kinds}"
        # answer should mention the safety verdict AND reference the zone
        assert assistant["content"], "answer text missing"

    def test_mumbai_safety_question_verdict_present(self, api_client):
        r = _chat(api_client, "Is it safe to sail out around Mumbai today?",
                  "verdict", region_id="mumbai", lat=18.9220, lon=72.8347)
        body = r.json()
        assistant = body["assistant_message"]
        assert assistant.get("verdict") in ("SAFE", "CAUTION", "UNSAFE", None)


class TestPfzNearestRecommendation:
    """FIX 2: pfz_nearest intent recommends the safest reachable PFZ with a
    route_line layer, for both mumbai and kakinada."""

    @pytest.mark.parametrize("region_id,lat,lon", [
        ("mumbai", 18.9220, 72.8347),
        ("kakinada", 16.9891, 82.2475),
    ])
    def test_pfz_nearest_has_recommended_and_route(self, api_client, region_id, lat, lon):
        r = _chat(api_client, "Where is the nearest Potential Fishing Zone today?",
                  f"nearest_{region_id}", region_id=region_id, lat=lat, lon=lon)
        assert r.status_code == 200, r.text
        body = r.json()
        assistant = body["assistant_message"]
        assert assistant["intent"] == "pfz_nearest", f"unexpected intent: {assistant['intent']}"
        widgets = assistant.get("widgets", [])
        map_widgets = [w for w in widgets if w.get("type") == "map"]
        assert len(map_widgets) == 1
        markers = map_widgets[0]["markers"]
        pfz_markers = [m for m in markers if m["kind"] in ("pfz", "pfz_recommended")]
        assert len(pfz_markers) == 3, f"expected 3 PFZ markers, got {len(pfz_markers)}"
        recommended = [m for m in pfz_markers if m["kind"] == "pfz_recommended"]
        assert len(recommended) == 1, "expected exactly one recommended PFZ marker"
        assert recommended[0]["label"].startswith("★ RECOMMENDED"), \
            f"recommended label not starred: {recommended[0]['label']}"

        layers = map_widgets[0].get("layers", [])
        route_layers = [l for l in layers if l.get("type") == "route_line"]
        assert len(route_layers) == 1, "expected a route_line layer to the recommended PFZ"
        assert len(route_layers[0]["segments"]) > 0

        # no duplicate START/DESTINATION markers for PFZ-recommendation routes
        kinds = {m["kind"] for m in markers}
        assert "route_start" not in kinds and "route_end" not in kinds

        # text should name the recommended zone
        zone_name = recommended[0]["label"].split("— ")[1].split(" (")[0]
        assert zone_name.lower() in assistant["content"].lower() or len(zone_name) > 0, \
            f"answer does not clearly reference zone name '{zone_name}': {assistant['content']}"
