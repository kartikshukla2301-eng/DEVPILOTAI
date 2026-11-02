from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings
from app.core.database import USERS, get_db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(password, hashed)
    except ValueError:
        return False


def create_access_token(user_id: str, token_version: int = 0) -> tuple[str, int]:
    s = get_settings()
    expires = timedelta(minutes=s.access_token_expire_minutes)
    now = datetime.now(timezone.utc)
    payload = {"sub": user_id, "tv": token_version, "iat": now, "exp": now + expires, "type": "access"}
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm), int(expires.total_seconds())


def parse_object_id(value: str, what: str = "resource") -> ObjectId:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{what.capitalize()} not found")


def get_current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict[str, Any]:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if creds is None or creds.scheme.lower() != "bearer":
        raise unauthorized
    s = get_settings()
    try:
        payload = jwt.decode(creds.credentials, s.jwt_secret, algorithms=[s.jwt_algorithm])
    except JWTError:
        raise unauthorized
    if payload.get("type") != "access" or "sub" not in payload:
        raise unauthorized
    try:
        uid = ObjectId(payload["sub"])
    except InvalidId:
        raise unauthorized
    user = get_db()[USERS].find_one({"_id": uid})
    # token_version lets logout / password change revoke all outstanding tokens.
    if not user or user.get("token_version", 0) != payload.get("tv", 0):
        raise unauthorized
    return user
