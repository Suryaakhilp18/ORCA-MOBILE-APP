"""MOCK data adapters for the demo coastal region: Kakinada, Andhra Pradesh.

Everything here is clearly labelled `is_mock: True` with a named `source`. Values
are realistic but synthetic. Ocean is to the east (Bay of Bengal).

Adapters (each mirrors a real EO / oceanographic source):
    - PFZ + tide            -> INCOIS
    - weather + cyclone     -> IMD
    - SST + chlorophyll grid -> ISRO / Bhuvan ocean-colour products
    - maritime boundaries    -> bundled static GeoJSON reference layer
"""
from datetime import datetime, timedelta, timezone

REGION = {
    "id": "kakinada",
    "name": "Kakinada, Andhra Pradesh",
    "center": {"lat": 16.9891, "lon": 82.2475},
    "coast_bearing": "east (Bay of Bengal)",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hours_ago(h: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=h)).isoformat()


# ---------------------------------------------------------------------------
# INCOIS adapter — Potential Fishing Zones + tide table
# ---------------------------------------------------------------------------
PFZ_ZONES = [
    {"key": "pfz-1", "name": "Kakinada Bay Mouth", "lat": 16.95, "lon": 82.40,
     "confidence": 0.86, "sst_c": 28.4, "chl_mg_m3": 2.1, "depth_m": 35,
     "species": "Mackerel, Sardine", "distance_note": "~18 km ESE of coast"},
    {"key": "pfz-2", "name": "Hope Island Shelf", "lat": 17.05, "lon": 82.48,
     "confidence": 0.78, "sst_c": 28.1, "chl_mg_m3": 1.8, "depth_m": 42,
     "species": "Tuna, Seer fish", "distance_note": "~30 km NE of coast"},
    {"key": "pfz-3", "name": "Uppada Deep", "lat": 17.12, "lon": 82.55,
     "confidence": 0.72, "sst_c": 27.9, "chl_mg_m3": 1.5, "depth_m": 60,
     "species": "Pomfret", "distance_note": "~42 km NE of coast"},
    {"key": "pfz-4", "name": "Coringa Offshore", "lat": 16.78, "lon": 82.42,
     "confidence": 0.69, "sst_c": 28.6, "chl_mg_m3": 2.4, "depth_m": 28,
     "species": "Prawn, Sardine", "distance_note": "~22 km SE of coast"},
]


def get_pfz_advisory() -> dict:
    return {
        "source": "INCOIS PFZ Advisory",
        "is_mock": True,
        "last_updated": _hours_ago(6),
        "region": REGION["name"],
        "zones": PFZ_ZONES,
    }


def get_tide_table() -> dict:
    return {
        "source": "INCOIS Tide Tables",
        "is_mock": True,
        "last_updated": _hours_ago(6),
        "region": REGION["name"],
        "events": [
            {"type": "High", "time": "05:42 IST", "height_m": 1.4},
            {"type": "Low", "time": "11:58 IST", "height_m": 0.3},
            {"type": "High", "time": "18:10 IST", "height_m": 1.6},
            {"type": "Low", "time": "23:47 IST", "height_m": 0.5},
        ],
    }


# ---------------------------------------------------------------------------
# IMD adapter — weather forecast + cyclone / lightning bulletins
# ---------------------------------------------------------------------------
FORECAST = {
    "today": {
        "label": "Today",
        "wind_kn": 14, "gust_kn": 20, "wave_m": 1.2,
        "condition": "Partly cloudy", "lightning_pct": 15,
        "cyclone": None,
    },
    "tomorrow": {
        "label": "Tomorrow morning",
        "wind_kn": 32, "gust_kn": 45, "wave_m": 3.1,
        "condition": "Squally thunderstorms", "lightning_pct": 70,
        "cyclone": "Deep Depression 'BOB-04' intensifying, approaching coast",
    },
}


def get_weather(timeframe: str = "today") -> dict:
    key = "tomorrow" if timeframe and "tomorrow" in timeframe.lower() else "today"
    fc = FORECAST[key]
    return {
        "source": "IMD Marine Weather Forecast",
        "is_mock": True,
        "last_updated": _hours_ago(3),
        "region": REGION["name"],
        "timeframe": key,
        **fc,
    }


