"""MOCK data adapters — India-wide coastal region registry.

ORCA is architected for the ENTIRE Indian coastline, not a single city.
Kakinada (Andhra Pradesh) is the first fully-validated demo region, but the
same adapter functions serve every region in `REGIONS` below. Adding a new
coastal region (Chennai, Kochi, Mumbai, Paradip, Veraval today; any other
Indian coastal town tomorrow) never requires touching the orchestrator,
routes, or spatial layer — only this registry.

Everything here is clearly labelled `is_mock: True` with a named `source`.
Values are realistic but synthetic. Real protected-area / port names are used
for flavour (Coringa, Bhitarkanika, Gulf of Kutch, Vembanad, Pulicat, Thane
Creek) but boundaries are simplified bundled reference polygons, NOT survey
data — do not treat as authoritative.

Adapters (each mirrors a real EO / oceanographic source):
    - PFZ + tide             -> INCOIS
    - weather + cyclone      -> IMD
    - SST + chlorophyll grid -> ISRO / Bhuvan ocean-colour products
    - maritime boundaries    -> bundled static GeoJSON reference layer
"""
import math
from datetime import datetime, timedelta, timezone

DEFAULT_REGION_ID = "kakinada"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hours_ago(h: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=h)).isoformat()


def _poly(cx: float, cy: float, dx: float = 0.09, dy: float = 0.09) -> dict:
    """Small rectangular reference polygon centred on (cx, cy)."""
    return {
        "type": "Polygon",
        "coordinates": [[
            [cx - dx, cy - dy], [cx + dx, cy - dy],
            [cx + dx, cy + dy], [cx - dx, cy + dy], [cx - dx, cy - dy],
        ]],
    }


def _eez_band(lon: float, lat: float, w: float = 0.25, h: float = 0.7) -> dict:
    return {
        "type": "Polygon",
        "coordinates": [[
            [lon, lat - h / 2], [lon + w, lat - h / 2],
            [lon + w, lat + h / 2], [lon, lat + h / 2], [lon, lat - h / 2],
        ]],
    }


