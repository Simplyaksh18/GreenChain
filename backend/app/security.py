import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from passlib.exc import UnknownHashError

from app.config import settings

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


# Alias kept for callers/scripts that use the standard FastAPI naming.
get_password_hash = hash_password


def verify_password(plain_password: str, hashed_password: Optional[str]) -> bool:
    """
    Verify a plaintext password against a stored hash.

    Returns False (never raises) on:
      - None / empty stored hash
      - malformed or unsupported hash format
      - any passlib-level parsing error

    A False return must be treated as an authentication failure by callers,
    which is indistinguishable from a wrong password — the caller must not
    leak the reason to the client.
    """
    if not hashed_password:
        return False
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except (UnknownHashError, ValueError) as exc:
        logger.warning("verify_password: malformed stored hash (%s)", type(exc).__name__)
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None
