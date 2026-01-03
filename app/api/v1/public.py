from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.api import deps
from app.core.response import APIResponse, success_response
from app.models.master import (
    MasterCompanyCategory,
    MasterDegree,
    MasterEducation,
    MasterExperienceLevel,
    MasterJobCategory,
    MasterLocation,
    MasterSkill,
)
from app.models.candidate import Candidate
from app.models.company import Company
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.candidate import CandidatePublicCreate, CandidateRead
from app.schemas.company import CompanyPublicCreate, CompanyPublicRead
from app.schemas.master import MasterRead
from app.services.file_service import FileService


router = APIRouter(prefix="/public", tags=["public"])


PUBLIC_MASTER_MODEL_MAP = {
    "company_category": MasterCompanyCategory,
    "location": MasterLocation,
    "job_category": MasterJobCategory,
    "experience_level": MasterExperienceLevel,
    "skill": MasterSkill,
    "education": MasterEducation,
    "degree": MasterDegree,
}


def _get_public_master_model(master_name: str):
    model = PUBLIC_MASTER_MODEL_MAP.get(master_name)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown master '{master_name}'",
        )
    return model


@router.get("/masters", response_model=APIResponse[list[str]])
async def public_list_master_types() -> APIResponse[list[str]]:
    return success_response(sorted(PUBLIC_MASTER_MODEL_MAP.keys()))


@router.get("/masters/{master_name}", response_model=APIResponse[PaginatedResponse[MasterRead]])
async def public_list_masters(
    master_name: str,
    page: int = 1,
    limit: int = 100,
    q: str | None = None,
    session: AsyncSession = Depends(deps.get_db_session),
) -> APIResponse[PaginatedResponse[MasterRead]]:
    if page < 1:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="page must be >= 1")
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="limit must be between 1 and 100")

    model = _get_public_master_model(master_name)
    stmt = select(model)
    total_stmt = select(func.count()).select_from(model)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(model.name.ilike(like))
        total_stmt = total_stmt.where(model.name.ilike(like))

    result = await session.execute(stmt.limit(limit).offset((page - 1) * limit))
    items = [MasterRead.model_validate(obj) for obj in result.scalars().all()]

    total_result = await session.execute(total_stmt)
    total = int(total_result.scalar_one() or 0)

    data = PaginatedResponse[MasterRead](items=items, total=total, page=page, limit=limit)
    return success_response(data)


@router.get("/company/{user_id}/{company_id}", response_model=APIResponse[CompanyPublicRead])
async def public_company_detail(
    user_id: UUID,
    company_id: UUID,
    session: AsyncSession = Depends(deps.get_db_session),
) -> APIResponse[CompanyPublicRead]:
    result = await session.execute(
        select(Company)
        .options(
            joinedload(Company.category),
            joinedload(Company.location_area),
        )
        .where(
            and_(
                Company.id == company_id,
                Company.created_by == user_id,
                Company.is_active.is_(True),
            )
        )
    )
    company = result.scalar_one_or_none()
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    return success_response(CompanyPublicRead.model_validate(company))


@router.post("/addcompany/{user_id}", response_model=APIResponse[CompanyPublicRead])
async def public_create_company(
    user_id: UUID,
    body: CompanyPublicCreate,
    session: AsyncSession = Depends(deps.get_db_session),
) -> APIResponse[CompanyPublicRead]:
    user = await session.get(User, user_id)
    if user is None or getattr(user, "is_active", False) is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user",
        )

    data = body.model_dump()
    company = Company(
        **data,
        created_by=user.id,
        verification_status=False,
        company_status="FREE",
    )

    session.add(company)
    await session.commit()
    return success_response({"message": "Company created"})


@router.post("/companies/multipart", response_model=APIResponse[dict])
async def public_create_company_multipart(
    payload: str = Form(...),
    visiting_card: UploadFile | None = File(None),
    front_image: UploadFile | None = File(None),
    session: AsyncSession = Depends(deps.get_db_session),
) -> APIResponse[dict]:
    body = CompanyPublicCreate.model_validate_json(payload)
    data = body.model_dump()

    file_service = FileService(session)
    if visiting_card is not None:
        visiting_card_file = await file_service.save_upload(visiting_card, None)
        data["visiting_card_url"] = visiting_card_file.url
    if front_image is not None:
        front_image_file = await file_service.save_upload(front_image, None)
        data["front_image_url"] = front_image_file.url

    company = Company(
        **data,
        created_by=None,
        verification_status=False,
        company_status="FREE",
        is_active=True,
    )
    session.add(company)
    await session.commit()
    return success_response({"message": "Company created"})


@router.post("/companies", response_model=APIResponse[dict])
async def public_create_company_no_user(
    body: CompanyPublicCreate,
    session: AsyncSession = Depends(deps.get_db_session),
) -> APIResponse[dict]:
    data = body.model_dump()
    company = Company(
        **data,
        created_by=None,
        verification_status=False,
        company_status="FREE",
        is_active=True,
    )

    session.add(company)
    await session.commit()
    return success_response({"message": "Company created"})


@router.post("/candidates", response_model=APIResponse[dict])
async def public_create_candidate(
    body: CandidatePublicCreate,
    session: AsyncSession = Depends(deps.get_db_session),
) -> APIResponse[dict]:
    payload = body.model_dump()
    status_value = payload.get("status")
    if status_value is not None:
        payload["status"] = status_value.value

    candidate = Candidate(**payload, is_active=True, created_by=None)
    session.add(candidate)
    await session.commit()

    return success_response({"message": "Candidate created"})


@router.post("/candidates/multipart", response_model=APIResponse[dict])
async def public_create_candidate_multipart(
    payload: str = Form(...),
    resume: UploadFile | None = File(None),
    photo: UploadFile | None = File(None),
    session: AsyncSession = Depends(deps.get_db_session),
) -> APIResponse[dict]:
    body = CandidatePublicCreate.model_validate_json(payload)
    payload_dict = body.model_dump()
    status_value = payload_dict.get("status")
    if status_value is not None:
        payload_dict["status"] = status_value.value

    file_service = FileService(session)
    if resume is not None:
        resume_file = await file_service.save_upload(resume, None)
        payload_dict["resume_url"] = resume_file.url
    if photo is not None:
        photo_file = await file_service.save_upload(photo, None)
        payload_dict["photo_url"] = photo_file.url

    candidate = Candidate(**payload_dict, is_active=True, created_by=None)
    session.add(candidate)
    await session.commit()

    return success_response({"message": "Candidate created"})
