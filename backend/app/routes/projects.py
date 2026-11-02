from fastapi import APIRouter, Depends, HTTPException, Query, status
from pymongo import DESCENDING
from pymongo.errors import DuplicateKeyError

from app.core.database import CODE_REVIEWS, PROJECTS, get_db
from app.core.security import get_current_user, parse_object_id
from app.routes.common import now
from app.schemas import ProjectIn, ProjectOut, ProjectUpdateIn

router = APIRouter(prefix="/projects", tags=["projects"])


def _out(doc: dict, count: int) -> ProjectOut:
    return ProjectOut(id=str(doc["_id"]), name=doc["name"], description=doc.get("description", ""), language=doc.get("language"),
                      review_count=count, created_at=doc["created_at"], updated_at=doc["updated_at"])


def _counts(user_id, ids) -> dict:
    pipeline = [{"$match": {"user_id": user_id, "project_id": {"$in": ids}}}, {"$group": {"_id": "$project_id", "n": {"$sum": 1}}}]
    return {r["_id"]: r["n"] for r in get_db()[CODE_REVIEWS].aggregate(pipeline)}


@router.get("", response_model=list[ProjectOut])
def list_projects(limit: int = Query(100, ge=1, le=200), user: dict = Depends(get_current_user)) -> list[ProjectOut]:
    docs = list(get_db()[PROJECTS].find({"user_id": user["_id"]}).sort("updated_at", DESCENDING).limit(limit))
    counts = _counts(user["_id"], [d["_id"] for d in docs])
    return [_out(d, counts.get(d["_id"], 0)) for d in docs]


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(body: ProjectIn, user: dict = Depends(get_current_user)) -> ProjectOut:
    ts = now()
    doc = {"user_id": user["_id"], "name": body.name.strip(), "description": body.description.strip(), "language": body.language,
           "created_at": ts, "updated_at": ts}
    try:
        doc["_id"] = get_db()[PROJECTS].insert_one(doc).inserted_id
    except DuplicateKeyError:
        raise HTTPException(status.HTTP_409_CONFLICT, "You already have a project with this name")
    return _out(doc, 0)


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: str, user: dict = Depends(get_current_user)) -> ProjectOut:
    doc = get_db()[PROJECTS].find_one({"_id": parse_object_id(project_id, "project"), "user_id": user["_id"]})
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return _out(doc, _counts(user["_id"], [doc["_id"]]).get(doc["_id"], 0))


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(project_id: str, body: ProjectUpdateIn, user: dict = Depends(get_current_user)) -> ProjectOut:
    pid = parse_object_id(project_id, "project")
    changes = body.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"] is not None:
        changes["name"] = changes["name"].strip()
    changes["updated_at"] = now()
    try:
        doc = get_db()[PROJECTS].find_one_and_update({"_id": pid, "user_id": user["_id"]}, {"$set": changes}, return_document=True)
    except DuplicateKeyError:
        raise HTTPException(status.HTTP_409_CONFLICT, "You already have a project with this name")
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return _out(doc, _counts(user["_id"], [pid]).get(pid, 0))


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: str, user: dict = Depends(get_current_user)) -> None:
    """Deletes the project. Its reviews are kept and become unassigned."""
    pid = parse_object_id(project_id, "project")
    db = get_db()
    res = db[PROJECTS].delete_one({"_id": pid, "user_id": user["_id"]})
    if res.deleted_count == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    db[CODE_REVIEWS].update_many({"user_id": user["_id"], "project_id": pid}, {"$set": {"project_id": None}})
