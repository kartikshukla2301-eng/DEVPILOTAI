from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.errors import DuplicateKeyError

from app.core.database import USER_SETTINGS, USERS, get_db
from app.core.security import create_access_token, get_current_user, hash_password, verify_password
from app.routes.common import DEFAULT_SETTINGS, auth_limiter, now
from app.schemas import LoginIn, RegisterIn, TokenOut, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])

# Pre-computed hash so failed logins for unknown emails take as long as for known ones.
_DUMMY_HASH = hash_password("timing-equaliser-not-a-real-password-1")


def user_out(u: dict) -> UserOut:
    return UserOut(id=str(u["_id"]), name=u["name"], email=u["email"], bio=u.get("bio", ""), created_at=u["created_at"])


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(auth_limiter)])
def register(body: RegisterIn) -> TokenOut:
    db = get_db()
    ts = now()
    doc = {"name": body.name, "email": body.email.lower(), "password_hash": hash_password(body.password),
           "bio": "", "token_version": 0, "created_at": ts, "updated_at": ts, "last_login_at": ts}
    try:
        res = db[USERS].insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    db[USER_SETTINGS].insert_one({"user_id": res.inserted_id, **DEFAULT_SETTINGS, "created_at": ts, "updated_at": ts})
    doc["_id"] = res.inserted_id
    token, exp = create_access_token(str(res.inserted_id), 0)
    return TokenOut(access_token=token, expires_in=exp, user=user_out(doc))


@router.post("/login", response_model=TokenOut, dependencies=[Depends(auth_limiter)])
def login(body: LoginIn) -> TokenOut:
    db = get_db()
    user = db[USERS].find_one({"email": body.email.lower()})
    if not user:
        verify_password(body.password, _DUMMY_HASH)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    if not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    db[USERS].update_one({"_id": user["_id"]}, {"$set": {"last_login_at": now()}})
    token, exp = create_access_token(str(user["_id"]), user.get("token_version", 0))
    return TokenOut(access_token=token, expires_in=exp, user=user_out(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(user: dict = Depends(get_current_user)) -> None:
    """Revokes every token issued to this user (all devices)."""
    get_db()[USERS].update_one({"_id": user["_id"]}, {"$inc": {"token_version": 1}, "$set": {"updated_at": now()}})


@router.get("/me", response_model=UserOut)
def me(user: dict = Depends(get_current_user)) -> UserOut:
    return user_out(user)
