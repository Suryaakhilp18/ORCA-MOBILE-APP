"""Planner + specialist agents + synthesizer pipeline.

India-wide: agents never hardcode a single region. Every specialist call is
parametrised by a `region_id`, resolved per-request from (in priority order):
1. An explicit place mentioned in the user's message (Planner extracts it and
   we snap to the nearest known region via `mr.nearest_region`).
2. The caller's GPS location / currently-selected app region.
3. The India-wide default demo region (Kakinada).
"""
import json
import logging
import os
import re
from datetime import datetime, timezone

from emergentintegrations.llm.chat import LlmChat, UserMessage

from data_adapters import mock_region as mr
from gis import spatial
from orchestrator.rules import evaluate_sea_safety

# User-provided Gemini API key powers ORCA's planner + synthesizer agents.
# Note: this key's free tier has a hard cap of ~20 requests/day for
# gemini-3.5-flash (and zero quota for "pro" models) — confirmed via live
# 429 RESOURCE_EXHAUSTED responses during testing. Since a normal chat turn
# is 2 LLM calls (plan + synthesize), that budget exhausts in ~10 messages.
# To keep ORCA usable, every LLM call automatically falls back to the
# Emergent-managed Universal Key (GPT-5.6 Luna) if Gemini errors for ANY
# reason (quota, auth, network) — Gemini always stays the first attempt.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = ("gemini", "gemini-3.5-flash")
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
FALLBACK_MODEL = ("openai", "gpt-5.6-luna")

INTENTS = [
    "pfz_nearest", "safety_sail", "conditions", "alerts_query",
    "chlorophyll_sst", "route_safety", "geofence_avoid",
    "productivity_decline", "general",
]


async def _chat_with_fallback(session_id: str, system: str, prompt: str) -> str:
    """Call the LLM with the user's Gemini key first; transparently fall
    back to the Emergent Universal Key if Gemini errors (e.g. daily quota
    exhausted). Raises only if BOTH providers fail."""
    try:
        chat = LlmChat(api_key=GEMINI_API_KEY, session_id=session_id,
                       system_message=system).with_model(*GEMINI_MODEL)
        resp = await chat.send_message(UserMessage(text=prompt))
        if resp and resp.strip():
            return resp
    except Exception as e:
        logging.getLogger("orca").warning(
            f"Gemini call failed ({type(e).__name__}: {e}); "
            "falling back to Emergent Universal Key.")
    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"{session_id}-fb",
                   system_message=system).with_model(*FALLBACK_MODEL)
    return await chat.send_message(UserMessage(text=prompt))


def _extract_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Planner Agent — decompose intent, resolve location, detect language
# ---------------------------------------------------------------------------
def _region_roster() -> str:
    return ", ".join(f"{r['name']} ({r['state']})" for r in mr.list_regions())


