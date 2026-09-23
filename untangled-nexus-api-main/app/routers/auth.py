from __future__ import annotations

import re
import hashlib
from starlette.concurrency import run_in_threadpool
from app.config import get_settings
from app.domain import public_employee
from app.security import hash_pbkdf2_sha256
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.security import (
    find_employee_for_user,
    is_active,
    make_token,
    normalise_login,
    require_session,
    serialize_id,
    verify_password,
)
from app.db import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginBody(BaseModel):
    username: Optional[str] = Field(default=None, max_length=200)
    email: Optional[str] = Field(default=None, max_length=200)
    password: str = Field(default="", max_length=1024)


@router.post("/login")
async def login(body: LoginBody, request: Request):
    username = normalise_login(body.username or body.email)
    password = str(body.password or "")
    if not username or not password:
        raise HTTPException(422, "Username and password are required.")

    db = get_db()
    bucket = int(datetime.now(timezone.utc).timestamp()) // 900
    login_key = hashlib.sha256(username.encode()).hexdigest()
    attempt_id = f"{login_key}:{bucket}"
    from pymongo import ReturnDocument
    attempt = await db['login_attempts'].find_one_and_update({'_id': attempt_id},
        {'$inc': {'count': 1}, '$setOnInsert': {'expires_at': datetime.now(timezone.utc) + timedelta(minutes=30)}},
        upsert=True, return_document=ReturnDocument.AFTER)
    if attempt['count'] > 15:
        raise HTTPException(429, 'Too many login attempts. Try again later.')
    users = db["users"]
    user = await users.find_one(
        {"$or": [{"username": username}, {"email": username}]},
        projection={
            "_id": 1,
            "username": 1,
            "email": 1,
            "role": 1,
            "status": 1,
            "employee_id": 1,
            "password_hash": 1,
            "hashed_password": 1,
            "password": 1,
            "full_name": 1,
            "department": 1,
            "position": 1,
            "require_password_change": 1,
        },
    )
    if not user:
        escaped = re.escape(username)
        user = await users.find_one(
            {
                "$or": [
                    {"username": {"$regex": f"^{escaped}$", "$options": "i"}},
                    {"email": {"$regex": f"^{escaped}$", "$options": "i"}},
                ]
            },
            projection={
                "_id": 1,
                "username": 1,
                "email": 1,
                "role": 1,
                "status": 1,
                "employee_id": 1,
                "password_hash": 1,
                "hashed_password": 1,
                "password": 1,
                "full_name": 1,
                "department": 1,
                "position": 1,
            "require_password_change": 1,
            },
        )

    if not user:
        raise HTTPException(401, 'Invalid username or password.')
    if not is_active(user.get("status"), True):
        raise HTTPException(403, "This user account is inactive. Contact a manager.")
    employee = await find_employee_for_user(user)
    if not employee or not is_active(employee.get("status"), True):
        raise HTTPException(403, "An active linked employee record is required. Contact a manager.")

    stored = user.get("password_hash") or user.get("hashed_password") or user.get("password")
    if not await run_in_threadpool(verify_password, password, stored):
        raise HTTPException(401, 'Invalid username or password.')

    if not str(stored).startswith('pbkdf2_sha256$'):
        upgraded = await run_in_threadpool(hash_pbkdf2_sha256, password)
        await users.update_one({'_id': user['_id']}, {'$set': {'password_hash': upgraded}, '$unset': {'password': '', 'hashed_password': ''}})
    token = make_token()
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=get_settings().session_expiry_hours)
    await db["api_sessions"].insert_one(
        {
            "token_hash": hashlib.sha256(token.encode()).hexdigest(),
            "user_id": user["_id"],
            "employee_id": employee.get("_id") or employee.get("employee_id"),
            "status": "active",
            "created_at": now,
            "expires_at": expires,
            "last_activity_at": now,
        }
    )

    safe_user = {
        "id": str(user["_id"]),
        "_id": str(user["_id"]),
        "username": user.get("username"),
        "email": user.get("email"),
        "role": user.get("role"),
        "status": user.get("status"),
        "require_password_change": bool(user.get("require_password_change")),
        "employee_id": str(user.get("employee_id") or employee.get("_id") or ""),
        "full_name": user.get("full_name")
        or employee.get("full_name")
        or " ".join(
            filter(
                None,
                [employee.get("first_name"), employee.get("surname") or employee.get("last_name")],
            )
        ),
        "department": user.get("department") or employee.get("department"),
        "position": user.get("position") or employee.get("position"),
    }

    return {
        "success": True,
        "token": token,
        "access_token": token,
        "user": safe_user,
        "employee": public_employee(employee),
        "expires_at": expires.isoformat(),
    }


@router.get("/me")
async def me(ctx: dict = Depends(require_session)):
    user = serialize_id(ctx["user"])
    employee = public_employee(ctx["employee"])
    return {"success": True, "user": user, "employee": employee}


@router.post("/logout")
async def logout(ctx: dict = Depends(require_session)):
    db = ctx["db"]
    await db["api_sessions"].update_one(
        {"_id": ctx["session"]["_id"]},
        {"$set": {"status": "revoked", "revoked_at": datetime.now(timezone.utc)}},
    )
    return {"success": True, "message": "Logged out."}


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=1024)
    new_password: str = Field(min_length=8, max_length=1024)


@router.post('/change-password')
async def change_password(body: PasswordChange, ctx: dict = Depends(require_session)):
    user = await ctx['db']['users'].find_one({'_id': ctx['user']['_id']})
    stored = user.get('password_hash') or user.get('hashed_password') or user.get('password')
    if not await run_in_threadpool(verify_password, body.current_password, stored):
        raise HTTPException(403, 'Current password is incorrect.')
    if body.current_password == body.new_password:
        raise HTTPException(422, 'Choose a different password.')
    hashed = await run_in_threadpool(hash_pbkdf2_sha256, body.new_password)
    await ctx['db']['users'].update_one({'_id': user['_id']}, {'$set': {'password_hash': hashed, 'require_password_change': False, 'updated_at': datetime.now(timezone.utc)}, '$unset': {'password': '', 'hashed_password': ''}})
    await ctx['db']['api_sessions'].update_many({'user_id': user['_id'], '_id': {'$ne': ctx['session']['_id']}}, {'$set': {'status': 'revoked'}})
    return {'success': True, 'message': 'Password changed.'}
