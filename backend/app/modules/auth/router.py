from fastapi import APIRouter, Depends, HTTPException, Request, status, Response, Cookie
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from datetime import timedelta
from urllib.parse import urlencode
import httpx
import jwt
from typing import Optional

from app.core.deps import get_db
from app.core.rate_limit import limiter
from app.core.security import (
    verify_password, get_password_hash,
    create_access_token, create_refresh_token, decode_token
)
from app.core.config import settings
from app.modules.users.models import User, RoleEnum
from app.modules.auth.schemas import UserCreate, Token, LoginRequest

GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_ENDPOINT = "https://www.googleapis.com/oauth2/v3/userinfo"

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.REGISTER_RATE_LIMIT)
def register(request: Request, user_in: UserCreate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == user_in.email).first()
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system."
        )
    user = User(
        name=user_in.name,
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        role=user_in.role,
        organization=user_in.organization
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"message": "User created successfully"}

@router.post("/login", response_model=Token)
@limiter.limit(settings.LOGIN_RATE_LIMIT)
def login(request: Request, response: Response, login_data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == login_data.email).first()
    if not user or not user.hashed_password or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")

    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True, 
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    )

    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/refresh", response_model=Token)
def refresh_token(response: Response, refresh_token: Optional[str] = Cookie(None), db: Session = Depends(get_db)):
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token missing")
    try:
        payload = decode_token(refresh_token)
        user_id = payload.get("sub")
        token_type = payload.get("type")
        if not user_id or token_type != "refresh":
            raise HTTPException(status_code=401, detail="Invalid refresh token")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    new_access_token = create_access_token(subject=user.id)
    new_refresh_token = create_refresh_token(subject=user.id)

    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=True, 
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    )

    return {"access_token": new_access_token, "token_type": "bearer"}

@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(key="refresh_token", httponly=True, secure=True, samesite="lax")
    return {"message": "Logged out successfully"}

@router.get("/google/login")
def google_login():
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google OAuth2 is not configured on this server (missing GOOGLE_CLIENT_ID/SECRET)."
        )
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "online",
        "prompt": "select_account",
    }
    return RedirectResponse(f"{GOOGLE_AUTH_ENDPOINT}?{urlencode(params)}")


@router.get("/google/callback")
def google_callback(response: Response, code: Optional[str] = None, error: Optional[str] = None, db: Session = Depends(get_db)):
    if error or not code:
        return RedirectResponse(f"{settings.FRONTEND_URL}/login?error=google_oauth_failed")

    token_res = httpx.post(GOOGLE_TOKEN_ENDPOINT, data={
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    })
    if token_res.status_code != 200:
        return RedirectResponse(f"{settings.FRONTEND_URL}/login?error=google_oauth_failed")
    google_access_token = token_res.json().get("access_token")

    userinfo_res = httpx.get(
        GOOGLE_USERINFO_ENDPOINT,
        headers={"Authorization": f"Bearer {google_access_token}"}
    )
    if userinfo_res.status_code != 200:
        return RedirectResponse(f"{settings.FRONTEND_URL}/login?error=google_oauth_failed")
    profile = userinfo_res.json()
    google_id = profile.get("sub")
    email = profile.get("email")
    if not google_id or not email:
        return RedirectResponse(f"{settings.FRONTEND_URL}/login?error=google_oauth_failed")

    user = db.query(User).filter(User.google_id == google_id).first()
    if not user:
        user = db.query(User).filter(User.email == email).first()
    if not user:
        # New account: this system has no role-selection step in the Google
        # flow, so it starts every Google sign-up as a Wildlife Researcher
        # (the least-privileged working role) rather than guessing a
        # higher-privilege one; an Administrator can change it afterwards.
        user = User(
            name=profile.get("name") or email,
            email=email,
            role=RoleEnum.RESEARCHER,
            google_id=google_id,
        )
        db.add(user)
    elif not user.google_id:
        user.google_id = google_id
    db.commit()
    db.refresh(user)

    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)

    redirect = RedirectResponse(f"{settings.FRONTEND_URL}/auth/callback?token={access_token}")
    redirect.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    )
    return redirect