def get_active_alerts() -> list[dict]:
    now = datetime.now(timezone.utc)
    return [
        {
            "key": "alert-cyclone-bob04",
            "type": "cyclone",
            "severity": "high",
            "title": "Cyclone Warning — Deep Depression BOB-04",
            "body": ("Deep Depression over west-central Bay of Bengal likely to "
                     "intensify into a cyclonic storm. Squally winds 45-55 kmph "
                     "gusting 65 kmph expected off Kakinada–Visakhapatnam coast "
                     "within 36 hours. Fishermen advised NOT to venture into sea."),
            "source": "IMD Cyclone Bulletin",
            "is_mock": True,
            "issued_at": _hours_ago(2),
            "valid_until": (now + timedelta(hours=36)).isoformat(),
            "region": REGION["name"],
        },
        {
            "key": "alert-lightning-01",
            "type": "lightning",
            "severity": "moderate",
            "title": "Lightning Alert — Offshore Kakinada",
            "body": ("Thunderstorms with frequent lightning likely offshore "
                     "Kakinada between 04:00–09:00 IST tomorrow. Avoid open-sea "
                     "activity during this window."),
            "source": "IMD Nowcast",
            "is_mock": True,
            "issued_at": _hours_ago(1),
            "valid_until": (now + timedelta(hours=18)).isoformat(),
            "region": REGION["name"],
        },
    ]


# ---------------------------------------------------------------------------
# ISRO / Bhuvan adapter — SST + chlorophyll grids and 7-day trends
# ---------------------------------------------------------------------------
def _grid():
    """A small synthetic SST/chlorophyll grid east of Kakinada."""
    base_lat, base_lon = 16.75, 82.35
    points = []
    for i in range(5):
        for j in range(5):
            lat = round(base_lat + i * 0.11, 4)
            lon = round(base_lon + j * 0.11, 4)
            # SST cooler further offshore; chl higher near coast upwelling
            sst = round(29.0 - j * 0.28 - i * 0.05, 2)
            chl = round(2.6 - j * 0.32 + (i % 2) * 0.15, 2)
            points.append({"lat": lat, "lon": lon, "sst_c": sst,
                           "chl_mg_m3": max(chl, 0.2)})
    return points


def get_sst_chl_grid() -> dict:
    return {
        "source": "ISRO / Bhuvan Ocean Colour (SST & Chlorophyll)",
        "is_mock": True,
        "last_updated": _hours_ago(8),
        "region": REGION["name"],
        "grid": _grid(),
    }


def get_sst_trend() -> dict:
    days = [(datetime.now(timezone.utc) - timedelta(days=d)).strftime("%d %b")
            for d in range(6, -1, -1)]
    return {
        "source": "ISRO / Bhuvan SST time-series",
        "is_mock": True,
        "last_updated": _hours_ago(8),
        "unit": "°C",
        "labels": days,
        "values": [28.9, 28.7, 28.6, 28.5, 28.4, 28.3, 28.4],
    }


def get_chl_trend() -> dict:
    days = [(datetime.now(timezone.utc) - timedelta(days=d)).strftime("%d %b")
            for d in range(6, -1, -1)]
    return {
        "source": "ISRO / Bhuvan Chlorophyll time-series",
        "is_mock": True,
        "last_updated": _hours_ago(8),
        "unit": "mg/m³",
        "labels": days,
        "values": [1.2, 1.4, 1.6, 1.9, 2.1, 2.2, 2.1],
    }


# ---------------------------------------------------------------------------
# Bundled maritime boundary reference layer (static GeoJSON) -> PostGIS/Mongo
# ---------------------------------------------------------------------------
BOUNDARIES = [
    {
        "key": "mpa-coringa",
        "name": "Coringa Wildlife Sanctuary (MPA)",
        "kind": "mpa",
        "restricted": True,
        "note": "Protected mangrove marine sanctuary — fishing restricted.",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [82.24, 16.70], [82.42, 16.70], [82.42, 16.83],
                [82.24, 16.83], [82.24, 16.70],
            ]],
        },
    },
    {
        "key": "restricted-port",
        "name": "Kakinada Deep-Water Port Restricted Zone",
        "kind": "restricted",
        "restricted": True,
        "note": "Naval / port operations — vessel entry restricted.",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [82.28, 16.93], [82.36, 16.93], [82.36, 16.99],
                [82.28, 16.99], [82.28, 16.93],
            ]],
        },
    },
    {
        "key": "eez-band",
        "name": "Indian EEZ Reference Band",
        "kind": "eez",
        "restricted": False,
        "note": "Exclusive Economic Zone reference band (informational).",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [82.70, 16.60], [82.95, 16.60], [82.95, 17.30],
                [82.70, 17.30], [82.70, 16.60],
            ]],
        },
    },
]
