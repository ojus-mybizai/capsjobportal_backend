from datetime import datetime, time
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.response import APIResponse, success_response
from app.models.candidate import Candidate, CandidateEmploymentStatus
from app.models.company import Company
from app.models.interview import Interview, InterviewStatus
from app.models.job import Job, JobStatus, Joined_candidates
from app.models.placement_income import PlacementIncome
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.interview import (
    InterviewCreate,
    InterviewRead,
    InterviewStatusUpdate,
    InterviewUpdate,
)


router = APIRouter(prefix="/interviews", tags=["interviews"])


@router.post("/", response_model=APIResponse[InterviewRead])
async def create_interview(
    body: InterviewCreate,
    session: AsyncSession = Depends(deps.get_db_session),
    current_user: User = Depends(deps.require_role(["admin", "recruiter"])),
) -> APIResponse[InterviewRead]:
    company = await session.get(Company, body.company_id)
    if not company or not company.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    job = await session.get(Job, body.job_id)
    if not job or not job.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    candidate = await session.get(Candidate, body.candidate_id)
    if not candidate or not candidate.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")

    interview = Interview(**body.model_dump())
    session.add(interview)
    await session.commit()
    await session.refresh(interview)

    return success_response(InterviewRead.model_validate(interview))


@router.get("/", response_model=APIResponse[PaginatedResponse[InterviewRead]])
async def list_interviews(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status_filter: Optional[InterviewStatus] = Query(None, alias="status"),
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    job_id: Optional[UUID] = Query(None),
    candidate_id: Optional[UUID] = Query(None),
    company_id: Optional[UUID] = Query(None),
    session: AsyncSession = Depends(deps.get_db_session),
    current_user: User = Depends(deps.get_current_active_user),
) -> APIResponse[PaginatedResponse[InterviewRead]]:
    filters = [Interview.is_active.is_(True)]

    if status_filter is not None:
        filters.append(Interview.status == status_filter.value)
    if from_date is not None:
        filters.append(Interview.interview_date >= from_date)
    if to_date is not None:
        filters.append(Interview.interview_date <= to_date)
    if job_id is not None:
        filters.append(Interview.job_id == job_id)
    if candidate_id is not None:
        filters.append(Interview.candidate_id == candidate_id)
    if company_id is not None:
        filters.append(Interview.company_id == company_id)

    stmt = select(Interview).where(and_(*filters)).order_by(Interview.created_at.desc())
    stmt = stmt.limit(limit).offset((page - 1) * limit)

    total_stmt = select(func.count()).select_from(Interview).where(and_(*filters))

    result = await session.execute(stmt)
    items = [InterviewRead.model_validate(x) for x in result.scalars().all()]

    total_res = await session.execute(total_stmt)
    total = int(total_res.scalar_one() or 0)

    return success_response(PaginatedResponse[InterviewRead](items=items, total=total, page=page, limit=limit))


@router.get("/{interview_id}", response_model=APIResponse[InterviewRead])
async def get_interview(
    interview_id: UUID,
    session: AsyncSession = Depends(deps.get_db_session),
    current_user: User = Depends(deps.get_current_active_user),
) -> APIResponse[InterviewRead]:
    interview = await session.get(Interview, interview_id)
    if not interview or not interview.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found")
    return success_response(InterviewRead.model_validate(interview))


@router.put("/{interview_id}", response_model=APIResponse[InterviewRead])
async def update_interview(
    interview_id: UUID,
    body: InterviewUpdate,
    session: AsyncSession = Depends(deps.get_db_session),
    current_user: User = Depends(deps.require_role(["admin", "recruiter"])),
) -> APIResponse[InterviewRead]:
    interview = await session.get(Interview, interview_id)
    if not interview or not interview.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found")

    update_data = body.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        if value is not None:
            setattr(interview, field, value)

    await session.commit()
    await session.refresh(interview)

    return success_response(InterviewRead.model_validate(interview))


@router.patch("/{interview_id}/status", response_model=APIResponse[InterviewRead])
async def update_interview_status(
    interview_id: UUID,
    body: InterviewStatusUpdate,
    session: AsyncSession = Depends(deps.get_db_session),
    current_user: User = Depends(deps.require_role(["admin", "recruiter"])),
) -> APIResponse[InterviewRead]:
    interview = await session.get(Interview, interview_id)
    if not interview or not interview.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found")

    job = await session.get(Job, interview.job_id)
    if not job or not job.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    candidate = await session.get(Candidate, interview.candidate_id)
    if not candidate or not candidate.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")

    placement_income_id: UUID | None = None

    if body.status == InterviewStatus.JOINED:
        if body.doj is None or body.salary is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="doj and salary are required when status is JOINED",
            )

        if body.placement_total_receivable is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="placement_total_receivable is required when status is JOINED",
            )

        if candidate.employment_status == CandidateEmploymentStatus.EMPLOYED.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Candidate is already EMPLOYED and cannot be joined to another job",
            )

        if int(job.num_vacancies or 0) <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No vacancies available for this job",
            )

        exists_stmt = (
            select(func.count())
            .select_from(Joined_candidates)
            .where(
                and_(
                    Joined_candidates.is_active.is_(True),
                    Joined_candidates.job_id == job.id,
                    Joined_candidates.candidate_id == interview.candidate_id,
                )
            )
        )
        exists_res = await session.execute(exists_stmt)
        already_joined = int(exists_res.scalar_one() or 0) > 0
        if already_joined:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Candidate already marked as JOINED for this job",
            )

        joined_row = Joined_candidates(
            job_id=job.id,
            candidate_id=interview.candidate_id,
            Date_of_joining=body.doj,
            salary=int(body.salary),
            remarks=None,
            is_active=True,
        )
        session.add(joined_row)

        existing_income_stmt = select(PlacementIncome).where(
            and_(
                PlacementIncome.is_active.is_(True),
                PlacementIncome.interview_id == interview.id,
            )
        )
        existing_income_res = await session.execute(existing_income_stmt)
        existing_income = existing_income_res.scalars().first()
        if existing_income is None:
            due_date = body.placement_due_date or body.doj
            income = PlacementIncome(
                interview_id=interview.id,
                candidate_id=interview.candidate_id,
                job_id=interview.job_id,
                total_receivable=int(body.placement_total_receivable),
                total_received=0,
                balance=int(body.placement_total_receivable),
                due_date=due_date,
                remarks=body.placement_remarks,
                is_active=True,
            )
            session.add(income)
            await session.flush()
            placement_income_id = income.id
        else:
            placement_income_id = existing_income.id

        job.num_vacancies = max(0, int(job.num_vacancies or 0) - 1)
        if int(job.num_vacancies or 0) == 0:
            job.status = JobStatus.FULFILLED.value

        candidate.employment_status = CandidateEmploymentStatus.EMPLOYED.value

    interview.status = body.status.value

    await session.commit()
    await session.refresh(interview)

    payload = InterviewRead.model_validate(interview)
    payload.placement_income_id = placement_income_id
    return success_response(payload)


@router.delete("/{interview_id}", response_model=APIResponse[InterviewRead])
async def delete_interview(
    interview_id: UUID,
    session: AsyncSession = Depends(deps.get_db_session),
    current_user: User = Depends(deps.require_role(["admin", "recruiter"])),
) -> APIResponse[InterviewRead]:
    interview = await session.get(Interview, interview_id)
    if not interview or not interview.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found")

    interview.is_active = False
    await session.commit()
    await session.refresh(interview)
    return success_response(InterviewRead.model_validate(interview))
