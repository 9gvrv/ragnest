from pydantic import BaseModel, EmailStr, Field

from app.modules.users.schemas import UserRead


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class SignupResponse(TokenResponse):
    user: UserRead
