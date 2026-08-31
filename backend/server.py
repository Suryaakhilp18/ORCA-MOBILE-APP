"""ORCA backend — FastAPI modular monolith (India-wide coastal intelligence).

Modules: orchestrator/ (agents), gis/ (spatial), data_adapters/ (mock feeds,
now an India-wide region registry), notifications/ (hazard + geofence). Mongo
stands in for PostgreSQL/PostGIS as the authoritative spatial store — every
supported region's PFZ + boundary layer is seeded into the SAME collections,
so nearest-neighbour lookups resolve correctly nationwide by geography alone.
All safety verdicts are deterministic; the LLM only explains them.
"""
import asyncio
import logging
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, FastAPI, HTTPException, Query, Request
from pydantic import BaseModel
from starlette.middleware.cors import CORSMiddleware

from data_adapters import mock_region as mr
from db import clean, db
from gis import spatial
from notifications import service as notif
from orchestrator import agents

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("orca")

app = FastAPI(title="ORCA API")
api = APIRouter(prefix="/api")

# ---- simple in-memory rate limiter (per client) for the LLM-backed chat ----
_HITS: dict[str, list[float]] = defaultdict(list)
CHAT_LIMIT = 20          # requests
CHAT_WINDOW = 60         # seconds


def _rate_limited(key: str) -> bool:
    now = time.time()
    hits = [t for t in _HITS[key] if now - t < CHAT_WINDOW]
    hits.append(now)
    _HITS[key] = hits
    return len(hits) > CHAT_LIMIT


# ---- Nominatim geocoding: app-wide 1 req/sec throttle per usage policy -----
_GEOCODE_LOCK = asyncio.Lock()
_last_geocode_at = 0.0
GEOCODE_USER_AGENT = "ORCA-MarineIntelligence/1.0 (Emergent demo; India coastal app)"


# --------------------------------- models -----------------------------------
class Location(BaseModel):
    name: str | None = None
    lat: float
    lon: float


class ChatRequest(BaseModel):
    message: str
    session_id: str
    language: str | None = None
    location: Location | None = None
    region_id: str | None = None
    user_id: str = "demo-user"


class SaveLocationRequest(BaseModel):
    name: str
    lat: float
    lon: float
    user_id: str = "demo-user"
    is_vessel: bool = False


class GeofenceCheckRequest(BaseModel):
    name: str
    lat: float
    lon: float
    user_id: str = "demo-user"


class SubscribeRequest(BaseModel):
    location_id: str
    user_id: str = "demo-user"


# --------------------------------- health -----------------------------------
@api.get("/")
async def root():
    return {"service": "ORCA", "status": "ok", "region": mr.REGION,
            "coverage": "India-wide", "regions_available": len(mr.REGIONS)}


@api.get("/health")
async def health():
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}


# ---------------------------------- chat -------------------------------------
@api.post("/chat")
async def chat(req: ChatRequest, request: Request):
    client_key = req.user_id or (request.client.host if request.client else "anon")
    if _rate_limited(client_key):
        raise HTTPException(status_code=429,
                            detail="Too many requests. Please wait a moment.")

    # Build conversation context from stored history
    convo = await db.conversations.find_one({"session_id": req.session_id})
    history = convo["messages"] if convo else []
    context = "\n".join(f"{m['role']}: {m['content']}" for m in history[-6:])

    user_loc = req.location.dict() if req.location else None

    try:
        result = await agents.orchestrate(req.session_id, req.message,
                                          context, user_loc, req.region_id,
                                          req.language)
    except Exception as e:  # explicit safe-default on any failure
        logger.exception("orchestrator failed")
        fallback_region = mr.get_region(req.region_id)
        result = {
            "answer": ("Could not verify current marine conditions right now. "
                       "Do not assume it is safe — please check local advisories."),
            "verdict": None, "language": req.language or "en", "intent": "general",
            "citations": [], "widgets": [], "reasoning_trace": [
                {"agent": "System", "detail": f"Pipeline error: {type(e).__name__}"}],
            "location": user_loc or fallback_region["center"],
            "region": fallback_region, "elapsed_ms": 0, "error": True,
        }

    # persist both turns
    now = datetime.now(timezone.utc).isoformat()
    user_msg = {"id": str(uuid.uuid4()), "role": "user",
                "content": req.message, "created_at": now}
    ai_msg = {"id": str(uuid.uuid4()), "role": "assistant",
              "content": result["answer"], "created_at": now,
              "verdict": result.get("verdict"),
              "citations": result.get("citations", []),
              "widgets": result.get("widgets", []),
              "reasoning_trace": result.get("reasoning_trace", []),
              "intent": result.get("intent"),
              "region": result.get("region")}
    await db.conversations.update_one(
        {"session_id": req.session_id},
        {"$push": {"messages": {"$each": [user_msg, ai_msg]}},
         "$setOnInsert": {"session_id": req.session_id,
                          "user_id": req.user_id, "created_at": now}},
        upsert=True,
    )
    return {"user_message": user_msg, "assistant_message": ai_msg,
            "meta": {"elapsed_ms": result.get("elapsed_ms"),
                     "language": result.get("language"),
                     "region": result.get("region")}}


@api.get("/conversations/{session_id}")
async def get_conversation(session_id: str):
    convo = await db.conversations.find_one({"session_id": session_id})
    if not convo:
        return {"session_id": session_id, "messages": []}
    return clean(convo)


