from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File as FastAPIFile, HTTPException, Query, UploadFile, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.api import deps
from app.core.response import APIResponse, success_response
from app.models.candidate import (
    Candidate,
    CandidateEmploymentStatus,
    CandidatePayment,
    CandidateStatus,
    JocStructureFee,
)
from app.models.interview import Interview
from app.models.user import User
from app.schemas.candidate import CandidateCreate, CandidateRead, CandidateUpdate
from app.schemas.common import PaginatedResponse
from app.services.file_service import FileService


router = APIRouter(prefix="/candidates", tags=["candidates"])


@router.get("/", response_model=APIResponse[PaginatedResponse[CandidateRead]])
async def list_candidates(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    q: Optional[str] = Query(None, description="Search in name, email, mobile"),
    qualification: Optional[str] = Query(None),
    location_area_id: Optional[UUID] = Query(None),
    expected_salary_min: Optional[int] = Query(None, ge=0),
    expected_salary_max: Optional[int] = Query(None, ge=0),
    experience_min: Optional[float] = Query(None, ge=0),
    experience_max: Optional[float] = Query(None, ge=0),
    skills: Optional[List[str]] = Query(None),
    is_active: Optional[bool] = Query(True),
    session: AsyncSession = Depends(deps.get_db_session),
    current_user: User = Depends(deps.get_current_active_user),
) -> APIResponse[PaginatedResponse[CandidateRead]]:
    stmt = select(Candidate).options(
        joinedload(Candidate.location_area),
        selectinload(Candidate.fee_structure),
        selectinload(Candidate.payments),
    )
    filters = []

    if is_active is not None:
        filters.append(Candidate.is_active.is_(is_active))
    if qualification:
        filters.append(Candidate.qualification.ilike(f"%{qualification}%"))
    if location_area_id:
        filters.append(Candidate.location_area_id == location_area_id)
    if expected_salary_min is not None:
        filters.append(Candidate.expected_salary >= expected_salary_min)
    if expected_salary_max is not None:
        filters.append(Candidate.expected_salary <= expected_salary_max)
    if experience_min is not None:
        filters.append(Candidate.experience_years >= experience_min)
    if experience_max is not None:
        filters.append(Candidate.experience_years <= experience_max)
    if skills:
        filters.append(Candidate.skills.contains(skills))
    if q:
        like = f"%{q}%"
        filters.append(
            or_(
                Candidate.full_name.ilike(like),
                Candidate.email.ilike(like),
                Candidate.mobile_number.ilike(like),
            )
        )

    if filters:
        stmt = stmt.where(and_(*filters))

    stmt = stmt.order_by(Candidate.created_at.desc()).limit(limit).offset((page - 1) * limit)

    total_stmt = select(func.count()).select_from(Candidate)
    if filters:
        total_stmt = total_stmt.where(and_(*filters))

    result = await session.execute(stmt)
    candidates = result.scalars().all()
    candidate_ids = [c.id for c in candidates]
    counts_by_candidate: dict[UUID, int] = {}
    if candidate_ids:
        counts_stmt = (
            select(Interview.candidate_id, func.count())
            .where(and_(Interview.is_active.is_(True), Interview.candidate_id.in_(candidate_ids)))
            .group_by(Interview.candidate_id)
        )
        counts_res = await session.execute(counts_stmt)
        counts_by_candidate = {row[0]: int(row[1] or 0) for row in counts_res.all()}

    items = []
    for obj in candidates:
        if getattr(obj, "employment_status", None) is None:
            obj.employment_status = CandidateEmploymentStatus.UNEMPLOYED.value
        payload = CandidateRead.model_validate(obj)
        payload.interviews_count = counts_by_candidate.get(obj.id, 0)
        items.append(payload)

    total_result = await session.execute(total_stmt)
    total = int(total_result.scalar_one() or 0)

    data = PaginatedResponse[CandidateRead](items=items, total=total, page=page, limit=limit)
    return success_response(data)


@router.post("/", response_model=APIResponse[CandidateRead])
async def create_candidate(
    body: CandidateCreate,
    session: AsyncSession = Depends(deps.get_db_session),
    current_user: User = Depends(deps.require_role(["admin", "recruiter"])),
) -> APIResponse[CandidateRead]:
    payload = body.model_dump(exclude={"fee_structure", "initial_payment"})
    status_value = payload.get("status")
    if isinstance(status_value, CandidateStatus):
        payload["status"] = status_value.value

    fee_payload = body.fee_structure if body.status == CandidateStatus.JOC else None
    if body.status == CandidateStatus.JOC and fee_payload is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="fee_structure is required")

    pay_payload = body.initial_payment if body.status in {CandidateStatus.REGISTERED, CandidateStatus.JOC} else None
    if body.status in {CandidateStatus.REGISTERED, CandidateStatus.JOC} and pay_payload is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="initial_payment is required")

    candidate = Candidate(**payload, is_active=True)
    session.add(candidate)

    try:
        await session.flush()

        if fee_payload is not None:
            total_fee = int(fee_payload.total_fee)
            fee_row = JocStructureFee(
                candidate_id=candidate.id,
                total_fee=total_fee,
                balance=total_fee,
                due_date=fee_payload.due_date,
                is_active=True,
            )
            session.add(fee_row)

        if pay_payload is not None:
            payment = CandidatePayment(
                candidate_id=candidate.id,
                amount=pay_payload.amount,
                payment_date=pay_payload.payment_date,
                remarks=pay_payload.remarks,
                is_active=True,
            )
            session.add(payment)

        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Candidate with this email or mobile_number already exists",
        ) from exc

    stmt = (
        select(Candidate)
        .options(selectinload(Candidate.fee_structure), selectinload(Candidate.payments))
        .where(Candidate.id == candidate.id)
    )
    res = await session.execute(stmt)
    candidate_with_rels = res.scalar_one()
    return success_response(CandidateRead.model_validate(candidate_with_rels))


