from fastapi import APIRouter, Depends

from app.core.config import get_settings
from app.core.database import USER_SETTINGS, get_db
from app.core.security import get_current_user
from app.routes.common import now, user_settings
from app.schemas import AIStatusOut, SettingsOut, SettingsUpdateIn
from app.services import ai

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=SettingsOut)
def get_user_settings(user: dict = Depends(get_current_user)) -> SettingsOut:
    return SettingsOut(**user_settings(user["_id"]))


@router.patch("", response_model=SettingsOut)
def update_user_settings(body: SettingsUpdateIn, user: dict = Depends(get_current_user)) -> SettingsOut:
    changes = body.model_dump(exclude_none=True)
    ts = now()
    get_db()[USER_SETTINGS].update_one(
        {"user_id": user["_id"]},
        {"$set": {**changes, "updated_at": ts}, "$setOnInsert": {"created_at": ts}},
        upsert=True,
    )
    return SettingsOut(**user_settings(user["_id"]))


@router.get("/ai-status", response_model=AIStatusOut)
def ai_status(user: dict = Depends(get_current_user)) -> AIStatusOut:
    """Reports whether AI is configured. Never returns the API key."""
    s = get_settings()
    return AIStatusOut(ai_configured=s.ai_enabled, mode="ai" if s.ai_enabled else "local",
                       model=s.ai_model if s.ai_enabled else None, provider_host=ai.provider_host())
