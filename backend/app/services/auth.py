from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Optional

from sqlmodel import Session, select

from app.core.config import settings
from app.models import RefreshToken, Role, User
from app.services import security


class AuthenticationError(Exception):
    pass


class RefreshTokenError(Exception):
    pass


def get_role_by_code(session: Session, code: str) -> Optional[Role]:
    statement = select(Role).where(Role.code == code)
    return session.exec(statement).first()


def get_user_by_username(session: Session, username: str) -> Optional[User]:
    statement = select(User).where(User.username == username)
    return session.exec(statement).first()


def authenticate_user(session: Session, username: str, password: str) -> User:
    user = get_user_by_username(session, username)
    if not user or not user.is_active:
        raise AuthenticationError("INVALID_CREDENTIALS")
    if not security.verify_password(password, user.password_hash):
        raise AuthenticationError("INVALID_CREDENTIALS")
    return user


def create_tokens_for_user(
    session: Session, user: User, metadata: Optional[Dict[str, str]] = None
) -> tuple[str, str, int]:
    metadata = metadata or {}
    role = session.get(Role, user.role_id)
    role_code = role.code if role else "user"
    access_token = security.create_access_token(str(user.id), {"role": role_code})
    refresh_token = security.create_refresh_token(str(user.id), {"role": role_code})
    payload = security.decode_token(refresh_token)
    expires = payload.get("exp")
    if expires is None:
        raise RefreshTokenError("INVALID_REFRESH_TOKEN_PAYLOAD")
    expires_at = datetime.fromtimestamp(expires, tz=timezone.utc)
    refresh_entry = RefreshToken(
        user_id=user.id,
        token=refresh_token,
        expires_at=expires_at,
        metadata_json=metadata,
    )
    session.add(refresh_entry)
    session.commit()
    return access_token, refresh_token, settings.access_token_expire_minutes * 60


def rotate_refresh_token(
    session: Session, refresh_token: str, metadata: Optional[Dict[str, str]] = None
) -> tuple[str, str, int]:
    metadata = metadata or {}
    statement = select(RefreshToken).where(RefreshToken.token == refresh_token)
    token_entry = session.exec(statement).first()
    if not token_entry or token_entry.revoked_at is not None:
        raise RefreshTokenError("TOKEN_NOT_FOUND")
    if token_entry.expires_at < datetime.now(timezone.utc):
        raise RefreshTokenError("TOKEN_EXPIRED")
    user = session.get(User, token_entry.user_id)
    if user is None or not user.is_active:
        raise RefreshTokenError("USER_INACTIVE")
    new_access, new_refresh, expires_in = create_tokens_for_user(session, user, metadata)
    token_entry.revoked_at = datetime.now(timezone.utc)
    session.add(token_entry)
    session.commit()
    return new_access, new_refresh, expires_in


def revoke_refresh_token(session: Session, refresh_token: str) -> None:
    statement = select(RefreshToken).where(RefreshToken.token == refresh_token)
    token_entry = session.exec(statement).first()
    if token_entry:
        token_entry.revoked_at = datetime.now(timezone.utc)
        session.add(token_entry)
        session.commit()


def ensure_seed_data(session: Session) -> None:
    roles = {
        "doctor": {
            "name": "Lääkäri",
            "permissions": ["patients:read", "patients:write", "appointments:write"],
        },
        "nurse": {
            "name": "Hoitaja",
            "permissions": ["patients:read", "patients:write", "appointments:write"],
        },
        "billing": {
            "name": "Laskutus",
            "permissions": ["patients:read"],
        },
        "admin": {
            "name": "Ylläpitäjä",
            "permissions": [
                "patients:read",
                "patients:write",
                "appointments:write",
                "audit:read",
                "admin:manage",
            ],
        },
    }
    for code, data in roles.items():
        role = get_role_by_code(session, code)
        if not role:
            role = Role(code=code, name=data["name"], permissions=data["permissions"])
            session.add(role)
            session.commit()
    admin_user = get_user_by_username(session, settings.first_superuser)
    admin_role = get_role_by_code(session, "admin")
    if admin_role and not admin_user:
        user = User(
            username=settings.first_superuser,
            password_hash=security.hash_password(settings.first_superuser_password),
            display_name="Järjestelmänvalvoja",
            role_id=admin_role.id,
        )
        session.add(user)
        session.commit()


__all__ = [
    "authenticate_user",
    "create_tokens_for_user",
    "rotate_refresh_token",
    "revoke_refresh_token",
    "ensure_seed_data",
    "AuthenticationError",
    "RefreshTokenError",
]
