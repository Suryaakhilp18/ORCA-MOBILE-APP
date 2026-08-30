"""Spatial queries backed by MongoDB 2dsphere indexes (PostGIS equivalent)."""
from db import clean, db


async def ensure_indexes():
    await db.boundaries.create_index([("geometry", "2dsphere")])
    await db.pfz.create_index([("location", "2dsphere")])


async def seed_spatial(boundaries: list[dict], pfz_zones: list[dict]):
    """Idempotently upsert bundled reference data (no destructive deletes)."""
    for b in boundaries:
        await db.boundaries.update_one({"key": b["key"]}, {"$set": b}, upsert=True)
    for z in pfz_zones:
        doc = {
            **z,
            "location": {"type": "Point", "coordinates": [z["lon"], z["lat"]]},
        }
        await db.pfz.update_one({"key": z["key"]}, {"$set": doc}, upsert=True)
    await ensure_indexes()


async def nearest_pfz(lat: float, lon: float, limit: int = 3) -> list[dict]:
    """Nearest Potential Fishing Zones, sorted by great-circle distance."""
    pipeline = [
        {"$geoNear": {
            "near": {"type": "Point", "coordinates": [lon, lat]},
            "distanceField": "distance_m",
            "spherical": True,
            "key": "location",
        }},
        {"$limit": limit},
    ]
    out = []
    async for doc in db.pfz.aggregate(pipeline):
        d = clean(doc)
        d["distance_km"] = round(d.pop("distance_m", 0) / 1000, 1)
        d.pop("location", None)
        out.append(d)
    return out


async def geofence_check(lat: float, lon: float) -> list[dict]:
    """Return every boundary polygon that contains the point (breaches)."""
    point = {"type": "Point", "coordinates": [lon, lat]}
    cursor = db.boundaries.find(
        {"geometry": {"$geoIntersects": {"$geometry": point}}}
    )
    breaches = []
    async for doc in cursor:
        d = clean(doc)
        d.pop("geometry", None)
        breaches.append(d)
    return breaches


async def all_boundaries() -> list[dict]:
    out = []
    async for doc in db.boundaries.find():
        out.append(clean(doc))
    return out


def _interp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


async def route_safety(start: dict, end: dict, samples: int = 6) -> dict:
    """Sample points along a straight route and flag unsafe segments.

    A segment is unsafe if it enters a restricted/MPA boundary polygon.
    Weather-driven hazard is layered on by the orchestrator.
    """
    segments = []
    unsafe = 0
    for i in range(samples + 1):
        t = i / samples
        lat = round(_interp(start["lat"], end["lat"], t), 4)
        lon = round(_interp(start["lon"], end["lon"], t), 4)
        breaches = await geofence_check(lat, lon)
        restricted = [b for b in breaches if b.get("restricted")]
        is_unsafe = len(restricted) > 0
        if is_unsafe:
            unsafe += 1
        segments.append({
            "lat": lat, "lon": lon,
            "safe": not is_unsafe,
            "reason": (restricted[0]["name"] if restricted else None),
        })
    return {"segments": segments, "unsafe_count": unsafe,
            "total": len(segments)}
