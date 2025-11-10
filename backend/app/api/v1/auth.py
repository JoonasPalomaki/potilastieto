from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.api.deps import get_db
from app.models import Role
from app.schemas import LoginRequest, RefreshRequest, TokenResponse
from app.services import (
    security,
    AuthenticationError,
    RefreshTokenError,
    authenticate_user,
    create_tokens_for_user,
    ensure_seed_data,
    revoke_refresh_token,
    rotate_refresh_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, session: Session = Depends(get_db)) -> TokenResponse:
    ensure_seed_data(session)
    try:
        user = authenticate_user(session, payload.username, payload.password)
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Virheelliset tunnukset") from exc

    metadata = {"ip": "local"}
    access_token, refresh_token, expires_in = create_tokens_for_user(session, user, metadata)
    role = session.get(Role, user.role_id) if user.role_id else None
    role_code = role.code if role else "user"
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=expires_in,
        role=role_code,
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, session: Session = Depends(get_db)) -> TokenResponse:
    try:
        access_token, refresh_token, expires_in = rotate_refresh_token(session, payload.refresh_token)
    except RefreshTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Virheellinen tai vanhentunut token") from exc

    decoded = security.decode_token(access_token)
    role = decoded.get("role", "user")
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=expires_in,
        role=role,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(payload: RefreshRequest, session: Session = Depends(get_db)) -> None:
    revoke_refresh_token(session, payload.refresh_token)