def _planner_system(region_hint: dict, lang_hint: str | None) -> str:
    hint_line = (
        f"The user's app language preference is currently set to '{lang_hint}'. "
        "See the LANGUAGE DETECTION RULES below for exactly how to use this.\n"
        if lang_hint else ""
    )
    return (
        "You are the PLANNER agent of ORCA, a marine intelligence assistant "
        "covering the ENTIRE Indian coastline — not a single city. ORCA has "
        f"live validated data for: {_region_roster()}, and can reason about "
        "any other Indian coastal location by estimating coordinates. The "
        f"user's app is currently focused on {region_hint['name']}, "
        f"{region_hint['state']} ({region_hint['center']['lat']}, "
        f"{region_hint['center']['lon']}).\n"
        f"{hint_line}"
        "Decompose the user's message into a plan. Respond with STRICT JSON "
        "only, no prose. Schema:\n"
        "{\n"
        '  "intent": one of ["pfz_nearest","safety_sail","conditions","alerts_query",'
        '"chlorophyll_sst","route_safety","geofence_avoid","productivity_decline","general"],\n'
        '  "timeframe": "today" | "tomorrow",\n'
        '  "language": "en" | "te" | "hi",\n'
        '  "script": "native" | "romanized",\n'
        '  "location": {"name": string, "lat": number, "lon": number} | null,\n'
        '  "route": {"start":{"lat":number,"lon":number},"end":{"lat":number,"lon":number}} | null,\n'
        '  "datasets": string[]  (subset of ["pfz","weather","sst","chl","tide","alerts","boundaries"])\n'
        "}\n"
        "ROUTE COORDINATES — CRITICAL (a common mistake): 'route' represents "
        "a BOAT's path through OPEN WATER, never through land. If the user "
        "names a coastal town/harbor/village as start or end (e.g. "
        "'Kakinada', 'Chennai'), do NOT use that town's on-land/city-centre "
        "coordinates — using your own knowledge of the Indian coastline's "
        "shape, shift the point a few km further out, into the sea in front "
        "of that town, so BOTH the point itself and the straight line "
        "between start and end stay over water and never cross a peninsula, "
        "island, bay mouth landmass, or riverbank. If the user names an "
        "island, fishing zone, or offshore landmark, that is already a sea "
        "point — use it as given.\n"
        "LANGUAGE DETECTION RULES (priority order):\n"
        "- 'te' = Telugu, 'hi' = Hindi, 'en' = English.\n"
        "- STEP 1: If the message is written in Telugu script, Devanagari "
        "script, OR clearly recognisable ROMANIZED Telugu/Hindi (e.g. 'Repu "
        "sea loki vellacha?' is romanized Telugu; 'Kal samundar jaana safe "
        "hai?' is romanized Hindi) — that detected language WINS, regardless "
        "of the app's language preference. Set script='native' for "
        "Telugu/Devanagari script, 'romanized' for Latin-script "
        "Telugu/Hindi.\n"
        "- STEP 2: Otherwise (plain/neutral English, or genuinely "
        "ambiguous), use the app's language preference from above as the "
        "reply language — the user chose that language for the WHOLE app, "
        "so replies should honour it even if they happened to type in "
        "English. Set script='native' in this case.\n"
        "- Only fall back to 'en' if there is no app language preference at all.\n"
        "LOCATION RULES:\n"
        "If the user references ANY Indian coastal place by name (e.g. Chennai, "
        "Kochi, Kakinada, Mumbai, Paradip, Veraval, Visakhapatnam, Goa, Mangalore, "
        "or any other coastal town), estimate its approximate lat/lon and set "
        "location to that place. If the user does NOT mention a specific place, "
        "set location to null so the app's currently selected region is used."
    )


async def run_planner(session_id: str, message: str, context: str,
                      region_hint: dict, lang_hint: str | None = None) -> dict:
    prompt = (f"Conversation so far:\n{context}\n\nUser message: {message}")
    try:
        resp = await _chat_with_fallback(f"{session_id}-plan",
                                         _planner_system(region_hint, lang_hint),
                                         prompt)
        plan = _extract_json(resp)
    except Exception:
        # Both LLM providers failed — deterministic keyword fallback keeps
        # the safety pipeline fully operational (LLM only ever explains,
        # never decides safety).
        plan = {}

    if plan.get("intent") not in INTENTS:
        plan = _keyword_plan(message, lang_hint)
    if plan.get("language") not in ("en", "te", "hi"):
        plan["language"] = lang_hint if lang_hint in ("en", "te", "hi") else "en"
    return plan


