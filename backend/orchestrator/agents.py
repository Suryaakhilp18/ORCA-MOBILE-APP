"""Planner + specialist agents + synthesizer pipeline."""
import json
import os
import re
from datetime import datetime, timezone

from emergentintegrations.llm.chat import LlmChat, UserMessage

from data_adapters import mock_region as mr
from gis import spatial
from orchestrator.rules import evaluate_sea_safety

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
MODEL = ("openai", "gpt-5.6-luna")

INTENTS = [
    "pfz_nearest", "safety_sail", "conditions", "alerts_query",
    "chlorophyll_sst", "route_safety", "geofence_avoid",
    "productivity_decline", "general",
]

DEFAULT_LOC = {"name": mr.REGION["name"],
               "lat": mr.REGION["center"]["lat"],
               "lon": mr.REGION["center"]["lon"]}


def _llm(session_id: str, system: str) -> LlmChat:
    return LlmChat(api_key=EMERGENT_LLM_KEY, session_id=session_id,
                   system_message=system).with_model(*MODEL)


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
PLANNER_SYSTEM = (
    "You are the PLANNER agent of ORCA, a marine intelligence assistant for the "
    "Kakinada (Andhra Pradesh, India) coast. Decompose the user's message into a "
    "plan. Respond with STRICT JSON only, no prose. Schema:\n"
    "{\n"
    '  "intent": one of ["pfz_nearest","safety_sail","conditions","alerts_query",'
    '"chlorophyll_sst","route_safety","geofence_avoid","productivity_decline","general"],\n'
    '  "timeframe": "today" | "tomorrow",\n'
    '  "language": "en" | "te"  (te = Telugu; detect from the user text),\n'
    '  "location": {"name": string, "lat": number, "lon": number} | null,\n'
    '  "route": {"start":{"lat":number,"lon":number},"end":{"lat":number,"lon":number}} | null,\n'
    '  "datasets": string[]  (subset of ["pfz","weather","sst","chl","tide","alerts","boundaries"])\n'
    "}\n"
    "If the user references a place without coordinates, estimate lat/lon near the "
    "Kakinada coast. If no location is given, set location to null."
)


async def run_planner(session_id: str, message: str, context: str) -> dict:
    chat = _llm(f"{session_id}-plan", PLANNER_SYSTEM)
    prompt = f"Conversation so far:\n{context}\n\nUser message: {message}"
    resp = await chat.send_message(UserMessage(text=prompt))
    plan = _extract_json(resp)
    if plan.get("intent") not in INTENTS:
        plan = _keyword_plan(message)
    return plan


def _keyword_plan(message: str) -> dict:
    """Deterministic fallback if the planner LLM is unavailable."""
    m = message.lower()
    te = bool(re.search(r"[\u0c00-\u0c7f]", message))  # Telugu unicode block
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
    return {"intent": intent, "timeframe": timeframe,
            "language": "te" if te else "en", "location": None,
            "route": None, "datasets": []}


