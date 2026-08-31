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
    if intent == "pfz_nearest":
        zones = await spatial.nearest_pfz(loc["lat"], loc["lon"], limit=3)
        data["nearest_pfz"] = zones
        adv = mr.get_pfz_advisory(region_id)
        citations.append(f"{adv['source']} (mock)")
        trace.append({"agent": "Geospatial/Risk Agent",
                      "detail": (f"Nationwide PostGIS-style $geoNear from "
                                 f"({loc['lat']},{loc['lon']}) returned "
                                 f"{len(zones)} PFZ sorted by distance.")})
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
        "safety_sail": ["weather", "alerts", "tide"],
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
        for z in data["nearest_pfz"]:
            markers.append({"lat": z["lat"], "lon": z["lon"],
                            "label": f"{z['name']} ({z['distance_km']} km)",
                            "kind": "pfz"})
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
        for s in data["route"]["segments"]:
            markers.append({"lat": s["lat"], "lon": s["lon"],
                            "label": s["reason"] or ("safe" if s["safe"] else "unsafe"),
                            "kind": "route_safe" if s["safe"] else "route_unsafe"})

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
    payload = {
        "user_question": message,
        "language": plan.get("language", "en"),
        "script": plan.get("script", "native"),
        "intent": plan["intent"],
        "region": f"{result['region']['name']}, {result['region']['state']}",
        "verdict": result.get("verdict"),
        "data": _slim(result.get("data", {})),
        "sources": result.get("citations", []),
    }
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