def _keyword_plan(message: str, lang_hint: str | None = None) -> dict:
    """Deterministic fallback if the planner LLM is unavailable. Can only
    reliably detect native script (not romanized text) — falls back to the
    app's selected language preference otherwise."""
    m = message.lower()
    is_te = bool(re.search(r"[\u0c00-\u0c7f]", message))  # Telugu block
    is_hi = bool(re.search(r"[\u0900-\u097f]", message))  # Devanagari block
    if is_te:
        lang = "te"
    elif is_hi:
        lang = "hi"
    else:
        lang = lang_hint if lang_hint in ("en", "te", "hi") else "en"
    if "pfz" in m or "fishing zone" in m or "fish" in m and "declin" not in m:
        intent = "pfz_nearest"
    elif "safe" in m or "venture" in m or "go out" in m or "sail" in m:
        intent = "safety_sail"
    elif "alert" in m or "cyclone" in m or "lightning" in m:
        intent = "alerts_query"
    elif "chlorophyll" in m or "sst" in m or "temperature" in m:
        intent = "chlorophyll_sst"
    elif "route" in m or "path" in m:
        intent = "route_safety"
    elif "avoid" in m or "restrict" in m or "geofenc" in m:
        intent = "geofence_avoid"
    elif "declin" in m or "productivity" in m:
        intent = "productivity_decline"
    elif "tide" in m or "weather" in m or "condition" in m:
        intent = "conditions"
    else:
        intent = "general"
    timeframe = "tomorrow" if "tomorrow" in m else "today"
    return {"intent": intent, "timeframe": timeframe, "language": lang,
            "script": "native", "location": None, "route": None, "datasets": []}


