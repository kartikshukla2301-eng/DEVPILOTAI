import os

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.core.config import get_settings
from app.core.database import CODE_REVIEWS, PROJECTS, get_db
from app.core.security import get_current_user, parse_object_id
from app.routes.common import analysis_limiter, ensure_code_size, now, serialize, user_settings
from app.schemas import SUPPORTED_LANGUAGES, ReviewIn, ReviewOut
from app.services import ai
from app.services.review import run_review

router = APIRouter(prefix="/code-review", tags=["code-review"])

EXT_TO_LANG = {".py": "python", ".pyw": "python", ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript", ".jsx": "javascript",
               ".ts": "typescript", ".tsx": "typescript", ".mts": "typescript", ".java": "java", ".c": "c", ".h": "c",
               ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp", ".hpp": "cpp", ".hh": "cpp", ".go": "go"}


@router.get("/languages")
def languages() -> dict:
    return {"languages": SUPPORTED_LANGUAGES, "extensions": EXT_TO_LANG}


@router.post("/analyze", response_model=ReviewOut, dependencies=[Depends(analysis_limiter)])
def analyze(body: ReviewIn, user: dict = Depends(get_current_user)) -> ReviewOut:
    ensure_code_size(body.code)
    db = get_db()
    project_id = None
    if body.project_id:
        project_id = parse_object_id(body.project_id, "project")
        if not db[PROJECTS].find_one({"_id": project_id, "user_id": user["_id"]}, {"_id": 1}):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    prefs = user_settings(user["_id"])
    report = run_review(body, ai.should_use_ai(body.use_ai, prefs["use_ai"]))
    report_id = None
    if body.save:
        doc = {**report, "user_id": user["_id"], "project_id": project_id, "updated_at": now()}
        report_id = db[CODE_REVIEWS].insert_one(doc).inserted_id
        if project_id:
            db[PROJECTS].update_one({"_id": project_id}, {"$set": {"updated_at": now()}})
    return ReviewOut(**{**report, "id": str(report_id) if report_id else None, "saved": bool(report_id),
                        "project_id": str(project_id) if project_id else None})


@router.post("/upload")
async def upload(file: UploadFile = File(...), user: dict = Depends(get_current_user)) -> dict:
    """Reads an uploaded source file and detects its language. The file is not stored."""
    name = os.path.basename(file.filename or "upload")
    ext = os.path.splitext(name)[1].lower()
    lang = EXT_TO_LANG.get(ext)
    if not lang:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, f"Unsupported file type '{ext or 'none'}'. Supported: {', '.join(sorted(EXT_TO_LANG))}")
    limit = get_settings().max_code_chars * 4  # bytes upper bound for UTF-8
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File is too large")
    try:
        code = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "File is not valid UTF-8 text")
    ensure_code_size(code)
    return {"filename": name, "language": lang, "code": code}


@router.get("/{review_id}", response_model=ReviewOut)
def get_review(review_id: str, user: dict = Depends(get_current_user)) -> ReviewOut:
    doc = get_db()[CODE_REVIEWS].find_one({"_id": parse_object_id(review_id, "review"), "user_id": user["_id"]})
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Review not found")
    d = serialize(doc)
    return ReviewOut(**{**d, "saved": True})  # type: ignore[arg-type]