# ------------------------------ saved locations ------------------------------
@api.post("/locations")
async def save_location(req: SaveLocationRequest):
    doc = {"id": str(uuid.uuid4()), "name": req.name, "lat": req.lat,
           "lon": req.lon, "user_id": req.user_id, "is_vessel": req.is_vessel,
           "subscribed": True,
           "created_at": datetime.now(timezone.utc).isoformat()}
    await db.locations.insert_one(doc)
    # auto-evaluate hazards for the newly saved location
    await notif.evaluate_location_hazards(req.user_id,
                                          {"name": req.name, "lat": req.lat,
                                           "lon": req.lon})
    return clean(doc)


@api.get("/locations")
async def list_locations(user_id: str = "demo-user"):
    out = []
    async for doc in db.locations.find({"user_id": user_id}).sort("created_at", -1):
        out.append(clean(doc))
    return out


@api.delete("/locations/{location_id}")
async def delete_location(location_id: str):
    await db.locations.update_one(
        {"id": location_id},
        {"$set": {"deleted_at": datetime.now(timezone.utc).isoformat()}})
    # soft delete: hide by removing from active list
    await db.locations.delete_one({"id": location_id})
    return {"deleted": True, "id": location_id}


# ---------------------------------- alerts -----------------------------------
@api.get("/alerts")
async def get_alerts(region_id: str | None = None):
    r = mr.get_region(region_id)
    return {"region": f"{r['name']}, {r['state']}", "region_id": r["id"],
            "alerts": mr.get_active_alerts(region_id)}


@api.get("/notifications")
async def get_notifications(user_id: str = "demo-user"):
    return await notif.list_notifications(user_id)


# --------------------------------- geofence ----------------------------------
@api.post("/geofence/check")
async def geofence_check(req: GeofenceCheckRequest):
    return await notif.check_geofence_breach(req.user_id, req.name,
                                             req.lat, req.lon)


# ----------------------------- reference data --------------------------------
@api.get("/data/boundaries")
async def data_boundaries(region_id: str | None = None):
    return {"source": "Bundled maritime boundary layer", "is_mock": True,
            "boundaries": mr.get_boundaries(region_id)}


@api.get("/data/pfz")
async def data_pfz(region_id: str | None = None):
    return mr.get_pfz_advisory(region_id)


@api.get("/data/ocean")
async def data_ocean(region_id: str | None = None):
    return {"grid": mr.get_sst_chl_grid(region_id),
            "sst_trend": mr.get_sst_trend(region_id),
            "chl_trend": mr.get_chl_trend(region_id)}


@api.get("/region")
async def region(region_id: str | None = None):
    return mr.get_region(region_id)


# ------------------------- India-wide region registry -------------------------
@api.get("/regions")
async def regions():
    return {"regions": mr.list_regions(), "default_region_id": mr.DEFAULT_REGION_ID}


@api.get("/regions/detect")
async def regions_detect(lat: float, lon: float):
    region_cfg, distance_km = mr.nearest_region(lat, lon)
    return {"region": region_cfg, "distance_km": distance_km}


# ------------------------------ location search ------------------------------
@api.get("/geocode")
async def geocode(q: str = Query(min_length=2, max_length=200), limit: int = 5):
    """Forward-geocode a free-text place name to coordinates (India-biased).

    Proxies OpenStreetMap Nominatim with an app-wide 1 req/sec throttle,
    identifying User-Agent and a Mongo cache — per Nominatim's usage policy.
    User-triggered search only (no autocomplete/typeahead).
    """
    global _last_geocode_at
    query = q.strip()
    cache_key = query.lower()

    cached = await db.geocode_cache.find_one({"cache_key": cache_key})
    if cached:
        return {"query": query, "results": cached["results"], "cached": True,
                "attribution": "© OpenStreetMap contributors"}

    async with _GEOCODE_LOCK:
        wait = 1.0 - (time.time() - _last_geocode_at)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_geocode_at = time.time()
        try:
            async with httpx.AsyncClient(
                timeout=10, headers={"User-Agent": GEOCODE_USER_AGENT},
            ) as client:
                resp = await client.get(
                    "https://nominatim.openstreetmap.org/search",
                    params={"q": query, "format": "jsonv2", "addressdetails": 0,
                           "countrycodes": "in", "limit": limit},
                )
                resp.raise_for_status()
                raw = resp.json()
        except Exception:
            logger.exception("geocode upstream failed")
            raise HTTPException(status_code=502,
                                detail="Location search temporarily unavailable")

    results = [{"display_name": item["display_name"], "lat": float(item["lat"]),
               "lon": float(item["lon"]), "type": item.get("type")}
              for item in raw]
    await db.geocode_cache.update_one(
        {"cache_key": cache_key},
        {"$set": {"cache_key": cache_key, "query": query, "results": results,
                  "created_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    return {"query": query, "results": results, "cached": False,
            "attribution": "© OpenStreetMap contributors"}


app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await spatial.seed_spatial(mr.all_boundaries_all_regions(), mr.all_pfz_zones())
    await db.geocode_cache.create_index("cache_key", unique=True)
    await db.geocode_cache.create_index("created_at", expireAfterSeconds=2592000)
    logger.info("ORCA nationwide spatial reference data seeded "
               f"({len(mr.REGIONS)} regions: {', '.join(mr.REGIONS)}).")


@app.on_event("shutdown")
async def shutdown():
    from db import client
    client.close()