# ---------------------------------------------------------------------------
# Specialist agents — deterministic data gathering + rule checks
# ---------------------------------------------------------------------------
async def run_specialists(plan: dict, loc: dict, region_id: str) -> dict:
    """Invoke the specialist agents relevant to the intent. Returns a bundle
    of data, the deterministic verdict, citations, widgets and a trace."""
    intent = plan["intent"]
    timeframe = plan.get("timeframe", "today")
    region = mr.get_region(region_id)
    trace = []
    citations = []
    widgets = []
    data = {}
    verdict = None

    # Data Discovery Agent
    needed = _discover(intent)
    trace.append({"agent": "Data Discovery Agent",
                  "detail": (f"Query intent '{intent}' resolved to region "
                             f"{region['name']}, {region['state']}; needs: "
                             f"{', '.join(needed)}.")})

    # Weather Intelligence Agent
    if "weather" in needed:
        weather = mr.get_weather(region_id, timeframe)
        data["weather"] = weather
        citations.append(f"{weather['source']} ({weather['timeframe']}, mock)")
        safety = evaluate_sea_safety(weather)
        data["safety"] = safety
        verdict = safety["verdict"]
        trace.append({"agent": "Weather Intelligence Agent",
                      "detail": (f"wind {weather['wind_kn']}kn, wave {weather['wave_m']}m, "
                                 f"lightning {weather['lightning_pct']}%, "
                                 f"cyclone={weather['cyclone'] or 'none'} -> "
                                 f"rule verdict {safety['verdict']}.")})

    # Ocean Analytics Agent
    if "sst" in needed or "chl" in needed or "pfz" in needed:
        grid = mr.get_sst_chl_grid(region_id)
        data["ocean_grid"] = grid
        citations.append(f"{grid['source']} (mock)")
        trace.append({"agent": "Ocean Analytics Agent",
                      "detail": ("Correlated SST & chlorophyll grid; higher chlorophyll "
                                 "with SST 27-29°C indicates favourable feeding zones.")})

    # Geospatial / Risk Agent
    if intent == "pfz_nearest" or "pfz" in needed:
        zones = await spatial.nearest_pfz(loc["lat"], loc["lon"], limit=3)
        data["nearest_pfz"] = zones
        adv = mr.get_pfz_advisory(region_id)
        citations.append(f"{adv['source']} (mock)")
        trace.append({"agent": "Geospatial/Risk Agent",
                      "detail": (f"Nationwide PostGIS-style $geoNear from "
                                 f"({loc['lat']},{loc['lon']}) returned "
                                 f"{len(zones)} PFZ sorted by distance.")})
        # Recommend the SAFEST reachable zone: check a route to each of the
        # nearest candidates (closest first) and pick the first fully-clear
        # one; if none are fully clear, recommend whichever has the fewest
        # unsafe waypoints. This is what actually plots a "safe route to
        # fish" on the map, not just a list of PFZ names.
        best = None
        for z in zones:
            rr = await spatial.route_safety(loc, {"lat": z["lat"], "lon": z["lon"]})
            if best is None or rr["unsafe_count"] < best["route"]["unsafe_count"]:
                best = {"zone": z, "route": rr}
            if rr["unsafe_count"] == 0:
                break
        if best:
            data["route"] = best["route"]
            data["recommended_pfz"] = best["zone"]
            citations.append("Bundled maritime boundary layer (route safety check)")
            trace.append({"agent": "Geospatial/Risk Agent",
                          "detail": (f"Checked safe-path routing to the nearest PFZ "
                                     f"candidates; recommending {best['zone']['name']} "
                                     f"with {best['route']['unsafe_count']} unsafe "
                                     f"waypoint(s) on the plotted route.")})
    if intent in ("geofence_avoid", "conditions", "safety_sail"):
        breaches = await spatial.geofence_check(loc["lat"], loc["lon"])
        data["geofence"] = breaches
        bnds = mr.get_boundaries(region_id)
        data["boundaries"] = bnds
        citations.append("Bundled maritime boundary layer (EEZ/MPA/restricted)")
        trace.append({"agent": "Geospatial/Risk Agent",
                      "detail": (f"Point-in-polygon check: {len(breaches)} boundary "
                                 f"breach(es) at location; {len(bnds)} local boundaries loaded.")})
        if intent == "geofence_avoid":
            data["avoid_zones"] = [b for b in bnds if b.get("restricted")]
    if intent == "route_safety" and plan.get("route"):
        route = plan["route"]
        rr = await spatial.route_safety(route["start"], route["end"])
        weather = mr.get_weather(region_id, timeframe)
        data["weather"] = weather
        safety = evaluate_sea_safety(weather)
        data["safety"] = safety
        route_unsafe = rr["unsafe_count"] > 0 or safety["verdict"] == "UNSAFE"
        verdict = "UNSAFE" if route_unsafe else ("CAUTION"
                                                 if safety["verdict"] == "CAUTION"
                                                 else "SAFE")
        data["route"] = rr
        citations.append("Bundled maritime boundary layer + IMD weather (mock)")
        trace.append({"agent": "Geospatial/Risk Agent",
                      "detail": (f"Route sampled into {rr['total']} points; "
                                 f"{rr['unsafe_count']} unsafe segment(s); "
                                 f"weather verdict {safety['verdict']} -> route {verdict}.")})

    if "tide" in needed:
        tide = mr.get_tide_table(region_id)
        data["tide"] = tide
        citations.append(f"{tide['source']} (mock)")
    if "alerts" in needed or intent == "alerts_query":
        alerts = mr.get_active_alerts(region_id)
        data["alerts"] = alerts
        for a in alerts:
            citations.append(f"{a['source']} (mock)")
        trace.append({"agent": "Weather Intelligence Agent",
                      "detail": f"{len(alerts)} active IMD hazard bulletin(s) for {region['name']}."})

    # Reporting / Visualization Agent — build widget payloads
    widgets = _build_widgets(intent, loc, data)
    trace.append({"agent": "Reporting/Visualization Agent",
                  "detail": f"Prepared {len(widgets)} inline widget(s) for the client."})

    return {"data": data, "verdict": verdict, "citations": _dedupe(citations),
            "widgets": widgets, "trace": trace, "region": region}


def _discover(intent: str) -> list[str]:
    table = {
        "pfz_nearest": ["pfz", "sst", "chl", "weather"],
        "safety_sail": ["weather", "alerts", "tide", "pfz"],
        "conditions": ["weather", "tide", "sst"],
        "alerts_query": ["alerts"],
        "chlorophyll_sst": ["sst", "chl", "pfz"],
        "route_safety": ["weather", "boundaries"],
        "geofence_avoid": ["boundaries"],
        "productivity_decline": ["sst", "chl", "pfz"],
        "general": ["weather"],
    }
    return table.get(intent, ["weather"])


