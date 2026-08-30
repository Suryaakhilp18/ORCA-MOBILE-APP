"""Agent orchestration: planner + specialist agents + synthesizer.

Reasoning is a planner→specialists→synthesizer pipeline. CRITICAL: every safety
verdict (safe/unsafe, hazard proximity, geofence breach) is decided by the
deterministic rule checks in `rules.py` against real data/spatial queries — the
LLM only EXPLAINS the rule-based verdict in natural, localised language.
"""