@router.get("/{candidate_id}", response_model=APIResponse[CandidateRead])
async def get_candidate(
    candidate_id: UUID,
    session: AsyncSession = Depends(deps.get_db_session),
    current_user: User = Depends(deps.get_current_active_user),
) -> APIResponse[CandidateRead]:
    stmt = (
        select(Candidate)
        .options(
            joinedload(Candidate.location_area),
            selectinload(Candidate.fee_structure),
            selectinload(Candidate.payments),
        )
        .where(Candidate.id == candidate_id)
    )
    res = await session.execute(stmt)
    candidate = res.scalar_one_or_none()
    if candidate is None or not candidate.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")

    count_stmt = select(func.count()).select_from(Interview).where(
        and_(Interview.is_active.is_(True), Interview.candidate_id == candidate_id)
    )
    count_res = await session.execute(count_stmt)
    interviews_count = int(count_res.scalar_one() or 0)

    if getattr(candidate, "employment_status", None) is None:
        candidate.employment_status = CandidateEmploymentStatus.UNEMPLOYED.value
    payload = CandidateRead.model_validate(candidate)
    payload.interviews_count = interviews_count
    return success_response(payload)


@router.put("/{candidate_id}", response_model=APIResponse[CandidateRead])
async def update_candidate(
    candidate_id: UUID,
    body: CandidateUpdate,
    session: AsyncSession = Depends(deps.get_db_session),
    current_user: User = Depends(deps.require_role(["admin", "recruiter"])),
) -> APIResponse[CandidateRead]:
    stmt = (
        select(Candidate)
        .options(selectinload(Candidate.fee_structure), selectinload(Candidate.payments))
        .where(Candidate.id == candidate_id)
    )
    res = await session.execute(stmt)
    candidate = res.scalar_one_or_none()
    if candidate is None or not candidate.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")

    update_data = body.model_dump(exclude_unset=True, exclude={"fee_structure", "initial_payment"})
    incoming_status = update_data.get("status")
    if isinstance(incoming_status, CandidateStatus):
        update_data["status"] = incoming_status.value

    for field, value in update_data.items():
        setattr(candidate, field, value)

    effective_status = CandidateStatus(candidate.status)

    if effective_status in {CandidateStatus.CAPS, CandidateStatus.FREE}:
        if body.fee_structure is not None or body.initial_payment is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="fee_structure and initial_payment are not allowed for CAPS/FREE",
            )

    if effective_status == CandidateStatus.REGISTERED:
        if body.fee_structure is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="fee_structure is not allowed for REGISTERED",
            )
        if body.initial_payment is not None:
            payment = CandidatePayment(
                candidate_id=candidate.id,
                amount=body.initial_payment.amount,
                payment_date=body.initial_payment.payment_date,
                remarks=body.initial_payment.remarks,
                is_active=True,
            )
            session.add(payment)

    if effective_status == CandidateStatus.JOC:
        if body.fee_structure is not None:
            if candidate.fee_structure is None:
                fee_row = JocStructureFee(
                    candidate_id=candidate.id,
                    total_fee=int(body.fee_structure.total_fee),
                    balance=int(body.fee_structure.total_fee),
                    due_date=body.fee_structure.due_date,
                    is_active=True,
                )
                session.add(fee_row)
            else:
                candidate.fee_structure.total_fee = int(body.fee_structure.total_fee)
                candidate.fee_structure.due_date = body.fee_structure.due_date
        if body.initial_payment is not None:
            payment = CandidatePayment(
                candidate_id=candidate.id,
                amount=body.initial_payment.amount,
                payment_date=body.initial_payment.payment_date,
                remarks=body.initial_payment.remarks,
                is_active=True,
            )
            session.add(payment)

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Candidate update conflict (email or mobile_number already exists)",
        ) from exc

    await session.refresh(candidate)
    return success_response(CandidateRead.model_validate(candidate))


@router.delete("/{candidate_id}", response_model=APIResponse[CandidateRead])
async def delete_candidate(
    candidate_id: UUID,
    session: AsyncSession = Depends(deps.get_db_session),
    current_user: User = Depends(deps.require_role(["admin"])),
) -> APIResponse[CandidateRead]:
    candidate = await session.get(Candidate, candidate_id)
    if not candidate or not candidate.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")

    candidate.is_active = False
    await session.commit()
    stmt = (
        select(Candidate)
        .options(selectinload(Candidate.fee_structure), selectinload(Candidate.payments))
        .where(Candidate.id == candidate_id)
    )
    res = await session.execute(stmt)
    candidate_with_rels = res.scalar_one()
    return success_response(CandidateRead.model_validate(candidate_with_rels))


@router.post("/{candidate_id}/upload", response_model=APIResponse[CandidateRead])
async def upload_candidate_files(
    candidate_id: UUID,
    resume: Optional[UploadFile] = FastAPIFile(None),
    photo: Optional[UploadFile] = FastAPIFile(None),
    session: AsyncSession = Depends(deps.get_db_session),
    current_user: User = Depends(deps.require_role(["admin", "recruiter"])),
) -> APIResponse[CandidateRead]:
    candidate = await session.get(Candidate, candidate_id)
    if not candidate or not candidate.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")

    file_service = FileService(session)

    if resume is not None:
        resume_file = await file_service.save_upload(resume, current_user)
        candidate.resume_url = resume_file.url

    if photo is not None:
        photo_file = await file_service.save_upload(photo, current_user)
        candidate.photo_url = photo_file.url

    await session.commit()
    await session.refresh(candidate)
    return success_response(CandidateRead.model_validate(candidate))
