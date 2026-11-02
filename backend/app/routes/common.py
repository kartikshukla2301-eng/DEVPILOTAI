import math
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from fastapi import HTTPException, Request, status

from app.core.config import get_settings
from app.core.database import USER_SETTINGS, get_db

DEFAULT_SETTINGS = {"theme": "dark", "default_language": "python", "explanation_level": "intermediate", "use_ai": True}


def now() -> datetime:
    return datetime.now(timezone.utc)


def serialize(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    """Convert a Mongo document to JSON-friendly dict: _id -> id, ObjectIds -> str."""
    if doc is None:
        return None
    out: dict[str, Any] = {}
    for k, v in doc.items():
        if k == "_id":
            out["id"] = str(v)
        elif isinstance(v, ObjectId):
            out[k] = str(v)
        elif isinstance(v, list):
            out[k] = [serialize(x) if isinstance(x, dict) else (str(x) if isinstance(x, ObjectId) else x) for x in v]
        elif isinstance(v, dict):
            out[k] = serialize(v)
        else:
            out[k] = v
    return out


def user_settings(user_id: ObjectId) -> dict[str, Any]:
    doc = get_db()[USER_SETTINGS].find_one({"user_id": user_id}) or {}
    return {**DEFAULT_SETTINGS, **{k: v for k, v in doc.items() if k in DEFAULT_SETTINGS}, "updated_at": doc.get("updated_at")}


def ensure_code_size(code: str) -> None:
    limit = get_settings().max_code_chars
    if len(code) > limit:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"Code is too large ({len(code):,} characters; limit is {limit:,}).")


def paginate(collection, query: dict, page: int, page_size: int, sort: list[tuple[str, int]], projection: dict | None = None) -> dict[str, Any]:
    total = collection.count_documents(query)
    cursor = collection.find(query, projection).sort(sort).skip((page - 1) * page_size).limit(page_size)
    return {"items": [serialize(d) for d in cursor], "total": total, "page": page, "page_size": page_size,
            "pages": max(1, math.ceil(total / page_size)) if total else 1}


class RateLimiter:
    """Small in-process sliding-window limiter (per client IP). Use a shared store (Redis) when running multiple workers."""

    def __init__(self, limit: int, window_s: int) -> None:
        self.limit, self.window = limit, window_s
        self.hits: dict[str, deque[float]] = defaultdict(deque)
        self.lock = threading.Lock()

    def __call__(self, request: Request) -> None:
        key = request.client.host if request.client else "unknown"
        t = time.monotonic()
        with self.lock:
            q = self.hits[key]
            while q and t - q[0] > self.window:
                q.popleft()
            if len(q) >= self.limit:
                raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts. Please wait a minute and try again.")
            q.append(t)


auth_limiter = RateLimiter(limit=10, window_s=60)
analysis_limiter = RateLimiter(limit=60, window_s=60)
