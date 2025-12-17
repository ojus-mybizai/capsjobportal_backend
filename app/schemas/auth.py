from typing import Optional

from pydantic import BaseModel, EmailStr, constr


class LoginRequest(BaseModel):
    email: EmailStr
    password: constr(min_length=1)


class TokenData(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenPayload(BaseModel):
    sub: str
    exp: int
    type: str
