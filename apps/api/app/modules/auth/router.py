from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.auth import service
from app.modules.auth.schemas import LoginRequest, SignupRequest, SignupResponse, TokenResponse
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
