from __future__ import annotations


from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class RoleRead(BaseModel):
    id: int
    code: str
    name: str


class UserRead(BaseModel):
    id: int
    username: str
    display_name: str
    role: RoleRead
    is_active: bool


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    role: str


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshTokenRead(BaseModel):
    id: int
    issued_at: datetime
    expires_at: datetime
    revoked_at: Optional[datetime]