def _dedupe(items: list[str]) -> list[str]:
    seen, out = set(), []
    for i in items:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def _build_widgets(intent: str, loc: dict, data: dict) -> list[dict]:
    widgets = []
    markers = [{"lat": loc["lat"], "lon": loc["lon"], "label": "Your location",
                "kind": "user"}]
    layers = []

    if data.get("nearest_pfz"):
        rec_key = (data.get("recommended_pfz") or {}).get("key")
        for z in data["nearest_pfz"]:
            is_rec = data.get("recommended_pfz") and z.get("key") == rec_key
            markers.append({"lat": z["lat"], "lon": z["lon"],
                            "label": f"{'★ RECOMMENDED — ' if is_rec else ''}{z['name']} ({z['distance_km']} km)",
                            "kind": "pfz_recommended" if is_rec else "pfz"})
    if data.get("boundaries"):
        layers.append({"type": "boundary", "features": data["boundaries"]})
    if data.get("avoid_zones"):
        layers.append({"type": "boundary", "features": data["avoid_zones"]})
    if data.get("ocean_grid") and intent in ("chlorophyll_sst", "pfz_nearest",
                                              "productivity_decline"):
        layers.append({"type": "heatmap",
                       "metric": "chl" if intent != "pfz_nearest" else "sst",
                       "grid": data["ocean_grid"]["grid"]})
    if data.get("route"):
        segs = data["route"]["segments"]
        # A "safe route to a recommended PFZ" starts at the user's own
        # location and ends exactly on a PFZ marker already added above —
        # skip re-adding duplicate START/DESTINATION pins for those, only a
        # named point-to-point route (route_safety intent) gets them.
        is_pfz_route = "recommended_pfz" in data
        # Start / destination get distinct, clearly-labelled markers; every
        # intermediate sampled point is colour-coded safe(green)/unsafe(red)
        # so the whole path — not just its endpoints — is visible on the map.
        for i, s in enumerate(segs):
            if i == 0:
                if is_pfz_route:
                    continue
                label, kind = "START", "route_start"
            elif i == len(segs) - 1:
                if is_pfz_route:
                    continue
                label, kind = "DESTINATION", "route_end"
            else:
                label = s["reason"] or ("Safe stretch" if s["safe"] else "Unsafe stretch")
                kind = "route_safe" if s["safe"] else "route_unsafe"
            markers.append({"lat": s["lat"], "lon": s["lon"], "label": label, "kind": kind})
        # A connected polyline (not just dots) between consecutive sampled
        # points, one coloured segment per pair, so the ACTUAL route path is
        # drawn end-to-end and unsafe stretches are visually obvious.
        route_segments = []
        for a, b in zip(segs, segs[1:]):
            route_segments.append({
                "a": [a["lon"], a["lat"]], "b": [b["lon"], b["lat"]],
                "unsafe": (not a["safe"]) or (not b["safe"]),
            })
        layers.append({"type": "route_line", "segments": route_segments})

    # Map widget (skip pure alert queries)
    if intent != "alerts_query":
        widgets.append({
            "type": "map",
            "center": {"lat": loc["lat"], "lon": loc["lon"]},
            "markers": markers,
            "layers": layers,
        })

    # Chart widgets
    if intent in ("chlorophyll_sst", "productivity_decline"):
        region_id = data.get("ocean_grid", {}).get("region_id")
        sst = mr.get_sst_trend(region_id)
        chl = mr.get_chl_trend(region_id)
        widgets.append({"type": "chart", "title": "Sea Surface Temperature (7-day)",
                        "unit": sst["unit"], "labels": sst["labels"],
                        "values": sst["values"], "color": "#E63946"})
        widgets.append({"type": "chart", "title": "Chlorophyll-a (7-day)",
                        "unit": chl["unit"], "labels": chl["labels"],
                        "values": chl["values"], "color": "#2A3B32"})
    return widgets