# =============================================================================
# REGION REGISTRY — India-wide. Add a new coastal region here only.
# =============================================================================
REGIONS: dict[str, dict] = {
    "kakinada": {
        "id": "kakinada", "name": "Kakinada", "state": "Andhra Pradesh",
        "center": {"lat": 16.9891, "lon": 82.2475}, "coast_bearing": "east",
        "sea": "Bay of Bengal",
        "pfz_zones": [
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
        ],
        "forecast": {
            "today": {"wind_kn": 14, "gust_kn": 20, "wave_m": 1.2,
                      "condition": "Partly cloudy", "lightning_pct": 15, "cyclone": None},
            "tomorrow": {"wind_kn": 32, "gust_kn": 45, "wave_m": 3.1,
                        "condition": "Squally thunderstorms", "lightning_pct": 70,
                        "cyclone": "Deep Depression 'BOB-04' intensifying, approaching coast"},
        },
        "alerts": [
            {"key": "alert-cyclone-bob04", "type": "cyclone", "severity": "high",
             "title": "Cyclone Warning — Deep Depression BOB-04",
             "body": ("Deep Depression over west-central Bay of Bengal likely to "
                      "intensify into a cyclonic storm. Squally winds 45-55 kmph "
                      "gusting 65 kmph expected off Kakinada–Visakhapatnam coast "
                      "within 36 hours. Fishermen advised NOT to venture into sea."),
             "source": "IMD Cyclone Bulletin", "issued_hours_ago": 2, "valid_hours": 36},
            {"key": "alert-lightning-01", "type": "lightning", "severity": "moderate",
             "title": "Lightning Alert — Offshore Kakinada",
             "body": ("Thunderstorms with frequent lightning likely offshore Kakinada "
                      "between 04:00–09:00 IST tomorrow. Avoid open-sea activity."),
             "source": "IMD Nowcast", "issued_hours_ago": 1, "valid_hours": 18},
        ],
        "boundaries": [
            {"key": "mpa", "name": "Coringa Wildlife Sanctuary (MPA)", "kind": "mpa",
             "restricted": True, "note": "Protected mangrove marine sanctuary — fishing restricted.",
             "geometry": _poly(82.33, 16.765, 0.09, 0.065)},
            {"key": "restricted-port", "name": "Kakinada Deep-Water Port Restricted Zone",
             "kind": "restricted", "restricted": True,
             "note": "Naval / port operations — vessel entry restricted.",
             "geometry": _poly(82.32, 16.96, 0.04, 0.03)},
            {"key": "eez-band", "name": "Indian EEZ Reference Band", "kind": "eez",
             "restricted": False, "note": "Exclusive Economic Zone reference band (informational).",
             "geometry": _eez_band(82.70, 16.95, 0.25, 0.70)},
        ],
        "grid_base": {"lat": 16.75, "lon": 82.35},
        "grid_dir": {"lat_step": 1, "lon_step": 1},
        "sst_trend": [28.9, 28.7, 28.6, 28.5, 28.4, 28.3, 28.4],
        "chl_trend": [1.2, 1.4, 1.6, 1.9, 2.1, 2.2, 2.1],
        "tide_events": [
            {"type": "High", "time": "05:42 IST", "height_m": 1.4},
            {"type": "Low", "time": "11:58 IST", "height_m": 0.3},
            {"type": "High", "time": "18:10 IST", "height_m": 1.6},
            {"type": "Low", "time": "23:47 IST", "height_m": 0.5},
        ],
    },
    "chennai": {
        "id": "chennai", "name": "Chennai", "state": "Tamil Nadu",
        "center": {"lat": 13.0827, "lon": 80.2707}, "coast_bearing": "east",
        "sea": "Bay of Bengal",
        "pfz_zones": [
            {"key": "pfz-1", "name": "Chennai Harbour Approach", "lat": 13.05, "lon": 80.35,
             "confidence": 0.81, "sst_c": 29.6, "chl_mg_m3": 1.4, "depth_m": 30,
             "species": "Seer fish, Anchovy", "distance_note": "~9 km E of coast"},
            {"key": "pfz-2", "name": "Marina Deep", "lat": 13.10, "lon": 80.42,
             "confidence": 0.74, "sst_c": 29.3, "chl_mg_m3": 1.1, "depth_m": 48,
             "species": "Tuna", "distance_note": "~17 km E of coast"},
            {"key": "pfz-3", "name": "Ennore Shelf", "lat": 13.25, "lon": 80.38,
             "confidence": 0.70, "sst_c": 29.1, "chl_mg_m3": 1.3, "depth_m": 40,
             "species": "Sardine", "distance_note": "~20 km NE of coast"},
            {"key": "pfz-4", "name": "Kovalam Bank", "lat": 12.95, "lon": 80.32,
             "confidence": 0.66, "sst_c": 29.4, "chl_mg_m3": 1.0, "depth_m": 25,
             "species": "Prawn, Anchovy", "distance_note": "~14 km S of coast"},
        ],
        "forecast": {
            "today": {"wind_kn": 12, "gust_kn": 16, "wave_m": 1.0,
                      "condition": "Clear", "lightning_pct": 10, "cyclone": None},
            "tomorrow": {"wind_kn": 20, "gust_kn": 28, "wave_m": 2.0,
                        "condition": "Moderate swell, scattered showers", "lightning_pct": 35,
                        "cyclone": None},
        },
        "alerts": [
            {"key": "alert-highwave-01", "type": "high_wave", "severity": "moderate",
             "title": "High Wave Advisory — Chennai Coast",
             "body": ("Sea condition rough to very rough with wave heights of 1.8-2.2 m "
                      "likely off Chennai coast tomorrow. Small craft advised caution."),
             "source": "INCOIS Ocean State Forecast", "issued_hours_ago": 3, "valid_hours": 24},
        ],
        "boundaries": [
            {"key": "mpa", "name": "Pulicat Lake Bird Sanctuary (Buffer)", "kind": "mpa",
             "restricted": True, "note": "Ramsar wetland buffer — fishing restricted in core zone.",
             "geometry": _poly(80.32, 13.42, 0.10, 0.09)},
            {"key": "restricted-port", "name": "Chennai Port Restricted Zone",
             "kind": "restricted", "restricted": True,
             "note": "Naval / port operations — vessel entry restricted.",
             "geometry": _poly(80.30, 13.10, 0.035, 0.03)},
            {"key": "eez-band", "name": "Indian EEZ Reference Band", "kind": "eez",
             "restricted": False, "note": "Exclusive Economic Zone reference band (informational).",
             "geometry": _eez_band(80.75, 13.08, 0.25, 0.70)},
        ],
        "grid_base": {"lat": 12.90, "lon": 80.25},
        "grid_dir": {"lat_step": 1, "lon_step": 1},
        "sst_trend": [29.8, 29.7, 29.6, 29.5, 29.5, 29.4, 29.5],
        "chl_trend": [0.9, 1.0, 1.1, 1.0, 0.9, 1.0, 1.1],
        "tide_events": [
            {"type": "High", "time": "04:58 IST", "height_m": 1.1},
            {"type": "Low", "time": "10:40 IST", "height_m": 0.2},
            {"type": "High", "time": "17:20 IST", "height_m": 1.2},
            {"type": "Low", "time": "23:05 IST", "height_m": 0.3},
        ],
    },
    "kochi": {
        "id": "kochi", "name": "Kochi", "state": "Kerala",
        "center": {"lat": 9.9312, "lon": 76.2673}, "coast_bearing": "west",
        "sea": "Arabian Sea",
        "pfz_zones": [
            {"key": "pfz-1", "name": "Kochi Harbour Mouth", "lat": 9.95, "lon": 76.15,
             "confidence": 0.84, "sst_c": 28.2, "chl_mg_m3": 3.1, "depth_m": 32,
             "species": "Sardine, Malabar Mackerel", "distance_note": "~12 km W of coast"},
            {"key": "pfz-2", "name": "Vypin Shelf", "lat": 10.05, "lon": 76.10,
             "confidence": 0.80, "sst_c": 28.0, "chl_mg_m3": 3.4, "depth_m": 38,
             "species": "Anchovy, Sardine", "distance_note": "~17 km NW of coast"},
            {"key": "pfz-3", "name": "Munambam Bank", "lat": 10.20, "lon": 76.05,
             "confidence": 0.75, "sst_c": 27.8, "chl_mg_m3": 3.0, "depth_m": 45,
             "species": "Mackerel", "distance_note": "~22 km NW of coast"},
            {"key": "pfz-4", "name": "Alappuzha Deep", "lat": 9.75, "lon": 76.10,
             "confidence": 0.71, "sst_c": 28.3, "chl_mg_m3": 2.6, "depth_m": 40,
             "species": "Prawn, Sardine", "distance_note": "~19 km SW of coast"},
        ],
        "forecast": {
            "today": {"wind_kn": 10, "gust_kn": 14, "wave_m": 0.8,
                      "condition": "Fair, light breeze", "lightning_pct": 5, "cyclone": None},
            "tomorrow": {"wind_kn": 13, "gust_kn": 17, "wave_m": 1.0,
                        "condition": "Fair", "lightning_pct": 10, "cyclone": None},
        },
        "alerts": [],
        "boundaries": [
            {"key": "mpa", "name": "Vembanad-Kol Wetland (Ramsar) Buffer", "kind": "mpa",
             "restricted": True, "note": "Ramsar wetland buffer — fishing restricted in core zone.",
             "geometry": _poly(76.35, 9.60, 0.10, 0.10)},
            {"key": "restricted-port", "name": "Kochi Port & Naval Restricted Zone",
             "kind": "restricted", "restricted": True,
             "note": "Naval base / port operations — vessel entry restricted.",
             "geometry": _poly(76.24, 9.96, 0.035, 0.03)},
            {"key": "eez-band", "name": "Indian EEZ Reference Band", "kind": "eez",
             "restricted": False, "note": "Exclusive Economic Zone reference band (informational).",
             "geometry": _eez_band(75.75, 9.93, 0.25, 0.70)},
        ],
        "grid_base": {"lat": 9.75, "lon": 76.30},
        "grid_dir": {"lat_step": 1, "lon_step": -1},
        "sst_trend": [28.5, 28.4, 28.3, 28.2, 28.1, 28.0, 28.1],
        "chl_trend": [2.4, 2.7, 3.0, 3.2, 3.4, 3.3, 3.1],
        "tide_events": [
            {"type": "High", "time": "06:10 IST", "height_m": 1.0},
            {"type": "Low", "time": "12:20 IST", "height_m": 0.2},
            {"type": "High", "time": "18:40 IST", "height_m": 1.1},
            {"type": "Low", "time": "00:15 IST", "height_m": 0.3},
        ],
    },
    "mumbai": {
        "id": "mumbai", "name": "Mumbai", "state": "Maharashtra",
        "center": {"lat": 18.9220, "lon": 72.8347}, "coast_bearing": "west",
        "sea": "Arabian Sea",
        "pfz_zones": [
            {"key": "pfz-1", "name": "Colaba Point Bank", "lat": 18.88, "lon": 72.70,
             "confidence": 0.77, "sst_c": 27.6, "chl_mg_m3": 1.9, "depth_m": 33,
             "species": "Bombay Duck, Pomfret", "distance_note": "~14 km SW of coast"},
            {"key": "pfz-2", "name": "Versova Shelf", "lat": 19.05, "lon": 72.65,
             "confidence": 0.73, "sst_c": 27.4, "chl_mg_m3": 2.0, "depth_m": 40,
             "species": "Prawn, Bombay Duck", "distance_note": "~19 km W of coast"},
            {"key": "pfz-3", "name": "Thal Deep", "lat": 18.65, "lon": 72.60,
             "confidence": 0.68, "sst_c": 27.8, "chl_mg_m3": 1.7, "depth_m": 55,
             "species": "Pomfret, Seer fish", "distance_note": "~27 km SW of coast"},
            {"key": "pfz-4", "name": "Uran Bank", "lat": 18.85, "lon": 72.75,
             "confidence": 0.65, "sst_c": 27.7, "chl_mg_m3": 1.8, "depth_m": 28,
             "species": "Prawn", "distance_note": "~10 km SW of coast"},
        ],
        "forecast": {
            "today": {"wind_kn": 16, "gust_kn": 22, "wave_m": 1.5,
                      "condition": "Cloudy", "lightning_pct": 20, "cyclone": None},
            "tomorrow": {"wind_kn": 22, "gust_kn": 30, "wave_m": 2.1,
                        "condition": "Rough seas — monsoon low-pressure trough", "lightning_pct": 40,
                        "cyclone": None},
        },
        "alerts": [
            {"key": "alert-roughsea-01", "type": "high_wave", "severity": "moderate",
             "title": "Rough Sea Advisory — Mumbai Coast",
             "body": ("A monsoon low-pressure trough is causing rough sea conditions with "
                      "wave heights up to 2.1 m off Mumbai tomorrow. Fishermen advised caution."),
             "source": "INCOIS Ocean State Forecast", "issued_hours_ago": 4, "valid_hours": 30},
        ],
        "boundaries": [
            {"key": "mpa", "name": "Thane Creek Flamingo Sanctuary (Buffer)", "kind": "mpa",
             "restricted": True, "note": "Protected wetland/flamingo sanctuary buffer — restricted.",
             "geometry": _poly(72.98, 19.05, 0.07, 0.06)},
            {"key": "restricted-port", "name": "Mumbai Port Restricted Zone",
             "kind": "restricted", "restricted": True,
             "note": "Naval dockyard / port operations — vessel entry restricted.",
             "geometry": _poly(72.84, 18.92, 0.035, 0.03)},
            {"key": "eez-band", "name": "Indian EEZ Reference Band", "kind": "eez",
             "restricted": False, "note": "Exclusive Economic Zone reference band (informational).",
             "geometry": _eez_band(72.20, 18.90, 0.25, 0.70)},
        ],
        "grid_base": {"lat": 18.70, "lon": 72.90},
        "grid_dir": {"lat_step": 1, "lon_step": -1},
        "sst_trend": [27.9, 27.8, 27.7, 27.6, 27.5, 27.5, 27.6],
        "chl_trend": [1.5, 1.6, 1.8, 1.9, 2.0, 1.9, 1.8],
        "tide_events": [
            {"type": "High", "time": "05:20 IST", "height_m": 2.1},
            {"type": "Low", "time": "11:35 IST", "height_m": 0.5},
            {"type": "High", "time": "17:50 IST", "height_m": 2.3},
            {"type": "Low", "time": "23:55 IST", "height_m": 0.6},
        ],
    },
    "paradip": {
        "id": "paradip", "name": "Paradip", "state": "Odisha",
        "center": {"lat": 20.3167, "lon": 86.6167}, "coast_bearing": "east",
        "sea": "Bay of Bengal",
        "pfz_zones": [
            {"key": "pfz-1", "name": "Paradip Harbour Mouth", "lat": 20.30, "lon": 86.75,
             "confidence": 0.80, "sst_c": 28.7, "chl_mg_m3": 2.3, "depth_m": 30,
             "species": "Hilsa, Prawn", "distance_note": "~13 km E of coast"},
            {"key": "pfz-2", "name": "Mahanadi Delta Shelf", "lat": 20.45, "lon": 86.85,
             "confidence": 0.76, "sst_c": 28.5, "chl_mg_m3": 2.6, "depth_m": 36,
             "species": "Hilsa", "distance_note": "~24 km NE of coast"},
            {"key": "pfz-3", "name": "Hukitola Bank", "lat": 20.20, "lon": 86.80,
             "confidence": 0.70, "sst_c": 28.6, "chl_mg_m3": 2.2, "depth_m": 42,
             "species": "Pomfret, Prawn", "distance_note": "~19 km SE of coast"},
            {"key": "pfz-4", "name": "Devi River Mouth Deep", "lat": 20.15, "lon": 86.70,
             "confidence": 0.67, "sst_c": 28.4, "chl_mg_m3": 2.4, "depth_m": 26,
             "species": "Prawn, Hilsa", "distance_note": "~16 km SE of coast"},
        ],
        "forecast": {
            "today": {"wind_kn": 16, "gust_kn": 22, "wave_m": 1.4,
                      "condition": "Partly cloudy", "lightning_pct": 20, "cyclone": None},
            "tomorrow": {"wind_kn": 38, "gust_kn": 55, "wave_m": 3.6,
                        "condition": "Severe cyclonic storm conditions", "lightning_pct": 75,
                        "cyclone": "Very Severe Cyclonic Storm approaching Odisha coast"},
        },
        "alerts": [
            {"key": "alert-cyclone-01", "type": "cyclone", "severity": "high",
             "title": "Cyclone Warning — Odisha Coast",
             "body": ("A Very Severe Cyclonic Storm is tracking towards the Odisha coast near "
                      "Paradip. Winds 90-100 kmph gusting 115 kmph expected. All fishing "
                      "operations suspended; fishermen must return to harbour immediately."),
             "source": "IMD Cyclone Bulletin", "issued_hours_ago": 3, "valid_hours": 48},
            {"key": "alert-lightning-01", "type": "lightning", "severity": "high",
             "title": "Lightning Alert — Paradip Coast",
             "body": ("Very heavy rain with frequent lightning likely offshore Paradip over "
                      "the next 24 hours. Avoid all open-sea activity."),
             "source": "IMD Nowcast", "issued_hours_ago": 1, "valid_hours": 24},
        ],
        "boundaries": [
            {"key": "mpa", "name": "Bhitarkanika Mangrove & Wildlife Sanctuary (Buffer)",
             "kind": "mpa", "restricted": True,
             "note": "Protected mangrove/crocodile sanctuary buffer — fishing restricted.",
             "geometry": _poly(86.90, 20.70, 0.12, 0.10)},
            {"key": "restricted-port", "name": "Paradip Port Restricted Zone",
             "kind": "restricted", "restricted": True,
             "note": "Naval / port operations — vessel entry restricted.",
             "geometry": _poly(86.68, 20.30, 0.035, 0.03)},
            {"key": "eez-band", "name": "Indian EEZ Reference Band", "kind": "eez",
             "restricted": False, "note": "Exclusive Economic Zone reference band (informational).",
             "geometry": _eez_band(87.10, 20.30, 0.25, 0.70)},
        ],
        "grid_base": {"lat": 20.10, "lon": 86.70},
        "grid_dir": {"lat_step": 1, "lon_step": 1},
        "sst_trend": [29.0, 28.9, 28.8, 28.7, 28.6, 28.6, 28.7],
        "chl_trend": [1.8, 2.0, 2.2, 2.4, 2.6, 2.5, 2.3],
        "tide_events": [
            {"type": "High", "time": "05:05 IST", "height_m": 1.6},
            {"type": "Low", "time": "11:15 IST", "height_m": 0.4},
            {"type": "High", "time": "17:35 IST", "height_m": 1.8},
            {"type": "Low", "time": "23:25 IST", "height_m": 0.5},
        ],
    },
    "veraval": {
        "id": "veraval", "name": "Veraval", "state": "Gujarat",
        "center": {"lat": 20.9159, "lon": 70.3629}, "coast_bearing": "south",
        "sea": "Arabian Sea",
        "pfz_zones": [
            {"key": "pfz-1", "name": "Veraval Harbour Approach", "lat": 20.85, "lon": 70.25,
             "confidence": 0.79, "sst_c": 26.8, "chl_mg_m3": 1.6, "depth_m": 30,
             "species": "Bombay Duck, Ribbonfish", "distance_note": "~11 km SW of coast"},
            {"key": "pfz-2", "name": "Prabhas Deep", "lat": 20.80, "lon": 70.15,
             "confidence": 0.74, "sst_c": 26.6, "chl_mg_m3": 1.5, "depth_m": 44,
             "species": "Pomfret", "distance_note": "~20 km SW of coast"},
            {"key": "pfz-3", "name": "Madhavpur Bank", "lat": 20.75, "lon": 70.05,
             "confidence": 0.69, "sst_c": 26.5, "chl_mg_m3": 1.4, "depth_m": 50,
             "species": "Ribbonfish, Prawn", "distance_note": "~30 km SW of coast"},
            {"key": "pfz-4", "name": "Diu Shelf", "lat": 20.72, "lon": 70.90,
             "confidence": 0.66, "sst_c": 27.0, "chl_mg_m3": 1.3, "depth_m": 33,
             "species": "Bombay Duck", "distance_note": "~48 km SE of coast"},
        ],
        "forecast": {
            "today": {"wind_kn": 11, "gust_kn": 15, "wave_m": 0.9,
                      "condition": "Clear", "lightning_pct": 8, "cyclone": None},
            "tomorrow": {"wind_kn": 15, "gust_kn": 20, "wave_m": 1.1,
                        "condition": "Fair", "lightning_pct": 12, "cyclone": None},
        },
        "alerts": [],
        "boundaries": [
            {"key": "mpa", "name": "Gulf of Kutch Marine National Park (Buffer)", "kind": "mpa",
             "restricted": True, "note": "India's first Marine National Park buffer — restricted.",
             "geometry": _poly(70.20, 22.35, 0.12, 0.10)},
            {"key": "restricted-port", "name": "Veraval Port Restricted Zone",
             "kind": "restricted", "restricted": True,
             "note": "Fishing harbour / port operations — vessel entry restricted.",
             "geometry": _poly(70.37, 20.90, 0.03, 0.025)},
            {"key": "eez-band", "name": "Indian EEZ Reference Band", "kind": "eez",
             "restricted": False, "note": "Exclusive Economic Zone reference band (informational).",
             "geometry": _eez_band(69.60, 20.90, 0.25, 0.70)},
        ],
        "grid_base": {"lat": 20.60, "lon": 70.10},
        "grid_dir": {"lat_step": 1, "lon_step": -1},
        "sst_trend": [26.9, 26.8, 26.7, 26.6, 26.5, 26.5, 26.6],
        "chl_trend": [1.2, 1.3, 1.4, 1.5, 1.6, 1.5, 1.4],
        "tide_events": [
            {"type": "High", "time": "04:40 IST", "height_m": 1.9},
            {"type": "Low", "time": "10:55 IST", "height_m": 0.4},
            {"type": "High", "time": "17:05 IST", "height_m": 2.0},
            {"type": "Low", "time": "23:10 IST", "height_m": 0.5},
        ],
    },
}

