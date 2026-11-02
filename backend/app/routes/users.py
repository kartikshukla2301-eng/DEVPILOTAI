from fastapi import APIRouter, Depends, HTTPException, status

from app.core.database import ARTIFACTS, CODE_REVIEWS, DEBUG_SESSIONS, EXPLANATIONS, PROJECTS, USER_SETTINGS, USERS, get_db
from app.core.security import create_access_token, get_current_user, hash_password, verify_password
from app.routes.auth import user_out
from app.routes.common import now
from app.schemas import PasswordChangeIn, ProfileUpdateIn, TokenOut, UserOut

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
def get_profile(user: dict = Depends(get_current_user)) -> UserOut:
    return user_out(user)


@router.patch("/me", response_model=UserOut)
def update_profile(body: ProfileUpdateIn, user: dict = Depends(get_current_user)) -> UserOut:
    changes = {k: (v.strip() if isinstance(v, str) else v) for k, v in body.model_dump(exclude_none=True).items()}
    if "name" in changes and not changes["name"]:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Name cannot be blank")
    if changes:
        changes["updated_at"] = now()
        get_db()[USERS].update_one({"_id": user["_id"]}, {"$set": changes})
        user = {**user, **changes}
    return user_out(user)


@router.post("/me/password", response_model=TokenOut)
def change_password(body: PasswordChangeIn, user: dict = Depends(get_current_user)) -> TokenOut:
    if not verify_password(body.current_password, user["password_hash"]):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect")
    if body.current_password == body.new_password:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "New password must be different from the current one")
    tv = user.get("token_version", 0) + 1  # invalidate tokens on other devices
    get_db()[USERS].update_one({"_id": user["_id"]}, {"$set": {"password_hash": hash_password(body.new_password),
                                                                 "token_version": tv, "updated_at": now()}})
    token, exp = create_access_token(str(user["_id"]), tv)
    return TokenOut(access_token=token, expires_in=exp, user=user_out(user))


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(user: dict = Depends(get_current_user)) -> None:
    db = get_db()
    uid = user["_id"]
    for coll in (CODE_REVIEWS, DEBUG_SESSIONS, EXPLANATIONS, ARTIFACTS, PROJECTS, USER_SETTINGS):
        db[coll].delete_many({"user_id": uid})
    db[USERS].delete_one({"_id": uid})
