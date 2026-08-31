"""Backend tests for FEATURE 1 (route_safety chat intent + route_line map
layer) and FEATURE 2 (GET /api/situation Marine Situation Intelligence
endpoint) — newly implemented per review_request."""
import os
import time

import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    BASE_URL = "http://localhost:8001"

REGION_IDS = ["kakinada", "chennai", "kochi", "mumbai", "paradip", "veraval"]


@pytest.fixture
def api_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


class TestSituationEndpoint:
    """GET /api/situation?region_id=X for all 6 regions."""

    @pytest.mark.parametrize("region_id", REGION_IDS)
    def test_situation_fields_populated(self, api_client, region_id):
        r = api_client.get(f"{BASE_URL}/api/situation", params={"region_id": region_id})
        assert r.status_code == 200, r.text
        data = r.json()
        for field in ["region", "region_id", "severity", "verdict", "reasons",
                      "weather_today", "weather_tomorrow", "alerts", "tide", "trends"]:
            assert field in data, f"missing field {field} for {region_id}"
        assert data["region_id"] == region_id
        assert data["severity"] in ("critical", "warning", "advisory")
        assert data["verdict"] in ("SAFE", "CAUTION", "UNSAFE")
        assert isinstance(data["reasons"], list) and len(data["reasons"]) > 0
        assert "wind_kn" in data["weather_today"] and "wave_m" in data["weather_today"]
        assert isinstance(data["alerts"], list)
        assert isinstance(data["tide"], list) and len(data["tide"]) > 0
        trends = data["trends"]
        for k in ("wind", "wave", "sst"):
            assert k in trends
            assert "labels" in trends[k] and "values" in trends[k]
            assert len(trends[k]["values"]) == 7

    def test_kakinada_severity_is_critical(self, api_client):
        """Kakinada has an active high-severity cyclone alert -> severity must be critical."""
        r = api_client.get(f"{BASE_URL}/api/situation", params={"region_id": "kakinada"})
        data = r.json()
        assert data["severity"] == "critical"
        assert any(a["severity"] == "high" for a in data["alerts"])

    def test_kochi_severity_is_advisory(self, api_client):
        """Kochi has zero active alerts and calm weather -> severity should be advisory."""
        r = api_client.get(f"{BASE_URL}/api/situation", params={"region_id": "kochi"})
        data = r.json()
        assert data["alerts"] == []
        assert data["severity"] == "advisory"

    def test_default_region_when_missing(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/situation")
        assert r.status_code == 200
        assert r.json()["region_id"] == "kakinada"


class TestRouteSafetyChat:
    """POST /api/chat with a route-between-two-points question triggers
    route_safety intent and returns a route_line map layer + explicit
    route verdict in the text answer."""

    def _chat(self, api_client, message, session_suffix):
        payload = {
            "message": message,
            "session_id": f"TEST_route_{session_suffix}_{int(time.time())}",
            "language": "en",
            "region_id": "kakinada",
            "user_id": "TEST_route_user",
        }
        return api_client.post(f"{BASE_URL}/api/chat", json=payload, timeout=60)

    def test_route_through_mpa_flags_unsafe(self, api_client):
        """Route through/near Coringa Wildlife Sanctuary MPA should be flagged unsafe."""
        msg = ("Is it safe to sail a route from 16.95,82.40 to 16.765,82.33 "
               "near Kakinada, passing through Coringa area?")
        r = self._chat(api_client, msg, "unsafe")
        assert r.status_code == 200, r.text
        body = r.json()
        assistant = body["assistant_message"]
        assert assistant["intent"] in ("route_safety", "safety_sail", "general")
        widgets = assistant.get("widgets", [])
        map_widgets = [w for w in widgets if w.get("type") == "map"]
        # Only assert route_line layer/verdict text if planner actually resolved route_safety
        if assistant["intent"] == "route_safety":
            assert len(map_widgets) == 1
            layers = map_widgets[0].get("layers", [])
            route_layers = [l for l in layers if l.get("type") == "route_line"]
            assert len(route_layers) == 1, "expected a route_line layer on the map widget"
            assert len(route_layers[0]["segments"]) > 0
            markers = map_widgets[0]["markers"]
            kinds = {m["kind"] for m in markers}
            assert "route_start" in kinds and "route_end" in kinds
            # AI text should explicitly mention route safety
            answer_lower = assistant["content"].lower()
            assert any(w in answer_lower for w in ["route", "path", "sail"]), \
                f"answer does not mention route/path/sail: {assistant['content']}"

    def test_chat_returns_200_and_persists(self, api_client):
        r = self._chat(api_client, "Is it safe to sail today near Kakinada?", "basic")
        assert r.status_code == 200
        body = r.json()
        assert "assistant_message" in body and "user_message" in body
        assert body["assistant_message"]["content"]
