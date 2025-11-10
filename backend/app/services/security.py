from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import jwt
from passlib.context import CryptContext

from app.core.config import settings

password_context = CryptContext(schemes=['bcrypt'], deprecated='auto')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    return password_context.hash(password)


def _create_token(data: Dict[str, Any], expires_delta: timedelta) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({'exp': expire})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(subject: str, claims: Dict[str, Any]) -> str:
    payload = {'sub': subject, **claims}
    expires = timedelta(minutes=settings.access_token_expire_minutes)
    return _create_token(payload, expires)


def create_refresh_token(subject: str, claims: Dict[str, Any]) -> str:
    expires = timedelta(minutes=settings.refresh_token_expire_minutes)
    payload = {'sub': subject, **claims, 'type': 'refresh'}
    return _create_token(payload, expires)


def decode_token(token: str) -> Dict[str, Any]:
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