# Legacy single-region export (kept for any not-yet-migrated call site).
REGION = {
    "id": REGIONS[DEFAULT_REGION_ID]["id"],
    "name": f"{REGIONS[DEFAULT_REGION_ID]['name']}, {REGIONS[DEFAULT_REGION_ID]['state']}",
    "center": REGIONS[DEFAULT_REGION_ID]["center"],
    "coast_bearing": f"{REGIONS[DEFAULT_REGION_ID]['coast_bearing']} ({REGIONS[DEFAULT_REGION_ID]['sea']})",
}
BOUNDARIES = REGIONS[DEFAULT_REGION_ID]["boundaries"]
PFZ_ZONES = REGIONS[DEFAULT_REGION_ID]["pfz_zones"]


def _region(region_id: str | None) -> dict:
    return REGIONS.get(region_id or DEFAULT_REGION_ID, REGIONS[DEFAULT_REGION_ID])


def _full_name(r: dict) -> str:
    return f"{r['name']}, {r['state']}"


# ---------------------------------------------------------------------------
# Region registry API — used by the India-wide region selector
# ---------------------------------------------------------------------------
def list_regions() -> list[dict]:
    return [
        {"id": r["id"], "name": r["name"], "state": r["state"],
         "center": r["center"], "sea": r["sea"]}
        for r in REGIONS.values()
    ]


