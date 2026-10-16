"""JWT authentication and role-based access control (admin > planner > viewer)."""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .reference import ROLE_RANK, USERS

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
SECRET_FILE = DATA_DIR / ".jwt_secret"
TOKEN_HOURS = int(os.getenv("TOKEN_HOURS", "12"))


def _secret() -> str:
    env = os.getenv("JWT_SECRET_KEY")
    if env:
        return env
    if SECRET_FILE.exists():
        return SECRET_FILE.read_text().strip()
    s = secrets.token_urlsafe(48)
    SECRET_FILE.write_text(s)
    return s


SECRET = _secret()
_SALT = b"logisentinel-demo"


def _hash(pw: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), _SALT, 120_000).hex()


# Passwords are stored only as PBKDF2 hashes in memory.
_USER_DB = {u: {**{k: v for k, v in d.items() if k != "password"}, "hash": _hash(d["password"])} for u, d in USERS.items()}


def authenticate(username: str, password: str):
    u = _USER_DB.get((username or "").strip().lower())
    if not u or not hmac.compare_digest(u["hash"], _hash(password or "")):
        return None
    return {"username": username.strip().lower(), "role": u["role"], "name": u["name"], "title": u["title"]}


def create_token(user: dict) -> str:
    payload = {"sub": user["username"], "role": user["role"], "name": user["name"],
               "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_HOURS)}
    return jwt.encode(payload, SECRET, algorithm="HS256")


bearer = HTTPBearer(auto_error=False)


def current_user(creds: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    if not creds:
        raise HTTPException(401, "Login required")
    try:
        p = jwt.decode(creds.credentials, SECRET, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Session expired - please log in again")
    u = _USER_DB.get(p.get("sub"))
    if not u:
        raise HTTPException(401, "Unknown user")
    return {"username": p["sub"], "role": u["role"], "name": u["name"], "title": u["title"]}


def require(min_role: str):
    def dep(user: dict = Depends(current_user)) -> dict:
        if ROLE_RANK[user["role"]] < ROLE_RANK[min_role]:
            raise HTTPException(403, f"This action needs the '{min_role}' role. You are logged in as '{user['role']}'.")
        return user
    return dep
