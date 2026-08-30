# ORCA — Marine EcOsystem Reasoning with Collaborative Agents

Agentic AI marine-intelligence platform for fishermen, coastal researchers,
disaster-management agencies and maritime operators. Ask natural-language
questions about ocean/weather conditions and get evidence-based, explainable,
conversational answers with inline maps, charts and alerts.

> Built for ISRO Problem Statement 26176 (Disaster Management theme).
> Adapted to the Emergent stack: **Expo/React Native + FastAPI + MongoDB**
> (runs in **Expo Go**). MongoDB with 2dsphere indexes stands in for
> PostgreSQL/PostGIS as the authoritative spatial store.

## Architecture

### Backend (`/app/backend`) — modular monolith
- `orchestrator/` — Planner + specialist agents + Synthesizer pipeline
  - `agents.py` — planner (LLM), specialist agents, synthesizer (LLM)
  - `rules.py` — **deterministic** safety verdict engine (the authority)
- `gis/spatial.py` — nearest-PFZ (`$geoNear`), geofence (`$geoIntersects`),
  route safety — all server-side, never on the client
- `data_adapters/mock_region.py` — swappable source adapters
- `notifications/service.py` — hazard + geofence notifications (FCM-ready hook)
- `server.py` — FastAPI routes, rate-limited chat, startup seeding

### Frontend (`/app/frontend`) — Expo Router
- Chat (primary), Alerts, Saved — bottom tabs
- Inline **MapLibre GL JS** map (WebView, open-source, custom raster/heatmap
  overlays), react-native-svg trend charts, collapsible reasoning trace
- EN + Telugu end-to-end, offline stale-data banners, SQLite-free local cache
  via the shared secure storage util

## Agent reasoning (visible / loggable)
Every answer returns a `reasoning_trace`:
`Planner → Data Discovery → Weather Intelligence → Ocean Analytics →
Geospatial/Risk → Reporting/Visualization → Synthesizer`.

**Critical rule:** safety verdicts (SAFE / UNSAFE / CAUTION, geofence breach)
are decided by deterministic threshold checks in `rules.py` against real
data/spatial queries. The LLM only *explains* the verdict in natural language.
On any AI/network failure the app returns an explicit safe default
("could not verify — do not assume it is safe").

## Real vs MOCKED data
For this MVP **all data sources are clearly-labelled MOCK adapters** for the
demo region **Kakinada, Andhra Pradesh** (`is_mock: true`, named `source`):

| Source | Real equivalent | Status |
|---|---|---|
| PFZ advisory, tide tables | INCOIS | **MOCK** |
| Weather, cyclone & lightning bulletins | IMD | **MOCK** |
| SST + chlorophyll grid & trends | ISRO / Bhuvan ocean colour | **MOCK** |
| Maritime boundaries (EEZ / MPA / restricted) | bundled static GeoJSON | **MOCK (bundled)** |

Each adapter returns a stable contract, so a real feed can replace the mock
body without touching the orchestrator. Boundaries include the real **Coringa
Wildlife Sanctuary** MPA near Kakinada.

## Flagship queries (fully working end-to-end)
- "Is it safe to venture into the sea tomorrow morning?" → **UNSAFE** (cyclone
  BOB-04 + 32 kn wind + 3.1 m waves + 70% lightning)
- "Where is the nearest Potential Fishing Zone today?" → nearest PFZ + map

## Key env / secrets (server-side only)
- `EMERGENT_LLM_KEY` (backend/.env) — LLM access (model `gpt-5.6-luna`)
- `MONGO_URL`, `DB_NAME` — database

No third-party or LLM key is bundled into the app; the client only knows
`EXPO_PUBLIC_BACKEND_URL`.

## Out of scope (this build)
Full national boundary coverage, background battery-optimized geofencing,
authority web dashboard, full offline query-answering, phone/OTP auth.
