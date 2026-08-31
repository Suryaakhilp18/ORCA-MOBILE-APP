"""Notifications module.

Evaluates active hazard bulletins + geofence breaches against saved user
locations and records notifications. This is the correct push-style pattern
(polled/pushed), NOT a persistent socket. FCM can plug into `send_push` on a
native build; in Expo Go we surface these as in-app notifications the client
polls.
"""
import uuid
from datetime import datetime, timezone

from data_adapters import mock_region as mr
from db import clean, db
from gis import spatial


async def send_push(token: str, title: str, body: str) -> bool:
    """FCM hook (no-op without server key / native build). Structured so a real
    FCM call can drop in here later."""
    return False


async def _record(user_id: str, notif: dict) -> dict:
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "read": False,
        **notif,
    }
    await db.notifications.insert_one(doc)
    return clean(doc)


async def evaluate_location_hazards(user_id: str, location: dict) -> list[dict]:
    """Match active IMD alerts to a saved location and record notifications.

    Region-aware: resolves the nearest supported coastal region to the saved
    point (India-wide) rather than always using the demo default.
    """
    created = []
    region, _dist_km = mr.nearest_region(location["lat"], location["lon"])
    for a in mr.get_active_alerts(region["id"]):
        notif = {
            "type": a["type"],
            "severity": a["severity"],
            "title": a["title"],
            "body": a["body"],
            "source": a["source"],
            "location_name": location.get("name"),
            "kind": "hazard",
        }
        created.append(await _record(user_id, notif))
    return created


async def check_geofence_breach(user_id: str, name: str, lat: float,
                                lon: float) -> dict:
    """Foreground-demonstrable geofence trigger."""
    breaches = await spatial.geofence_check(lat, lon)
    restricted = [b for b in breaches if b.get("restricted")]
    notifs = []
    for b in restricted:
        notif = {
            "type": "geofence",
            "severity": "high",
            "title": f"Geofence breach: {b['name']}",
            "body": (f"Location '{name}' ({lat:.4f}, {lon:.4f}) is inside "
                     f"{b['name']}. {b.get('note', '')}"),
            "source": "PostGIS boundary check",
            "location_name": name,
            "kind": "geofence",
        }
        notifs.append(await _record(user_id, notif))
    return {"breach": len(restricted) > 0, "zones": restricted,
            "notifications": notifs}


async def list_notifications(user_id: str) -> list[dict]:
    out = []
    async for doc in db.notifications.find({"user_id": user_id}).sort("created_at", -1):
        out.append(clean(doc))
    return out
