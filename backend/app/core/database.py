"""MongoDB connection, collection access and index management."""
from __future__ import annotations

import logging

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.database import Database

from app.core.config import get_settings

log = logging.getLogger(__name__)

_client: MongoClient | None = None

USERS = "users"
PROJECTS = "projects"
CODE_REVIEWS = "code_reviews"
DEBUG_SESSIONS = "debugging_sessions"
EXPLANATIONS = "code_explanations"
USER_SETTINGS = "user_settings"
# Optimizations and documentation outputs share one collection keyed by "kind".
ARTIFACTS = "code_artifacts"


def get_client() -> MongoClient:
    global _client
    if _client is None:
        s = get_settings()
        _client = MongoClient(s.mongodb_uri, serverSelectionTimeoutMS=5000, tz_aware=True)
    return _client


def get_db() -> Database:
    return get_client()[get_settings().mongodb_db]


def close_client() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


def _user_validator() -> dict:
    return {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["email", "password_hash", "name", "created_at"],
            "properties": {
                "email": {"bsonType": "string", "pattern": "^.+@.+$"},
                "password_hash": {"bsonType": "string", "minLength": 20},
                "name": {"bsonType": "string", "minLength": 1, "maxLength": 100},
            },
        }
    }


def init_db() -> None:
    """Create collections with validators and indexes. Idempotent."""
    db = get_db()
    existing = set(db.list_collection_names())
    if USERS not in existing:
        db.create_collection(USERS, validator=_user_validator())
    else:
        db.command("collMod", USERS, validator=_user_validator())
    for name in (PROJECTS, CODE_REVIEWS, DEBUG_SESSIONS, EXPLANATIONS, USER_SETTINGS, ARTIFACTS):
        if name not in existing:
            db.create_collection(name)

    db[USERS].create_index([("email", ASCENDING)], unique=True)
    db[USER_SETTINGS].create_index([("user_id", ASCENDING)], unique=True)
    db[PROJECTS].create_index([("user_id", ASCENDING), ("updated_at", DESCENDING)])
    db[PROJECTS].create_index([("user_id", ASCENDING), ("name", ASCENDING)], unique=True)

    db[CODE_REVIEWS].create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
    db[CODE_REVIEWS].create_index([("user_id", ASCENDING), ("language", ASCENDING)])
    db[CODE_REVIEWS].create_index([("user_id", ASCENDING), ("max_severity", ASCENDING)])
    db[CODE_REVIEWS].create_index([("user_id", ASCENDING), ("project_id", ASCENDING)])
    # Note: no text index on code_reviews. MongoDB treats a document's "language" field as the
    # text-index stemming language and rejects values like "python". Search uses an escaped,
    # case-insensitive regex on title/filename, scoped by the user_id index.
    if "review_text" in db[CODE_REVIEWS].index_information():
        db[CODE_REVIEWS].drop_index("review_text")

    for name in (DEBUG_SESSIONS, EXPLANATIONS, ARTIFACTS):
        db[name].create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
    db[ARTIFACTS].create_index([("user_id", ASCENDING), ("kind", ASCENDING)])
    log.info("MongoDB indexes ensured")
