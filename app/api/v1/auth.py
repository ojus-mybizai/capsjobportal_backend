from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.config import settings
from app.core.response import APIResponse, success_response
from app.core.security import create_access_token
from app.crud.user import authenticate_user, create_user, get_user_by_email
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenData
from app.schemas.user import UserCreate, UserRead


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=APIResponse[TokenData])
async def login(
    body: LoginRequest,
    session: AsyncSession = Depends(deps.get_db_session),
) -> APIResponse[TokenData]:
    user = await authenticate_user(session, body.email, body.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect email or password")

    access_token_expires = settings.ACCESS_TOKEN_EXPIRE_MINUTES
    access_token = create_access_token(str(user.id), expires_minutes=access_token_expires)
    token_data = TokenData(access_token=access_token, expires_in=access_token_expires)
    return success_response(token_data)


@router.post("/register", response_model=APIResponse[UserRead])
async def register_user(
    user_in: UserCreate,
    current_user: User = Depends(deps.require_role(["admin"])),
    session: AsyncSession = Depends(deps.get_db_session),
) -> APIResponse[UserRead]:
    existing = await get_user_by_email(session, user_in.email)
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    user = await create_user(session, user_in)
    return success_response(UserRead.model_validate(user))


@router.get("/me", response_model=APIResponse[UserRead])
async def read_users_me(
    current_user: User = Depends(deps.get_current_active_user),
) -> APIResponse[UserRead]:
    return success_response(UserRead.model_validate(current_user))
