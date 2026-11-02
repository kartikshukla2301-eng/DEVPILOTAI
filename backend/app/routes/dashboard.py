from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from pymongo import DESCENDING

from app.core.database import ARTIFACTS, CODE_REVIEWS, DEBUG_SESSIONS, EXPLANATIONS, PROJECTS, get_db
from app.core.security import get_current_user
from app.routes.common import now, serialize
from app.services import ai

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def summary(tz_offset_minutes: int = Query(0, ge=-840, le=840), user: dict = Depends(get_current_user)) -> dict:
    """All statistics are computed from the user's stored records.

    tz_offset_minutes: client offset from UTC (e.g. +330 for IST) so daily buckets match the user's calendar.
    """
    db = get_db()
    uid = user["_id"]
    reviews = db[CODE_REVIEWS]

    agg = list(reviews.aggregate([
        {"$match": {"user_id": uid}},
        {"$group": {
            "_id": None, "count": {"$sum": 1}, "avg_score": {"$avg": "$score"},
            "bugs": {"$sum": "$category_summary.bug"}, "security": {"$sum": "$category_summary.security"},
            "quality": {"$sum": "$category_summary.quality"}, "performance": {"$sum": "$category_summary.performance"},
            "critical": {"$sum": "$summary.critical"}, "high": {"$sum": "$summary.high"}, "medium": {"$sum": "$summary.medium"},
            "low": {"$sum": "$summary.low"}, "info": {"$sum": "$summary.info"}, "lines": {"$sum": "$metrics.lines_total"},
            "ai_reviews": {"$sum": {"$cond": ["$ai_used", 1, 0]}},
        }},
    ]))
    a = agg[0] if agg else {}

    languages = [{"language": r["_id"], "count": r["n"]} for r in reviews.aggregate([
        {"$match": {"user_id": uid}}, {"$group": {"_id": "$language", "n": {"$sum": 1}}}, {"$sort": {"n": -1}}])]

    counts = {
        "reviews": a.get("count", 0),
        "debug_sessions": db[DEBUG_SESSIONS].count_documents({"user_id": uid}),
        "explanations": db[EXPLANATIONS].count_documents({"user_id": uid}),
        "optimizations": db[ARTIFACTS].count_documents({"user_id": uid, "kind": "optimization"}),
        "documentation": db[ARTIFACTS].count_documents({"user_id": uid, "kind": "documentation"}),
        "projects": db[PROJECTS].count_documents({"user_id": uid}),
    }

    # Daily activity for the last 7 days (in the user's local calendar)
    offset = timedelta(minutes=tz_offset_minutes)
    local_today = (now() + offset).date()
    days = [local_today - timedelta(days=i) for i in range(6, -1, -1)]
    start_utc = (now() + offset).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=6) - offset
    weekly = {d.isoformat(): {"date": d.isoformat(), "label": d.strftime("%a"), "reviews": 0, "debug": 0, "explain": 0, "other": 0,
                              "total": 0, "findings": 0} for d in days}
    tz = f"{'+' if tz_offset_minutes >= 0 else '-'}{abs(tz_offset_minutes) // 60:02d}{abs(tz_offset_minutes) % 60:02d}"
    for coll, key, extra in ((CODE_REVIEWS, "reviews", {}), (DEBUG_SESSIONS, "debug", {}), (EXPLANATIONS, "explain", {}), (ARTIFACTS, "other", {})):
        for r in db[coll].aggregate([
            {"$match": {"user_id": uid, "created_at": {"$gte": start_utc}, **extra}},
            {"$group": {"_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at", "timezone": tz}}, "n": {"$sum": 1},
                        "f": {"$sum": {"$ifNull": ["$total_findings", 0]}}}},
        ]):
            if r["_id"] in weekly:
                weekly[r["_id"]][key] += r["n"]
                weekly[r["_id"]]["total"] += r["n"]
                if key == "reviews":
                    weekly[r["_id"]]["findings"] += r["f"]

    # Most recent critical/high findings across saved reviews (findings are stored worst-first).
    top_findings = []
    for r in reviews.find({"user_id": uid, "$or": [{"summary.critical": {"$gt": 0}}, {"summary.high": {"$gt": 0}}]},
                          {"title": 1, "filename": 1, "language": 1, "created_at": 1, "findings": {"$slice": 3}}
                          ).sort("created_at", DESCENDING).limit(6):
        for f in r.get("findings", []):
            if f.get("severity") in ("critical", "high") and len(top_findings) < 4:
                top_findings.append({"review_id": str(r["_id"]), "filename": r.get("filename"), "language": r.get("language"),
                                     "created_at": r["created_at"], "title": f.get("title"), "severity": f.get("severity"),
                                     "category": f.get("category"), "line": f.get("line"), "recommendation": f.get("recommendation"),
                                     "snippet": f.get("snippet"), "source": f.get("source", "static")})

    score_trend = [{"date": r["created_at"], "score": r["score"], "title": r.get("title")}
                   for r in reviews.find({"user_id": uid}, {"score": 1, "created_at": 1, "title": 1}).sort("created_at", DESCENDING).limit(12)][::-1]

    recent_reviews = [serialize(d) for d in reviews.find(
        {"user_id": uid}, {"title": 1, "filename": 1, "language": 1, "score": 1, "grade": 1, "summary": 1, "created_at": 1, "ai_used": 1, "total_findings": 1}
    ).sort("created_at", DESCENDING).limit(5)]

    projects = list(db[PROJECTS].find({"user_id": uid}).sort("updated_at", DESCENDING).limit(5))
    pcounts = {r["_id"]: r for r in reviews.aggregate([
        {"$match": {"user_id": uid, "project_id": {"$in": [p["_id"] for p in projects]}}},
        {"$group": {"_id": "$project_id", "n": {"$sum": 1}, "avg": {"$avg": "$score"}}}])}
    recent_projects = [{**serialize(p), "review_count": pcounts.get(p["_id"], {}).get("n", 0),  # type: ignore[dict-item]
                        "avg_score": round(pcounts[p["_id"]]["avg"]) if p["_id"] in pcounts else None} for p in projects]

    activity = []
    for coll, kind, extra in ((CODE_REVIEWS, "review", {}), (DEBUG_SESSIONS, "debug", {}), (EXPLANATIONS, "explain", {}),
                              (ARTIFACTS, "optimize", {"kind": "optimization"}), (ARTIFACTS, "documentation", {"kind": "documentation"})):
        for d in db[coll].find({"user_id": uid, **extra}, {"title": 1, "language": 1, "created_at": 1, "score": 1, "error_type": 1}).sort("created_at", DESCENDING).limit(8):
            activity.append({**serialize(d), "type": kind})  # type: ignore[dict-item]
    activity.sort(key=lambda x: x["created_at"], reverse=True)

    total_activity = sum(counts[k] for k in ("reviews", "debug_sessions", "explanations", "optimizations", "documentation"))
    return {
        "is_empty": total_activity == 0,
        "totals": {
            "reviews": counts["reviews"],
            "bugs": a.get("bugs", 0),
            "security_issues": a.get("security", 0),
            "quality_issues": a.get("quality", 0),
            "performance_issues": a.get("performance", 0),
            "avg_score": round(a["avg_score"]) if a.get("avg_score") is not None else None,
            "lines_analyzed": a.get("lines", 0),
            "ai_reviews": a.get("ai_reviews", 0),
        },
        "usage": counts,
        "severity_distribution": [{"severity": s, "count": a.get(s, 0)} for s in ("critical", "high", "medium", "low", "info")],
        "language_distribution": languages,
        "weekly_activity": list(weekly.values()),
        "score_trend": score_trend,
        "recent_reviews": recent_reviews,
        "recent_projects": recent_projects,
        "recent_activity": activity[:10],
        "top_findings": top_findings,
        "week_total": sum(d["total"] for d in weekly.values()),
        "ai_mode": "ai" if ai.ai_available() else "local",
    }
