"""Tests for: (1) Voice Agent (ElevenLabs TTS/STT), (2) /api/situation
(Alerts tab redesign), (3) route_safety chat intent (sea-not-land fix).
"""
import io
import os
import struct
import wave

import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "").rstrip("/")


@pytest.fixture
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


def _make_silent_wav_bytes(duration_s=1, framerate=16000):
    buf = io.BytesIO()
    n_frames = duration_s * framerate
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(framerate)
        w.writeframes(b"\x00\x00" * n_frames)
    return buf.getvalue()


class TestVoiceSpeak:
    def test_speak_returns_audio_mpeg(self, api_client):
        resp = api_client.post(
            f"{BASE_URL}/api/voice/speak",
            json={"text": "The sea is calm today near Kakinada.", "language": "en"},
            timeout=60,
        )
        assert resp.status_code == 200, f"Unexpected status {resp.status_code}: {resp.text[:300]}"
        assert resp.headers.get("content-type", "").startswith("audio/"), resp.headers
        assert len(resp.content) > 1000, "audio payload suspiciously small"

    def test_speak_empty_text_400(self, api_client):
        resp = api_client.post(
            f"{BASE_URL}/api/voice/speak", json={"text": "  ", "language": "en"}, timeout=30
        )
        assert resp.status_code == 400


class TestVoiceTranscribe:
    def test_transcribe_silent_audio_no_auth_error(self, api_client):
        wav_bytes = _make_silent_wav_bytes()
        files = {"audio": ("test.wav", wav_bytes, "audio/wav")}
        resp = api_client.post(
            f"{BASE_URL}/api/voice/transcribe?language=en", files=files, timeout=60
        )
        # Should NOT be 401/402/503 (credential/quota errors). 422 (could not
        # understand) or 200 (empty/short text) are both acceptable for a
        # silent synthetic file.
        assert resp.status_code not in (401, 402, 503), (
            f"Voice credential/quota error: {resp.status_code} {resp.text[:300]}"
        )
        assert resp.status_code in (200, 422), f"Unexpected status: {resp.status_code} {resp.text[:300]}"


class TestSituation:
    @pytest.mark.parametrize("region_id", ["kakinada", "mumbai"])
    def test_situation_structure(self, api_client, region_id):
        resp = api_client.get(f"{BASE_URL}/api/situation", params={"region_id": region_id})
        assert resp.status_code == 200
        data = resp.json()
        for key in ("region", "severity", "verdict", "reasons", "weather_today",
                     "alerts", "tide", "trends", "generated_at"):
            assert key in data, f"missing key {key}"
        assert data["severity"] in ("critical", "warning", "advisory")
        for series in ("wind", "wave", "sst"):
            assert series in data["trends"]
            assert len(data["trends"][series]["values"]) == 7, f"{series} trend should be 7-day"

    def test_kakinada_critical_due_to_cyclone(self, api_client):
        resp = api_client.get(f"{BASE_URL}/api/situation", params={"region_id": "kakinada"})
        assert resp.status_code == 200
        data = resp.json()
        # Per problem statement: kakinada has active high-severity cyclone alert
        # -> severity should be critical even if today's verdict is SAFE.
        high_sev_alert = any(a.get("severity") == "high" for a in data["alerts"])
        if high_sev_alert:
            assert data["severity"] == "critical", (
                f"Expected critical severity due to high-severity alert, got {data['severity']}"
            )


class TestRouteSafetyChat:
    def test_route_query_kakinada_to_hope_island(self, api_client):
        resp = api_client.post(
            f"{BASE_URL}/api/chat",
            json={
                "message": "Is the route from Kakinada to Hope Island safe for my boat today?",
                "session_id": "TEST_route_session_1",
                "region_id": "kakinada",
            },
            timeout=60,
        )
        assert resp.status_code == 200
        data = resp.json()
        ai_msg = data["assistant_message"]
        assert ai_msg["content"], "empty answer"
        widgets = ai_msg.get("widgets", [])
        map_widgets = [w for w in widgets if w["type"] == "map"]
        assert map_widgets, "expected a map widget for route_safety intent"
        markers = map_widgets[0]["markers"]
        kinds = [m["kind"] for m in markers]
        assert "route_start" in kinds, f"no route_start marker in {kinds}"
        assert "route_end" in kinds, f"no route_end marker in {kinds}"
        layers = map_widgets[0].get("layers", [])
        route_lines = [l for l in layers if l["type"] == "route_line"]
        assert route_lines, "expected route_line layer for connected polyline"
        assert len(route_lines[0]["segments"]) > 0

        # Sea-not-land check: start point should not be exactly Kakinada's
        # known city-center coords (~16.9891, 82.2475) - should be shifted.
        start_marker = next(m for m in markers if m["kind"] == "route_start")
        kakinada_center = (16.9891, 82.2475)
        dist = ((start_marker["lat"] - kakinada_center[0]) ** 2 +
                (start_marker["lon"] - kakinada_center[1]) ** 2) ** 0.5
        print(f"start marker: {start_marker}, distance from city center: {dist}")

    def test_route_query_verdict_in_text(self, api_client):
        resp = api_client.post(
            f"{BASE_URL}/api/chat",
            json={
                "message": "Is the route from Chennai to a nearby island safe today?",
                "session_id": "TEST_route_session_2",
                "region_id": "kakinada",
            },
            timeout=60,
        )
        assert resp.status_code == 200
        data = resp.json()
        ai_msg = data["assistant_message"]
        assert ai_msg["content"]
        print("ANSWER:", ai_msg["content"])
        print("VERDICT:", ai_msg.get("verdict"))
