"""Shared Mongo client + serialization helpers (Mongo stands in for PostGIS here).

ObjectId is not JSON serializable, so every read strips `_id`. Spatial data
(boundaries, PFZ points) is stored as GeoJSON with 2dsphere indexes so that the
DB — never the client — is the authoritative source of truth for spatial queries.
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]


def clean(doc: dict) -> dict:
    """Drop Mongo's internal _id so documents are JSON-serializable."""
    if not doc:
        return doc
    doc = dict(doc)
    doc.pop("_id", None)
    return doc
