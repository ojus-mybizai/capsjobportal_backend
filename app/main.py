import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.logging import setup_logging
from app.db.session import AsyncSessionLocal
from app.api.v1 import auth as auth_routes
from app.api.v1 import health as health_routes
from app.api.v1 import masters as masters_routes
from app.api.v1 import companies as companies_routes
from app.api.v1 import jobs as jobs_routes
from app.api.v1 import candidates as candidates_routes
from app.api.v1 import candidate_payments as candidate_payments_routes
from app.api.v1 import public as public_routes
from app.api.v1 import interviews as interviews_routes
from app.api.v1 import placement_incomes as placement_incomes_routes
from app.api.v1 import files as files_routes
from app.api.v1 import reports as reports_routes
from app.api.v1 import payments as payments_routes
from app.crud.user import get_user_by_email, create_user
from app.models.user import UserRole
from app.schemas.user import UserCreate


setup_logging()

logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(origin).rstrip("/") for origin in settings.BACKEND_CORS_ORIGINS],
    allow_origin_regex=".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files (serve uploaded media)
app.mount(
    "/media",
    StaticFiles(directory=settings.MEDIA_ROOT, check_dir=True),
    name="media",
)


@app.on_event("startup")
async def init_default_users() -> None:
    """Create default users on application startup if they don't exist."""
    default_users = [
        {
            "email": "caps.infotech@gmail.com",
            "full_name": "Admin User",
            "password": "Caps@2024",
            "role": UserRole.admin.value,
        },
        {
            "email": "capstally.in@gmail.com",
            "full_name": "Recruiter User",
            "password": "Caps@2024",
            "role": UserRole.recruiter.value,
        },
    ]

    async with AsyncSessionLocal() as session:
        for user_data in default_users:
            existing = await get_user_by_email(session, user_data["email"])
            if existing:
                logger.info(f"User {user_data['email']} already exists, skipping creation")
                continue

            user_in = UserCreate(
                email=user_data["email"],
                full_name=user_data["full_name"],
                password=user_data["password"],
                role=user_data["role"],
            )
            try:
                await create_user(session, user_in)
                logger.info(f"Created default user: {user_data['email']} with role {user_data['role']}")
            except Exception as e:
                logger.error(f"Failed to create user {user_data['email']}: {e}")

# Routers
app.include_router(health_routes.router, prefix=settings.API_V1_STR)
app.include_router(auth_routes.router, prefix=settings.API_V1_STR)
app.include_router(public_routes.router, prefix=settings.API_V1_STR)
app.include_router(masters_routes.router, prefix=settings.API_V1_STR)
app.include_router(companies_routes.router, prefix=settings.API_V1_STR)
app.include_router(jobs_routes.router, prefix=settings.API_V1_STR)
app.include_router(candidates_routes.router, prefix=settings.API_V1_STR)
app.include_router(candidate_payments_routes.router, prefix=settings.API_V1_STR)
app.include_router(interviews_routes.router, prefix=settings.API_V1_STR)
app.include_router(placement_incomes_routes.router, prefix=settings.API_V1_STR)
app.include_router(files_routes.router, prefix=settings.API_V1_STR)
app.include_router(reports_routes.router, prefix=settings.API_V1_STR)
app.include_router(payments_routes.router, prefix=settings.API_V1_STR)


@app.get("/health", tags=["health"])
async def root_health_check() -> dict[str, str]:
    return {"status": "ok"}
