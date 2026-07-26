from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.database import get_db
from app.security import decode_access_token
from app.models.user import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
    user_id: str = payload.get("sub")
    if user_id is None:
        raise credentials_exception
    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")
    return user


def require_roles(*roles: UserRole):
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access restricted to: {[r.value for r in roles]}",
            )
        return current_user
    return role_checker


def get_current_farmer(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.FARMER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Farmers only")
    return current_user


def get_current_fpo(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.FPO:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="FPOs only")
    return current_user


def get_current_verifier(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.VERIFIER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verifiers only")
    return current_user


def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins only")
    return current_user