def get_region(region_id: str | None = None) -> dict:
    r = _region(region_id)
    return {"id": r["id"], "name": r["name"], "state": r["state"],
            "center": r["center"], "coast_bearing": r["coast_bearing"],
            "sea": r["sea"]}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(a))


def nearest_region(lat: float, lon: float) -> tuple[dict, float]:
    """Nearest supported coastal region to a GPS point (India-wide lookup)."""
    best, best_d = None, float("inf")
    for r in REGIONS.values():
        d = _haversine_km(lat, lon, r["center"]["lat"], r["center"]["lon"])
        if d < best_d:
            best, best_d = r, d
    return get_region(best["id"]), round(best_d, 1)


# ---------------------------------------------------------------------------
# INCOIS adapter — Potential Fishing Zones + tide table
# ---------------------------------------------------------------------------
def get_pfz_advisory(region_id: str | None = None) -> dict:
    r = _region(region_id)
    return {"source": "INCOIS PFZ Advisory", "is_mock": True,
            "last_updated": _hours_ago(6), "region": _full_name(r),
            "region_id": r["id"], "zones": r["pfz_zones"]}


def get_tide_table(region_id: str | None = None) -> dict:
    r = _region(region_id)
    return {"source": "INCOIS Tide Tables", "is_mock": True,
            "last_updated": _hours_ago(6), "region": _full_name(r),
            "region_id": r["id"], "events": r["tide_events"]}


