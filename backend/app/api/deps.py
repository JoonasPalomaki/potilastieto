from __future__ import annotations


from dataclasses import dataclass
from typing import Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session

from app.db.session import get_session
from app.models import Role, User
from app.services import security

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


@dataclass
class AuthenticatedUser:
    user: User
    role: Role | None


def get_db():
    with get_session() as session:
        yield session


async def get_current_user(
    token: str = Depends(oauth2_scheme), session: Session = Depends(get_db)
) -> AuthenticatedUser:
    try:
        payload = security.decode_token(token)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    subject = payload.get("sub")
    if subject is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    try:
        user_id = int(subject)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload") from exc

    user = session.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
    role = session.get(Role, user.role_id) if user.role_id else None
    return AuthenticatedUser(user=user, role=role)


def require_roles(*allowed_roles: str) -> Callable[[AuthenticatedUser], AuthenticatedUser]:
    async def checker(current: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        if allowed_roles:
            if current.role is None or current.role.code not in allowed_roles:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        return current

    return checker


async def get_audit_context(request: Request, current: AuthenticatedUser = Depends(get_current_user)) -> dict:
    return {
        "ip": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
        "role": current.role.code if current.role else None,
        "request_path": request.url.path,
    }


CurrentUser = Depends(get_current_user)
