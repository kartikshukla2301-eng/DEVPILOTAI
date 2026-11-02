import json
import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from pymongo import DESCENDING

from app.core.database import ARTIFACTS, CODE_REVIEWS, DEBUG_SESSIONS, EXPLANATIONS, get_db
from app.core.security import get_current_user, parse_object_id
from app.routes.common import paginate, serialize
from app.schemas import SUPPORTED_LANGUAGES, Paginated
from app.services.report import review_markdown

router = APIRouter(prefix="/history", tags=["history"])

REVIEW_LIST_PROJECTION = {"code": 0, "findings": 0, "suggested_code": 0, "metrics": 0, "ai_summary": 0, "disclaimer": 0}
ACTIVITY_SOURCES = {
    "review": (CODE_REVIEWS, {}),
    "debug": (DEBUG_SESSIONS, {}),
    "explain": (EXPLANATIONS, {}),
    "optimize": (ARTIFACTS, {"kind": "optimization"}),
    "documentation": (ARTIFACTS, {"kind": "documentation"}),
}


@router.get("/reviews", response_model=Paginated)
def list_reviews(
    search: str | None = Query(None, max_length=100),
    language: str | None = Query(None),
    severity: Literal["critical", "high", "medium", "low", "info"] | None = None,
    project_id: str | None = None,
    sort: Literal["newest", "oldest", "score_asc", "score_desc"] = "newest",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_current_user),
) -> dict:
    q: dict = {"user_id": user["_id"]}
    if search:
        rx = {"$regex": re.escape(search.strip()), "$options": "i"}
        q["$or"] = [{"title": rx}, {"filename": rx}]
    if language:
        if language not in SUPPORTED_LANGUAGES:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unsupported language filter")
        q["language"] = language
    if severity:
        q[f"summary.{severity}"] = {"$gt": 0}
    if project_id:
        q["project_id"] = parse_object_id(project_id, "project")
    order = {"newest": [("created_at", DESCENDING)], "oldest": [("created_at", 1)],
             "score_asc": [("score", 1), ("created_at", DESCENDING)], "score_desc": [("score", DESCENDING), ("created_at", DESCENDING)]}[sort]
    res = paginate(get_db()[CODE_REVIEWS], q, page, page_size, order, {**REVIEW_LIST_PROJECTION, "findings": {"$slice": 1}})
    for item in res["items"]:
        top = (item.pop("findings", None) or [None])[0]
        item["top_finding"] = {k: top.get(k) for k in ("title", "severity", "category", "line", "source")} if top else None
    return res


@router.get("/stats")
def review_stats(user: dict = Depends(get_current_user)) -> dict:
    """Aggregate counts for the history header and severity filter chips."""
    agg = list(get_db()[CODE_REVIEWS].aggregate([
        {"$match": {"user_id": user["_id"]}},
        {"$group": {
            "_id": None, "total": {"$sum": 1}, "avg_score": {"$avg": "$score"},
            "findings": {"$sum": "$total_findings"},
            **{f"with_{s}": {"$sum": {"$cond": [{"$gt": [f"$summary.{s}", 0]}, 1, 0]}} for s in ("critical", "high", "medium", "low", "info")},
            **{f"sum_{s}": {"$sum": f"$summary.{s}"} for s in ("critical", "high", "medium")},
            "clean": {"$sum": {"$cond": [{"$and": [{"$eq": ["$summary.critical", 0]}, {"$eq": ["$summary.high", 0]}]}, 1, 0]}},
            "grade_a": {"$sum": {"$cond": [{"$eq": ["$grade", "A"]}, 1, 0]}},
            "ai": {"$sum": {"$cond": ["$ai_used", 1, 0]}},
        }},
    ]))
    a = agg[0] if agg else {}
    a.pop("_id", None)
    langs = [{"language": r["_id"], "count": r["n"]} for r in get_db()[CODE_REVIEWS].aggregate([
        {"$match": {"user_id": user["_id"]}}, {"$group": {"_id": "$language", "n": {"$sum": 1}}}, {"$sort": {"n": -1}}])]
    return {
        "total": a.get("total", 0), "avg_score": round(a["avg_score"]) if a.get("avg_score") is not None else None,
        "findings": a.get("findings", 0), "clean": a.get("clean", 0), "grade_a": a.get("grade_a", 0), "ai": a.get("ai", 0),
        "with_severity": {s: a.get(f"with_{s}", 0) for s in ("critical", "high", "medium", "low", "info")},
        "severity_totals": {s: a.get(f"sum_{s}", 0) for s in ("critical", "high", "medium")},
        "languages": langs,
    }