# ---------------------------------------------------------------------------
# IMD adapter — weather forecast + cyclone / lightning bulletins
# ---------------------------------------------------------------------------
def get_weather(region_id: str | None = None, timeframe: str = "today") -> dict:
    r = _region(region_id)
    key = "tomorrow" if timeframe and "tomorrow" in timeframe.lower() else "today"
    fc = r["forecast"][key]
    return {"source": "IMD Marine Weather Forecast", "is_mock": True,
            "last_updated": _hours_ago(3), "region": _full_name(r),
            "region_id": r["id"], "timeframe": key, **fc}


def get_active_alerts(region_id: str | None = None) -> list[dict]:
    r = _region(region_id)
    now = datetime.now(timezone.utc)
    out = []
    for a in r["alerts"]:
        out.append({
            "key": a["key"], "type": a["type"], "severity": a["severity"],
            "title": a["title"], "body": a["body"], "source": a["source"],
            "is_mock": True, "issued_at": _hours_ago(a["issued_hours_ago"]),
            "valid_until": (now + timedelta(hours=a["valid_hours"])).isoformat(),
            "region": _full_name(r), "region_id": r["id"],
        })
    return out


# ---------------------------------------------------------------------------
# ISRO / Bhuvan adapter — SST + chlorophyll grids and 7-day trends
# ---------------------------------------------------------------------------
def _grid(region_id: str | None = None) -> list[dict]:
    r = _region(region_id)
    base_lat, base_lon = r["grid_base"]["lat"], r["grid_base"]["lon"]
    lat_step = r.get("grid_dir", {}).get("lat_step", 1)
    lon_step = r.get("grid_dir", {}).get("lon_step", 1)
    points = []
    for i in range(5):
        for j in range(5):
            lat = round(base_lat + lat_step * i * 0.11, 4)
            lon = round(base_lon + lon_step * j * 0.11, 4)
            sst = round(29.0 - j * 0.28 - i * 0.05, 2)
            chl = round(2.6 - j * 0.32 + (i % 2) * 0.15, 2)
            points.append({"lat": lat, "lon": lon, "sst_c": sst,
                           "chl_mg_m3": max(chl, 0.2)})
    return points