# ---------------------------------------------------------------------------
# Specialist agents — deterministic data gathering + rule checks
# ---------------------------------------------------------------------------
async def run_specialists(plan: dict, loc: dict) -> dict:
    """Invoke the specialist agents relevant to the intent. Returns a bundle
    of data, the deterministic verdict, citations, widgets and a trace."""
    intent = plan["intent"]
    timeframe = plan.get("timeframe", "today")
    trace = []
    citations = []
    widgets = []
    data = {}
    verdict = None

    # Data Discovery Agent
    needed = _discover(intent)
    trace.append({"agent": "Data Discovery Agent",
                  "detail": f"Query intent '{intent}' needs: {', '.join(needed)}."})

    # Weather Intelligence Agent
    if "weather" in needed:
        weather = mr.get_weather(timeframe)
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
        grid = mr.get_sst_chl_grid()
        data["ocean_grid"] = grid
        citations.append(f"{grid['source']} (mock)")
        trace.append({"agent": "Ocean Analytics Agent",
                      "detail": ("Correlated SST & chlorophyll grid; higher chlorophyll "
                                 "with SST 27-29°C indicates favourable feeding zones.")})

    # Geospatial / Risk Agent
    if intent == "pfz_nearest":
        zones = await spatial.nearest_pfz(loc["lat"], loc["lon"], limit=3)
        data["nearest_pfz"] = zones
        adv = mr.get_pfz_advisory()
        citations.append(f"{adv['source']} (mock)")
        trace.append({"agent": "Geospatial/Risk Agent",
                      "detail": (f"PostGIS-style $geoNear from ({loc['lat']},{loc['lon']}) "
                                 f"returned {len(zones)} PFZ sorted by distance.")})
    if intent in ("geofence_avoid", "conditions", "safety_sail"):
        breaches = await spatial.geofence_check(loc["lat"], loc["lon"])
        data["geofence"] = breaches
        bnds = await spatial.all_boundaries()
        data["boundaries"] = bnds
        citations.append("Bundled maritime boundary layer (EEZ/MPA/restricted)")
        trace.append({"agent": "Geospatial/Risk Agent",
                      "detail": (f"Point-in-polygon check: {len(breaches)} boundary "
                                 f"breach(es) at location; {len(bnds)} boundaries loaded.")})
        if intent == "geofence_avoid":
            restricted = [b for b in (await spatial.all_boundaries())
                          if b.get("restricted")]
            data["avoid_zones"] = restricted
    if intent == "route_safety" and plan.get("route"):
        route = plan["route"]
        rr = await spatial.route_safety(route["start"], route["end"])
        weather = mr.get_weather(timeframe)
        data["weather"] = weather
        safety = evaluate_sea_safety(weather)
        data["safety"] = safety
        # Route unsafe if any segment breaches restricted zone OR weather unsafe
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
        tide = mr.get_tide_table()
        data["tide"] = tide
        citations.append(f"{tide['source']} (mock)")
    if "alerts" in needed or intent == "alerts_query":
        alerts = mr.get_active_alerts()
        data["alerts"] = alerts
        for a in alerts:
            citations.append(f"{a['source']} (mock)")
        trace.append({"agent": "Weather Intelligence Agent",
                      "detail": f"{len(alerts)} active IMD hazard bulletin(s) for region."})

    # Reporting / Visualization Agent — build widget payloads
    widgets = _build_widgets(intent, loc, data)
    trace.append({"agent": "Reporting/Visualization Agent",
                  "detail": f"Prepared {len(widgets)} inline widget(s) for the client."})

    return {"data": data, "verdict": verdict, "citations": _dedupe(citations),
            "widgets": widgets, "trace": trace}


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
        sst = mr.get_sst_trend()
        chl = mr.get_chl_trend()
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
    "You are the SYNTHESIZER agent of ORCA. You receive a machine-computed result "
    "with a DETERMINISTIC safety verdict and the data that produced it. Write ONE "
    "clear, calm, conversational answer for a fisherman.\n"
    "HARD RULES:\n"
    "- NEVER change or contradict the given verdict. If verdict is UNSAFE, you must "
    "clearly tell the user it is not safe. If data is missing, say conditions could "
    "not be verified and to not assume it is safe.\n"
    "- Cite the contributing data sources naturally (e.g. 'Based on IMD wind "
    "forecast and INCOIS PFZ advisory...').\n"
    "- Keep it under 130 words. Be specific with numbers.\n"
    "- Do NOT use any markdown, asterisks, bullet symbols or '#'. Plain sentences only.\n"
    "- Respond ENTIRELY in the requested language: 'en' = English, 'te' = Telugu "
    "(use Telugu script).\n"
    "Return plain text only."
)


async def run_synthesizer(session_id: str, message: str, plan: dict,
                          result: dict) -> str:
    payload = {
        "user_question": message,
        "language": plan.get("language", "en"),
        "intent": plan["intent"],
        "verdict": result.get("verdict"),
        "data": _slim(result.get("data", {})),
        "sources": result.get("citations", []),
    }
    try:
        chat = _llm(f"{session_id}-synth", SYNTH_SYSTEM)
        prompt = ("Produce the answer from this result JSON:\n"
                  + json.dumps(payload, ensure_ascii=False, default=str))
        text = await chat.send_message(UserMessage(text=prompt))
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
    """Safe-default templated explanation if the LLM is unavailable."""
    v = result.get("verdict")
    data = result.get("data", {})
    if v == "UNSAFE":
        reasons = "; ".join(data.get("safety", {}).get("reasons", []))
        return ("⚠️ NOT SAFE to venture out. " + reasons +
                " Do not assume conditions are safe. (Auto-generated safe default — "
                "AI explanation unavailable.)")
    if v == "SAFE":
        return ("Conditions appear within safe limits based on the latest mock "
                "IMD/INCOIS data. Still verify locally before sailing. "
                "(Auto-generated — AI explanation unavailable.)")
    if plan["intent"] == "pfz_nearest" and data.get("nearest_pfz"):
        z = data["nearest_pfz"][0]
        return (f"Nearest Potential Fishing Zone: {z['name']} (~{z['distance_km']} km), "
                f"SST {z['sst_c']}°C, chlorophyll {z['chl_mg_m3']} mg/m³. "
                "Source: INCOIS PFZ advisory (mock).")
    return ("Could not verify current conditions from the AI service. Do not assume "
            "it is safe — please check local advisories.")


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------
async def orchestrate(session_id: str, message: str, context: str,
                      user_location: dict | None) -> dict:
    started = datetime.now(timezone.utc)
    plan = await run_planner(session_id, message, context)

    loc = plan.get("location") or user_location or DEFAULT_LOC
    if "lat" not in loc or "lon" not in loc:
        loc = DEFAULT_LOC

    trace = [{"agent": "Planner Agent",
              "detail": (f"Intent='{plan['intent']}', timeframe='{plan.get('timeframe')}', "
                         f"language='{plan.get('language')}', "
                         f"location={loc.get('name', 'coords')}.")}]

    result = await run_specialists(plan, loc)
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
        "elapsed_ms": int((datetime.now(timezone.utc) - started).total_seconds() * 1000),
    }