# ---------------------------------------------------------------------------
# Synthesizer — explain the deterministic verdict in natural, localised language
# ---------------------------------------------------------------------------
SYNTH_SYSTEM = (
    "You are ORCA, a friendly, knowledgeable marine copilot talking directly to "
    "a fisherman — not a report generator. You receive a machine-computed result "
    "with a DETERMINISTIC safety verdict and the data that produced it. Turn it "
    "into ONE warm, natural, human reply, the way a trusted local friend who "
    "knows the sea would explain it over a phone call.\n"
    "HARD SAFETY RULES (never break these):\n"
    "- NEVER change, soften or contradict the given verdict. If verdict is "
    "UNSAFE, clearly and unambiguously tell the user it is not safe to go. If "
    "data is missing/verdict is null, say conditions could not be verified and "
    "explicitly tell them not to assume it is safe.\n"
    "- Numbers must stay accurate — never invent or round away key figures.\n"
    "TONE RULES (very important):\n"
    "- Sound like a person, not a weather bulletin. Prefer 'the sea looks rougher "
    "than usual tomorrow morning, so I'd hold off' over 'wind velocity is 32 "
    "km/h, risk threshold exceeded'.\n"
    "- Weave 1-2 concrete numbers in naturally (wind speed, wave height) instead "
    "of listing every metric like a spec sheet.\n"
    "- Mention the data sources briefly and naturally, not as a citation list "
    "(e.g. 'IMD's forecast shows...' not 'Source: IMD Marine Weather Forecast').\n"
    "- Mention which coastal region this is for, conversationally.\n"
    "- Keep it under 110 words. No markdown, asterisks, bullet symbols or '#' — "
    "plain spoken sentences only, as if you were talking, not writing a memo.\n"
    "- Do NOT mirror the user's grammar mistakes; understand their intent and "
    "still reply cleanly and naturally.\n"
    "ROUTE QUERIES: if 'route_summary' is present in the data, this is a "
    "route-safety check between a start and destination point. You MUST "
    "explicitly and unambiguously state whether the ROUTE (not just the "
    "general sea) is safe to sail, and if any stretch of it passes through "
    "a restricted/hazardous zone, name that zone and mention roughly how "
    "many of the sampled points along the path were unsafe. Make it obvious "
    "this is about the whole path from start to destination, e.g. 'the "
    "route you're planning...' — the user has a map showing this path.\n"
    "LANGUAGE & STYLE MATCHING:\n"
    "- Reply entirely in the given 'language': 'en' = English, 'te' = Telugu, "
    "'hi' = Hindi.\n"
    "- If 'script' is 'romanized' (user typed Telugu/Hindi using English "
    "letters, e.g. 'Repu sea loki vellacha?'), reply in the SAME casual "
    "romanized style mixed naturally with English words — the way people "
    "actually text each other — instead of switching to formal native script. "
    "Example tone for romanized Telugu: 'Repu morning sea konchem rough ga "
    "untundi, kabatti fishing ki vellakapovadam better.' If 'script' is "
    "'native', reply in proper native script, still keeping it casual and warm "
    "rather than overly formal/bureaucratic.\n"
    "Return plain text only, nothing else."
)


