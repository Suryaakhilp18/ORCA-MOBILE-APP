"""Geospatial / Risk layer.

Mongo (with 2dsphere indexes) is the authoritative source of truth for all
spatial queries — nearest-PFZ lookups, point-in-polygon geofence checks and
route-segment safety. These are NEVER computed on the client and NEVER guessed
by the LLM.
"""