def _review(review_id: str, user: dict) -> dict:
    doc = get_db()[CODE_REVIEWS].find_one({"_id": parse_object_id(review_id, "review"), "user_id": user["_id"]})
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Review not found")
    return doc


@router.get("/reviews/{review_id}")
def get_review(review_id: str, user: dict = Depends(get_current_user)) -> dict:
    return serialize(_review(review_id, user))  # type: ignore[return-value]


@router.delete("/reviews/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_review(review_id: str, user: dict = Depends(get_current_user)) -> None:
    res = get_db()[CODE_REVIEWS].delete_one({"_id": parse_object_id(review_id, "review"), "user_id": user["_id"]})
    if res.deleted_count == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Review not found")


@router.get("/reviews/{review_id}/export")
def export_review(review_id: str, format: Literal["md", "json"] = "md", user: dict = Depends(get_current_user)) -> Response:
    doc = _review(review_id, user)
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", f"devpilot-review-{doc.get('filename', 'code')}-{str(doc['_id'])[-6:]}")
    if format == "json":
        data = serialize(doc) or {}
        data.pop("user_id", None)
        body = json.dumps(data, default=str, indent=2, ensure_ascii=False)
        return Response(body, media_type="application/json", headers={"Content-Disposition": f'attachment; filename="{base}.json"'})
    return Response(review_markdown(doc), media_type="text/markdown; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{base}.md"'})


@router.get("/activity", response_model=Paginated)
def activity(
    type: Literal["all", "review", "debug", "explain", "optimize", "documentation"] = "all",
    search: str | None = Query(None, max_length=100),
    language: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_current_user),
) -> dict:
    """Unified, paginated feed across all modules (newest first)."""
    db = get_db()
    base: dict = {"user_id": user["_id"]}
    if language:
        base["language"] = language
    if search:
        base["title"] = {"$regex": re.escape(search.strip()), "$options": "i"}
    sources = ACTIVITY_SOURCES if type == "all" else {type: ACTIVITY_SOURCES[type]}
    proj = {"title": 1, "language": 1, "created_at": 1, "score": 1, "grade": 1, "error_type": 1, "ai_used": 1, "summary": 1, "level": 1, "filename": 1}
    need = page * page_size
    merged, total = [], 0
    for kind, (coll, extra) in sources.items():
        q = {**base, **extra}
        total += db[coll].count_documents(q)
        for d in db[coll].find(q, proj).sort("created_at", DESCENDING).limit(need):
            item = serialize(d) or {}
            item["type"] = kind
            merged.append(item)
    merged.sort(key=lambda x: x["created_at"], reverse=True)
    items = merged[(page - 1) * page_size: page * page_size]
    return {"items": items, "total": total, "page": page, "page_size": page_size, "pages": max(1, -(-total // page_size))}


@router.delete("/activity/{kind}/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_activity(kind: Literal["review", "debug", "explain", "optimize", "documentation"], item_id: str, user: dict = Depends(get_current_user)) -> None:
    coll, extra = ACTIVITY_SOURCES[kind]
    res = get_db()[coll].delete_one({"_id": parse_object_id(item_id, "record"), "user_id": user["_id"], **extra})
    if res.deleted_count == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Record not found")
