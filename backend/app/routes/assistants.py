"""Debugging, explanation, optimization and documentation endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from pymongo import DESCENDING

from app.core.database import ARTIFACTS, DEBUG_SESSIONS, EXPLANATIONS, get_db
from app.core.security import get_current_user, parse_object_id
from app.routes.common import analysis_limiter, ensure_code_size, paginate, serialize, user_settings
from app.schemas import DebugIn, DebugOut, DocsIn, DocsOut, ExplainIn, ExplainOut, OptimizeIn, OptimizeOut, Paginated
from app.services import ai
from app.services.debugger import run_debug
from app.services.docgen import run_docs
from app.services.explainer import run_explain
from app.services.optimizer import run_optimize

debug_router = APIRouter(prefix="/debug", tags=["debug"])
explain_router = APIRouter(prefix="/explain", tags=["explain"])
optimize_router = APIRouter(prefix="/optimize", tags=["optimize"])
docs_router = APIRouter(prefix="/documentation", tags=["documentation"])

LIST_PROJECTION = {"code": 0, "lines": 0, "optimized_code": 0, "original_code": 0, "markdown": 0, "suggested_code": 0}


def _allow_ai(requested: bool, user: dict) -> bool:
    return ai.should_use_ai(requested, user_settings(user["_id"])["use_ai"])


def _get(coll: str, item_id: str, user: dict, what: str, extra: dict | None = None) -> dict:
    doc = get_db()[coll].find_one({"_id": parse_object_id(item_id, what), "user_id": user["_id"], **(extra or {})})
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{what.capitalize()} not found")
    return doc


def _delete(coll: str, item_id: str, user: dict, what: str, extra: dict | None = None) -> None:
    res = get_db()[coll].delete_one({"_id": parse_object_id(item_id, what), "user_id": user["_id"], **(extra or {})})
    if res.deleted_count == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{what.capitalize()} not found")


def _title(code: str, filename: str | None) -> str:
    if filename:
        return filename
    first = next((ln.strip() for ln in code.splitlines() if ln.strip()), "snippet")
    return first[:60]


# ----------------------------------------------------------------- debug
@debug_router.post("", response_model=DebugOut, dependencies=[Depends(analysis_limiter)])
def debug(body: DebugIn, user: dict = Depends(get_current_user)) -> DebugOut:
    ensure_code_size(body.code)
    out = run_debug(body, _allow_ai(body.use_ai, user))
    doc = {**out, "user_id": user["_id"], "code": body.code, "error_message": body.error_message, "context": body.context,
           "filename": body.filename, "title": out["error_type"] + " — " + _title(body.code, body.filename)}
    rid = get_db()[DEBUG_SESSIONS].insert_one(doc).inserted_id
    return DebugOut(**{**out, "id": str(rid)})


@debug_router.get("/sessions", response_model=Paginated)
def list_debug(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), user: dict = Depends(get_current_user)) -> dict:
    return paginate(get_db()[DEBUG_SESSIONS], {"user_id": user["_id"]}, page, page_size, [("created_at", DESCENDING)], LIST_PROJECTION)


@debug_router.get("/sessions/{item_id}")
def get_debug(item_id: str, user: dict = Depends(get_current_user)) -> dict:
    return serialize(_get(DEBUG_SESSIONS, item_id, user, "debugging session"))  # type: ignore[return-value]


@debug_router.delete("/sessions/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_debug(item_id: str, user: dict = Depends(get_current_user)) -> None:
    _delete(DEBUG_SESSIONS, item_id, user, "debugging session")


# ----------------------------------------------------------------- explain
@explain_router.post("", response_model=ExplainOut, dependencies=[Depends(analysis_limiter)])
def explain(body: ExplainIn, user: dict = Depends(get_current_user)) -> ExplainOut:
    ensure_code_size(body.code)
    out = run_explain(body, _allow_ai(body.use_ai, user))
    doc = {**out, "user_id": user["_id"], "code": body.code, "filename": body.filename, "title": _title(body.code, body.filename)}
    rid = get_db()[EXPLANATIONS].insert_one(doc).inserted_id
    return ExplainOut(**{**out, "id": str(rid)})


@explain_router.get("/history", response_model=Paginated)
def list_explain(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), user: dict = Depends(get_current_user)) -> dict:
    return paginate(get_db()[EXPLANATIONS], {"user_id": user["_id"]}, page, page_size, [("created_at", DESCENDING)], LIST_PROJECTION)


@explain_router.get("/history/{item_id}")
def get_explain(item_id: str, user: dict = Depends(get_current_user)) -> dict:
    return serialize(_get(EXPLANATIONS, item_id, user, "explanation"))  # type: ignore[return-value]


@explain_router.delete("/history/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_explain(item_id: str, user: dict = Depends(get_current_user)) -> None:
    _delete(EXPLANATIONS, item_id, user, "explanation")


# ----------------------------------------------------------------- optimize
@optimize_router.post("", response_model=OptimizeOut, dependencies=[Depends(analysis_limiter)])
def optimize(body: OptimizeIn, user: dict = Depends(get_current_user)) -> OptimizeOut:
    ensure_code_size(body.code)
    out = run_optimize(body, _allow_ai(body.use_ai, user))
    doc = {**out, "kind": "optimization", "user_id": user["_id"], "filename": body.filename, "title": _title(body.code, body.filename)}
    rid = get_db()[ARTIFACTS].insert_one(doc).inserted_id
    return OptimizeOut(**{**out, "id": str(rid)})


@optimize_router.get("/history", response_model=Paginated)
def list_optimize(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), user: dict = Depends(get_current_user)) -> dict:
    return paginate(get_db()[ARTIFACTS], {"user_id": user["_id"], "kind": "optimization"}, page, page_size, [("created_at", DESCENDING)], LIST_PROJECTION)


@optimize_router.get("/history/{item_id}")
def get_optimize(item_id: str, user: dict = Depends(get_current_user)) -> dict:
    return serialize(_get(ARTIFACTS, item_id, user, "optimization", {"kind": "optimization"}))  # type: ignore[return-value]


@optimize_router.delete("/history/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_optimize(item_id: str, user: dict = Depends(get_current_user)) -> None:
    _delete(ARTIFACTS, item_id, user, "optimization", {"kind": "optimization"})


# ----------------------------------------------------------------- documentation
@docs_router.post("", response_model=DocsOut, dependencies=[Depends(analysis_limiter)])
def documentation(body: DocsIn, user: dict = Depends(get_current_user)) -> DocsOut:
    ensure_code_size(body.code)
    out = run_docs(body, _allow_ai(body.use_ai, user))
    doc = {**out, "kind": "documentation", "user_id": user["_id"], "code": body.code, "filename": body.filename,
           "title": body.project_name or _title(body.code, body.filename)}
    rid = get_db()[ARTIFACTS].insert_one(doc).inserted_id
    return DocsOut(**{**out, "id": str(rid)})


@docs_router.get("/history", response_model=Paginated)
def list_docs(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), user: dict = Depends(get_current_user)) -> dict:
    return paginate(get_db()[ARTIFACTS], {"user_id": user["_id"], "kind": "documentation"}, page, page_size, [("created_at", DESCENDING)], LIST_PROJECTION)


@docs_router.get("/history/{item_id}")
def get_docs(item_id: str, user: dict = Depends(get_current_user)) -> dict:
    return serialize(_get(ARTIFACTS, item_id, user, "documentation", {"kind": "documentation"}))  # type: ignore[return-value]


@docs_router.get("/history/{item_id}/download")
def download_docs(item_id: str, user: dict = Depends(get_current_user)) -> Response:
    doc = _get(ARTIFACTS, item_id, user, "documentation", {"kind": "documentation"})
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in (doc.get("title") or "documentation"))[:60] or "documentation"
    return Response(doc["markdown"], media_type="text/markdown; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{safe}.md"'})


@docs_router.delete("/history/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_docs(item_id: str, user: dict = Depends(get_current_user)) -> None:
    _delete(ARTIFACTS, item_id, user, "documentation", {"kind": "documentation"})
