"""Auth routes — login, logout, me."""

from __future__ import annotations

import os

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.auth import (
    _COOKIE_NAME,
    check_credentials,
    create_console_token,
    get_cookie_token,
    verify_console_token,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Only set Secure flag when we know HTTPS is in play (ALB with cert or explicit env)
_COOKIE_SECURE = os.environ.get("HOLLY_COOKIE_SECURE", "").lower() in ("1", "true")


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/login")
async def login(body: LoginRequest, request: Request):
    """Authenticate and set httpOnly cookie."""
    if not check_credentials(body.email, body.password):
        return JSONResponse({"detail": "Invalid credentials"}, status_code=401)

    token = create_console_token(body.email)
    response = JSONResponse({"email": body.email})
    # Use Secure flag if explicitly configured or if request came over HTTPS
    secure = _COOKIE_SECURE or request.headers.get("x-forwarded-proto") == "https"
    response.set_cookie(
        key=_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
        max_age=86400,  # 24h
    )
    return response


@router.get("/me")
async def me(request: Request):
    """Return current user from cookie."""
    token = get_cookie_token(request)
    if not token:
        return JSONResponse({"detail": "Not authenticated"}, status_code=401)
    claims = verify_console_token(token)
    if not claims:
        return JSONResponse({"detail": "Invalid token"}, status_code=401)
    return {"email": claims["sub"]}


@router.post("/logout")
async def logout():
    """Clear the auth cookie."""
    response = JSONResponse({"status": "logged_out"})
    response.delete_cookie(key=_COOKIE_NAME, path="/")
    return response
