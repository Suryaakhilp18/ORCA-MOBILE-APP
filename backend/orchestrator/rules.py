"""Deterministic safety rules — the authoritative verdict engine.

The LLM never decides safety. These threshold checks run against real
weather/spatial data and produce the verdict the synthesizer must explain.
"""

# Small-craft thresholds
WIND_UNSAFE_KN = 25
WAVE_UNSAFE_M = 2.5
LIGHTNING_UNSAFE_PCT = 60

WIND_CAUTION_KN = 18
WAVE_CAUTION_M = 1.8
LIGHTNING_CAUTION_PCT = 30


def evaluate_sea_safety(weather: dict) -> dict:
    """Return {verdict, reasons[], factors} from a weather adapter payload."""
    reasons = []
    unsafe = False
    caution = False

    wind = weather.get("wind_kn", 0)
    wave = weather.get("wave_m", 0)
    lightning = weather.get("lightning_pct", 0)
    cyclone = weather.get("cyclone")

    if cyclone:
        unsafe = True
        reasons.append(f"Active cyclonic system: {cyclone}.")
    if wind >= WIND_UNSAFE_KN:
        unsafe = True
        reasons.append(f"Wind {wind} kn exceeds safe limit ({WIND_UNSAFE_KN} kn).")
    elif wind >= WIND_CAUTION_KN:
        caution = True
        reasons.append(f"Elevated wind {wind} kn — handle with caution.")

    if wave >= WAVE_UNSAFE_M:
        unsafe = True
        reasons.append(f"Wave height {wave} m exceeds safe limit ({WAVE_UNSAFE_M} m).")
    elif wave >= WAVE_CAUTION_M:
        caution = True
        reasons.append(f"Moderate waves {wave} m — handle with caution.")

    if lightning >= LIGHTNING_UNSAFE_PCT:
        unsafe = True
        reasons.append(f"High lightning probability {lightning}%.")
    elif lightning >= LIGHTNING_CAUTION_PCT:
        caution = True
        reasons.append(f"Some lightning risk {lightning}%.")

    if unsafe:
        verdict = "UNSAFE"
    elif caution:
        verdict = "CAUTION"
    else:
        verdict = "SAFE"
        reasons.append("Wind, wave and lightning conditions are within safe limits.")

    return {
        "verdict": verdict,
        "reasons": reasons,
        "factors": {
            "wind_kn": wind, "wave_m": wave,
            "lightning_pct": lightning, "cyclone": cyclone,
        },
    }


def compute_situation_severity(verdict: str, alerts: list[dict]) -> str:
    """Deterministic 3-tier alert severity for the Alerts tab: the LLM never
    decides this — it is purely a function of the rule-based sea-safety
    verdict plus any active hazard bulletins' own severity field.
    critical > warning > advisory (the calm/default state)."""
    has_high = any(a.get("severity") == "high" for a in alerts)
    has_moderate = any(a.get("severity") == "moderate" for a in alerts)
    if verdict == "UNSAFE" or has_high:
        return "critical"
    if verdict == "CAUTION" or has_moderate:
        return "warning"
    return "advisory"
