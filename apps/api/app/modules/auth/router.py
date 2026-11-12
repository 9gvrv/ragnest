from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.modules.auth import service
from app.modules.auth.deps import get_google_client
from app.modules.auth.google import (
    GoogleEmailUnverifiedError,
    GoogleOAuthClient,
    GoogleOAuthError,
)
from app.modules.auth.schemas import (
    GoogleExchangeRequest,
    LoginRequest,
    SignupRequest,
    SignupResponse,
    TokenResponse,
)
from app.modules.auth.security import create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", status_code=201, response_model=SignupResponse)
async def signup(
    payload: SignupRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SignupResponse:
    try:
        user = await service.create_user(session, str(payload.email), payload.password)
    except service.EmailAlreadyExistsError:
        raise HTTPException(status_code=409, detail="Email already registered") from None
    return SignupResponse(access_token=create_access_token(str(user.id)), user=user)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    user = await service.authenticate_user(session, str(payload.email), payload.password)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.post("/google", response_model=TokenResponse)
async def google_login(
    payload: GoogleExchangeRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    google: Annotated[GoogleOAuthClient, Depends(get_google_client)],
) -> TokenResponse:
    if not settings.google_oauth_enabled:
        raise HTTPException(status_code=503, detail="Google sign-in is not configured")

    # A code issued for another callback must never be exchanged here.
    if payload.redirect_uri != settings.GOOGLE_REDIRECT_URI.strip():
        raise HTTPException(status_code=400, detail="Invalid redirect URI")

    try:
        profile = await google.exchange_code(
            code=payload.code,
            code_verifier=payload.code_verifier,
            redirect_uri=payload.redirect_uri,
        )
    except GoogleEmailUnverifiedError:
        raise HTTPException(
            status_code=403,
            detail="Google has not verified that email address.",
        ) from None
    except GoogleOAuthError:
        raise HTTPException(status_code=400, detail="Google sign-in failed.") from None

    try:
        user = await service.authenticate_google(session, profile)
    except service.GoogleAccountConflictError:
        raise HTTPException(
            status_code=409,
            detail="That email is already linked to a different sign-in method.",
        ) from None

    return TokenResponse(access_token=create_access_token(str(user.id)))
