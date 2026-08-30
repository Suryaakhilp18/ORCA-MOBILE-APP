"""Data adapters.

Each source is wrapped behind an adapter so it can degrade gracefully or be
swapped for mock data without touching the orchestrator. For this MVP every
adapter serves clearly-labelled MOCK data (`is_mock: True`) for the demo region
of Kakinada, Andhra Pradesh. Real feeds (INCOIS / IMD / ISRO-Bhuvan) can later
replace the mock bodies without changing their return contract.
"""
