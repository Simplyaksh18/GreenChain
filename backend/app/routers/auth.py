"""
Auth Router — Phase 1 / Phase 15 (Google OAuth)

Phase 1: POST /auth/register  — email/password registration
         POST /auth/login     — email/password login
         GET  /auth/me        — authenticated user info

Phase 15: POST /auth/google/login    — verify Google access token, return JWT
          POST /auth/google/register — create account via Google (role still user-selected)

SECURITY:
  - Google access tokens are NEVER stored in the database.
  - Google access tokens are NEVER logged.
  - Role is always selected by the user — Google never decides role.
  - Existing email/password flows are fully preserved and unaffected.
  - auth_provider distinguishes PASSWORD users from GOOGLE users.
"""
import logging
import secrets

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User, UserRole
from app.schemas.token_schema import Token
from app.schemas.user_schema import (
    GoogleLoginRequest,
    GoogleLoginResponse,
    GoogleNeedsRegistrationResponse,
    GoogleRegisterRequest,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.security import create_access_token, hash_password, verify_password

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _verify_google_token(access_token: str) -> dict:
    """
    Call Google's userinfo endpoint to verify the access token and fetch user profile.
    Returns: {"sub": "...", "email": "...", "name": "...", "picture": "..."}
    Never logs the token value.
    """
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                _GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if resp.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Google token verification failed. Token may be expired or invalid.",
                )
            return resp.json()
    except httpx.RequestError as exc:
        logger.error("Google userinfo request failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not reach Google authentication service.",
        )


# ── Existing Phase 1 endpoints — UNCHANGED ────────────────────────────────────

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    auto_approve = payload.role == UserRole.FARMER
    user = User(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=True,
        is_approved=auto_approve,
        auth_provider="PASSWORD",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(payload: UserLoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")
    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


# ── Phase 15: Google OAuth endpoints ──────────────────────────────────────────

@router.post("/google/login")
async def google_login(
    payload: GoogleLoginRequest,
    db: Session = Depends(get_db),
):
    """
    Verify a Google access token and return a GreenChain JWT if the user exists.

    Flow:
      1. Backend verifies token by calling Google's userinfo endpoint.
      2. Look up user by email.
      3. If found → return GreenChain JWT (GoogleLoginResponse).
      4. If not found → return 404 with user data so mobile can open registration.

    The access token is NEVER stored or logged.
    Role is determined by the existing GreenChain account, not by Google.
    """
    google_user = await _verify_google_token(payload.google_access_token)
    email = google_user.get("email", "").lower().strip()
    if not email:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Google account did not return an email address.",
        )

    user = db.query(User).filter(User.email == email).first()
    if not user:
        # Signal to mobile: navigate to registration with prefilled data
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "needs_registration": True,
                "name": google_user.get("name", ""),
                "email": email,
                "google_sub": google_user.get("sub", ""),
                "profile_photo_url": google_user.get("picture"),
            },
        )

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")

    # Update Google fields on existing users if not set (e.g. they originally registered with password)
    changed = False
    if not user.google_sub and google_user.get("sub"):
        user.google_sub = google_user["sub"]
        changed = True
    if not user.profile_photo_url and google_user.get("picture"):
        user.profile_photo_url = google_user["picture"]
        changed = True
    if changed:
        db.commit()

    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    logger.info("google.login | user_id=%s", user.id)
    return {"access_token": token, "token_type": "bearer", "auth_provider": "GOOGLE"}


@router.post("/google/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def google_register(
    payload: GoogleRegisterRequest,
    db: Session = Depends(get_db),
):
    """
    Create a GreenChain account using Google identity.

    The backend verifies the Google access token to confirm the email.
    Role is ALWAYS user-selected on the mobile registration screen.
    A random password hash is set — Google users log in via Google, not password.

    The access token is NEVER stored or logged.
    """
    # Verify token to confirm email ownership
    google_user = await _verify_google_token(payload.google_access_token)
    verified_email = google_user.get("email", "").lower().strip()

    if verified_email != payload.email.lower().strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Email from Google token does not match submitted email.",
        )

    existing = db.query(User).filter(User.email == verified_email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered. Sign in instead.",
        )

    # Random password — Google users never login with password
    random_password = hash_password(secrets.token_hex(32))
    auto_approve = payload.role == UserRole.FARMER

    user = User(
        name=payload.name.strip() or google_user.get("name", ""),
        email=verified_email,
        password_hash=random_password,
        role=payload.role,
        is_active=True,
        is_approved=auto_approve,
        auth_provider="GOOGLE",
        google_sub=google_user.get("sub"),
        profile_photo_url=google_user.get("picture"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("google.register | user_id=%s role=%s", user.id, user.role.value)
    return user