async def run_synthesizer(session_id: str, message: str, plan: dict,
                          result: dict) -> str:
    data = result.get("data", {})
    payload = {
        "user_question": message,
        "language": plan.get("language", "en"),
        "script": plan.get("script", "native"),
        "intent": plan["intent"],
        "region": f"{result['region']['name']}, {result['region']['state']}",
        "verdict": result.get("verdict"),
        "data": _slim(data),
        "sources": result.get("citations", []),
    }
    if data.get("route"):
        route = data["route"]
        rec = data.get("recommended_pfz")
        dest = f"the recommended fishing zone ({rec['name']})" if rec else "the planned route"
        if route["unsafe_count"] > 0:
            hazard_names = _dedupe([s["reason"] for s in route["segments"] if s.get("reason")])
            payload["route_summary"] = (
                f"{route['unsafe_count']} of {route['total']} sampled points along "
                f"the path to {dest} pass through restricted/hazardous zone(s): "
                f"{', '.join(hazard_names) or 'unspecified'}. "
                + ("This is the LEAST-unsafe of the nearby zones checked — mention this "
                   "clearly and suggest extra caution." if rec else "Route is NOT fully safe.")
            )
        else:
            payload["route_summary"] = (
                f"All {route['total']} sampled points along the path to {dest} are "
                "clear of restricted/hazardous zones."
                + (" Mention that a safe route to this zone has been plotted on the map."
                   if rec else "")
            )
    try:
        prompt = ("Produce the answer from this result JSON:\n"
                  + json.dumps(payload, ensure_ascii=False, default=str))
        text = await _chat_with_fallback(f"{session_id}-synth", SYNTH_SYSTEM, prompt)
        if text and text.strip():
            return text.strip()
    except Exception:
        pass
    return _fallback_answer(plan, result)


def _slim(data: dict) -> dict:
    """Trim large grids out of the synthesizer payload."""
    d = dict(data)
    if "ocean_grid" in d:
        g = d["ocean_grid"]
        d["ocean_grid"] = {"source": g["source"],
                           "sample_count": len(g["grid"])}
    if "boundaries" in d:
        d["boundaries"] = [b["name"] for b in d["boundaries"]]
    return d


