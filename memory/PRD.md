# ORCA — Marine EcOsystem Reasoning with Collaborative Agents (PRD)

## Original problem statement
ISRO PS 26176 (Disaster Management). Agentic AI marine-intelligence platform:
fishermen / coastal researchers / disaster agencies / maritime operators ask
natural-language questions about ocean & weather and get evidence-based,
EXPLAINABLE, conversational answers with inline maps, charts and alerts.
Requested stack was Flutter/PostGIS; adapted (per user) to the Emergent stack:
**Expo/React Native + FastAPI + MongoDB (2dsphere)**, runs in **Expo Go**.
User choices: no phone/OTP auth; model gpt-5.6-luna; mock data for demo region
Kakinada; English + Telugu. Later: reskin UI to a dark "maritime command
console" aesthetic (reference screenshot).

## Architecture
- Backend modular monolith: `orchestrator/` (planner + specialists + synthesizer,
  `rules.py` deterministic verdicts), `gis/spatial.py` (MongoDB 2dsphere:
  $geoNear, $geoIntersects, route sampling), `data_adapters/mock_region.py`
  (INCOIS/IMD/ISRO/boundaries — all is_mock), `notifications/service.py`
  (hazard + geofence, FCM-ready hook), `server.py` (rate-limited chat, seeding).
- Frontend Expo Router: bottom tabs Chat / Alerts / Saved. MapLibre GL JS in a
  WebView (dark Carto basemap), react-native-svg trend charts, collapsible
  reasoning trace, RadarCard telemetry hero + agent chips.
- Safety verdicts are DETERMINISTIC (thresholds), LLM only explains; explicit
  safe-default on any AI/network failure.

## User personas
Fisherman (low-end Android, at sea, regional language), coastal researcher,
disaster-management agency, maritime/vessel operator.

## Core requirements (static)
Conversational chat (primary), inline maps+charts, explainable answers with
source/agent citations + visible reasoning trace, deterministic safety, hazard
alerts, geofencing, route safety, saved locations/vessel, offline stale banners,
EN + Telugu, server-side keys, rate-limited chat.

## Implemented (2026-08-30)
- Backend: /api/chat multi-agent pipeline (7 agents), 9 intents incl. two
  flagships (safe-tomorrow → UNSAFE, nearest-PFZ), Telugu, persistence,
  rate limiting; alerts, notifications, locations CRUD, geofence check,
  boundaries/pfz/ocean data endpoints. Startup seeds boundaries + PFZ.
- Frontend: Chat (RadarCard hero, suggestions, verdict badge, citations,
  reasoning trace, inline map+charts, offline banner, EN/te toggle, new session),
  Alerts (active hazards + notifications, pull-to-refresh, stale cache),
  Saved (2-col grid, add modal, use-my-location w/ permission flow, vessel
  switch, ASK deep-link, GEOFENCE trigger).
- Tested end-to-end by testing agent: 15/15 backend pass, all frontend flows.
- UI reskinned to dark maritime command-console theme (design tokens propagate).

## Data: real vs mock
All sources MOCK (is_mock:true) for Kakinada demo: INCOIS PFZ/tide, IMD
weather/cyclone/lightning, ISRO/Bhuvan SST/chl, bundled maritime boundaries
(incl. real Coringa MPA). Swappable adapters.

## Backlog / remaining
- P1: Voice input for chat (architecture already text-first).
- P1: FCM push on native build (hook exists; needs google-services.json + build).
- P2: More demo regions; live weather adapter behind the mock contract.
- P2: Route-planner UI (backend route_safety exists; needs start/end picker).
- P2: Animated radar sweep (currently static motif).

## Next tasks
Voice input, route-planner map picker, additional regions.