def get_sst_chl_grid(region_id: str | None = None) -> dict:
    r = _region(region_id)
    return {"source": "ISRO / Bhuvan Ocean Colour (SST & Chlorophyll)",
            "is_mock": True, "last_updated": _hours_ago(8),
            "region": _full_name(r), "region_id": r["id"], "grid": _grid(region_id)}


def _trend(region_id: str | None, key: str, source: str, unit: str) -> dict:
    r = _region(region_id)
    days = [(datetime.now(timezone.utc) - timedelta(days=d)).strftime("%d %b")
            for d in range(6, -1, -1)]
    return {"source": source, "is_mock": True, "last_updated": _hours_ago(8),
            "region": _full_name(r), "region_id": r["id"], "unit": unit,
            "labels": days, "values": r[key]}


def get_sst_trend(region_id: str | None = None) -> dict:
    return _trend(region_id, "sst_trend", "ISRO / Bhuvan SST time-series", "°C")


def get_chl_trend(region_id: str | None = None) -> dict:
    return _trend(region_id, "chl_trend", "ISRO / Bhuvan Chlorophyll time-series", "mg/m³")


# ---------------------------------------------------------------------------
# Bundled maritime boundary reference layer (static GeoJSON) -> PostGIS/Mongo
# ---------------------------------------------------------------------------
def get_boundaries(region_id: str | None = None) -> list[dict]:
    return _region(region_id)["boundaries"]


# ---------------------------------------------------------------------------
# Flattened, uniquely-keyed exports for seeding the NATIONWIDE spatial index.
# Every region's PFZ + boundary layer is loaded into the same Mongo
# collections (mirroring one authoritative national PostGIS store) — nearest
# lookups then resolve correctly across the whole coastline purely by
# geographic distance, with no per-region filtering needed.
# ---------------------------------------------------------------------------
def all_pfz_zones() -> list[dict]:
    out = []
    for r in REGIONS.values():
        for z in r["pfz_zones"]:
            out.append({**z, "key": f"{r['id']}-{z['key']}", "region_id": r["id"],
                       "region": _full_name(r)})
    return out


def all_boundaries_all_regions() -> list[dict]:
    out = []
    for r in REGIONS.values():
        for b in r["boundaries"]:
            out.append({**b, "key": f"{r['id']}-{b['key']}", "region_id": r["id"],
                       "region": _full_name(r)})
    return out