def _fallback_answer(plan: dict, result: dict) -> str:
    """Safe-default templated explanation if BOTH LLM providers are down."""
    v = result.get("verdict")
    lang = plan.get("language", "en")
    data = result.get("data", {})
    region_name = f"{result['region']['name']}, {result['region']['state']}"
    if v == "UNSAFE":
        reasons = "; ".join(data.get("safety", {}).get("reasons", []))
        msg = {
            "en": f"⚠️ NOT SAFE to venture out near {region_name}. {reasons} "
                 "Do not assume conditions are safe.",
            "te": f"⚠️ {region_name} దగ్గర సముద్రంలోకి వెళ్లడం సురక్షితం కాదు. {reasons} "
                 "సురక్షితమని భావించవద్దు.",
            "hi": f"⚠️ {region_name} के पास समुद्र में जाना सुरक्षित नहीं है। {reasons} "
                 "इसे सुरक्षित न मानें।",
        }
        return msg.get(lang, msg["en"]) + " (Safe default — AI explanation unavailable.)"
    if v == "SAFE":
        msg = {
            "en": f"Conditions near {region_name} appear within safe limits based on "
                 "the latest demo IMD/INCOIS data. Still check locally before sailing.",
            "te": f"{region_name} దగ్గర పరిస్థితులు సురక్షిత పరిధిలో ఉన్నాయి (డెమో డేటా ఆధారంగా). "
                 "బయలుదేరే ముందు స్థానికంగా నిర్ధారించుకోండి.",
            "hi": f"{region_name} के पास हालात सुरक्षित सीमा में लग रहे हैं (डेमो डेटा के आधार पर)। "
                 "जाने से पहले स्थानीय रूप से पुष्टि कर लें।",
        }
        return msg.get(lang, msg["en"]) + " (AI explanation unavailable.)"
    if plan["intent"] == "pfz_nearest" and data.get("nearest_pfz"):
        z = data["nearest_pfz"][0]
        return (f"Nearest Potential Fishing Zone: {z['name']} (~{z['distance_km']} km), "
                f"SST {z['sst_c']}°C, chlorophyll {z['chl_mg_m3']} mg/m³. "
                "Source: INCOIS PFZ advisory (demo data).")
    if plan["intent"] == "route_safety" and data.get("route"):
        route = data["route"]
        if route["unsafe_count"] > 0:
            hazard_names = _dedupe([s["reason"] for s in route["segments"] if s.get("reason")])
            msg = {
                "en": (f"This route is NOT fully safe — {route['unsafe_count']} of "
                      f"{route['total']} checkpoints along it pass through "
                      f"{', '.join(hazard_names) or 'a restricted zone'}. Consider a "
                      "different path."),
                "te": (f"ఈ మార్గం పూర్తిగా సురక్షితం కాదు — {route['total']} పాయింట్లలో "
                      f"{route['unsafe_count']} {', '.join(hazard_names) or 'నిషేధిత జోన్'} "
                      "గుండా వెళ్తున్నాయి. వేరే మార్గం చూడండి."),
                "hi": (f"यह मार्ग पूरी तरह सुरक्षित नहीं है — {route['total']} में से "
                      f"{route['unsafe_count']} बिंदु {', '.join(hazard_names) or 'प्रतिबंधित क्षेत्र'} "
                      "से गुज़र रहे हैं। कोई दूसरा रास्ता देखें।"),
            }
        else:
            msg = {
                "en": f"This route looks clear — all {route['total']} checkpoints along it are free of restricted/hazardous zones.",
                "te": f"ఈ మార్గం క్లియర్‌గా ఉంది — అన్ని {route['total']} పాయింట్లు సురక్షితంగా ఉన్నాయి.",
                "hi": f"यह मार्ग साफ़ दिख रहा है — सभी {route['total']} बिंदु सुरक्षित हैं।",
            }
        return msg.get(lang, msg["en"]) + (" (AI explanation unavailable — safe-default rule check.)" if lang == "en" else "")
    msg = {
        "en": "Could not verify current conditions from the AI service right now. "
             "Do not assume it is safe — please check local advisories.",
        "te": "ప్రస్తుత పరిస్థితులను ధృవీకరించలేకపోయాం. సురక్షితమని భావించవద్దు — స్థానిక సలహాలను చూడండి.",
        "hi": "मौजूदा हालात की पुष्टि नहीं हो सकी। इसे सुरक्षित न मानें — स्थानीय सलाह ज़रूर देखें।",
    }
    return msg.get(lang, msg["en"])


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------
async def orchestrate(session_id: str, message: str, context: str,
                      user_location: dict | None,
                      region_id: str | None = None,
                      lang_hint: str | None = None) -> dict:
    started = datetime.now(timezone.utc)
    region_hint = mr.get_region(region_id)
    plan = await run_planner(session_id, message, context, region_hint, lang_hint)

    if plan.get("location") and "lat" in plan["location"] and "lon" in plan["location"]:
        # User explicitly named a different coastal place -> snap to it.
        loc = plan["location"]
        resolved_region, dist_km = mr.nearest_region(loc["lat"], loc["lon"])
        resolved_region_id = resolved_region["id"]
    else:
        loc = user_location if user_location and "lat" in user_location else region_hint["center"]
        resolved_region, dist_km = mr.nearest_region(loc["lat"], loc["lon"])
        resolved_region_id = region_id or resolved_region["id"]

    trace = [{"agent": "Planner Agent",
              "detail": (f"Intent='{plan['intent']}', timeframe='{plan.get('timeframe')}', "
                         f"language='{plan.get('language')}', "
                         f"location={loc.get('name') or 'coords'} "
                         f"-> region resolved to {resolved_region['name']}, "
                         f"{resolved_region['state']}.")}]

    result = await run_specialists(plan, loc, resolved_region_id)
    trace.extend(result["trace"])

    answer = await run_synthesizer(session_id, message, plan, result)
    trace.append({"agent": "Synthesizer",
                  "detail": "Combined specialist outputs into one explainable answer."})

    return {
        "answer": answer,
        "verdict": result.get("verdict"),
        "language": plan.get("language", "en"),
        "intent": plan["intent"],
        "citations": result["citations"],
        "widgets": result["widgets"],
        "reasoning_trace": trace,
        "location": loc,
        "region": result["region"],
        "elapsed_ms": int((datetime.now(timezone.utc) - started).total_seconds() * 1000),
    }
