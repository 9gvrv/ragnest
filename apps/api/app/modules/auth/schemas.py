from pydantic import BaseModel, EmailStr, Field

from app.modules.users.schemas import UserRead


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class GoogleExchangeRequest(BaseModel):
    code: str = Field(min_length=1)
    # RFC 7636: the verifier is 43-128 characters.
    code_verifier: str = Field(min_length=43, max_length=128)
    redirect_uri: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class SignupResponse(TokenResponse):
    user: UserRead
