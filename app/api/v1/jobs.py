from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File as FastAPIFile, HTTPException, Query, UploadFile, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api import deps
from app.core.response import APIResponse, success_response
from app.models.interview import Interview
from app.models.job import Job, JobStatus, JobType, Joined_candidates
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.job import JobCreate, JobRead, JobStatusUpdate, JobUpdate
from app.services.file_service import FileService


router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/", response_model=APIResponse[PaginatedResponse[JobRead]])
async def list_jobs(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    company_id: Optional[UUID] = Query(None),
    status_filter: Optional[JobStatus] = Query(None, alias="status"),
    location_area_id: Optional[UUID] = Query(None),
    min_salary: Optional[int] = Query(None, ge=0),
    max_salary: Optional[int] = Query(None, ge=0),
    skills: Optional[List[str]] = Query(None),
    q: Optional[str] = Query(None, description="Search in title and description"),
    sort_by: Optional[str] = Query("created_at"),
    order: Optional[str] = Query("desc"),
    session: AsyncSession = Depends(deps.get_db_session),
    current_user: User = Depends(deps.get_current_active_user),
) -> APIResponse[PaginatedResponse[JobRead]]:
    stmt = select(Job).options(
        joinedload(Job.company),
        joinedload(Job.joined_candidates).joinedload(Joined_candidates.candidate),
    )
    filters = [Job.is_active.is_(True)]

    if company_id:
        filters.append(Job.company_id == company_id)
    if status_filter:
        filters.append(Job.status == status_filter.value)
    if location_area_id:
        filters.append(Job.location_area_id == location_area_id)
    if min_salary is not None:
        filters.append(Job.salary_min >= min_salary)
    if max_salary is not None:
        filters.append(Job.salary_max <= max_salary)
    if skills:
        filters.append(Job.skills.contains(skills))
    if q:
        like = f"%{q}%"
        filters.append(or_(Job.title.ilike(like), Job.description.ilike(like)))

    if filters:
        stmt = stmt.where(and_(*filters))

    sort_attr = getattr(Job, sort_by, Job.created_at)
    if order == "asc":
        stmt = stmt.order_by(sort_attr.asc())
    else:
        stmt = stmt.order_by(sort_attr.desc())

    stmt = stmt.limit(limit).offset((page - 1) * limit)

    total_stmt = select(func.count()).select_from(Job)
    if filters:
        total_stmt = total_stmt.where(and_(*filters))

    result = (await session.execute(stmt)).unique()
    jobs = result.scalars().all()
    items = [JobRead.model_validate(job) for job in jobs]

    total_result = await session.execute(total_stmt)
    total = int(total_result.scalar_one() or 0)

    job_ids = [job.id for job in jobs]
    counts_by_job: dict[UUID, int] = {}
    if job_ids:
        counts_stmt = (
            select(Interview.job_id, func.count())
            .where(and_(Interview.is_active.is_(True), Interview.job_id.in_(job_ids)))
            .group_by(Interview.job_id)
        )
        counts_res = await session.execute(counts_stmt)
        counts_by_job = {row[0]: int(row[1] or 0) for row in counts_res.all()}

    items = []
    for job in jobs:
        payload = JobRead.model_validate(job)
        payload.interviews_count = counts_by_job.get(job.id, 0)
        items.append(payload)

    data = PaginatedResponse[JobRead](items=items, total=total, page=page, limit=limit)
    return success_response(data)


@router.post("/", response_model=APIResponse[JobRead])
async def create_job(
    body: JobCreate,
    session: AsyncSession = Depends(deps.get_db_session),
    current_user: User = Depends(deps.require_role(["admin", "recruiter"])),
) -> APIResponse[JobRead]:
    job_data = body.model_dump()
    status_value = job_data.pop("status", JobStatus.OPEN)

    job_type_value = job_data.get("job_type")
    if isinstance(job_type_value, JobType):
        job_data["job_type"] = job_type_value.value

    job = Job(
        **job_data,
        status=status_value.value,
    )
    session.add(job)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Job creation conflict",
        ) from exc
    stmt = (
        select(Job)
        .options(
            joinedload(Job.company),
            joinedload(Job.joined_candidates).joinedload(Joined_candidates.candidate),
        )
        .where(Job.id == job.id)
    )
    result = (await session.execute(stmt)).unique()
    job_with_rels = result.scalar_one()
    return success_response(JobRead.model_validate(job_with_rels))


@router.get("/{job_id}", response_model=APIResponse[JobRead])
async def get_job(
    job_id: UUID,
    session: AsyncSession = Depends(deps.get_db_session),
    current_user: User = Depends(deps.get_current_active_user),
) -> APIResponse[JobRead]:
    stmt = (
        select(Job)
        .options(
            joinedload(Job.company),
            joinedload(Job.joined_candidates).joinedload(Joined_candidates.candidate),
        )
        .where(Job.id == job_id)
    )
    result = (await session.execute(stmt)).unique()
    job = result.scalar_one_or_none()
    if job is None or not job.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    count_stmt = select(func.count()).select_from(Interview).where(
        and_(Interview.is_active.is_(True), Interview.job_id == job_id)
    )
    count_res = await session.execute(count_stmt)
    interviews_count = int(count_res.scalar_one() or 0)

    payload = JobRead.model_validate(job)
    payload.interviews_count = interviews_count
    return success_response(payload)


@router.put("/{job_id}", response_model=APIResponse[JobRead])
async def update_job(
    job_id: UUID,
    body: JobUpdate,
    session: AsyncSession = Depends(deps.get_db_session),
    current_user: User = Depends(deps.require_role(["admin", "recruiter"])),
) -> APIResponse[JobRead]:
    stmt = (
        select(Job)
        .options(
            joinedload(Job.company),
            joinedload(Job.joined_candidates).joinedload(Joined_candidates.candidate),
        )
        .where(Job.id == job_id)
    )
    result = (await session.execute(stmt)).unique()
    job = result.scalar_one_or_none()
    if job is None or not job.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    update_data = body.model_dump(exclude_unset=True)
    status_value = update_data.pop("status", None)
    for field, value in update_data.items():
        if field == "job_type" and isinstance(value, JobType):
            value = value.value
        setattr(job, field, value)
    if status_value is not None:
        job.status = status_value.value

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Job update conflict",
        ) from exc
    stmt = (
        select(Job)
        .options(
            joinedload(Job.company),
            joinedload(Job.joined_candidates).joinedload(Joined_candidates.candidate),
        )
        .where(Job.id == job_id)
    )
    result = (await session.execute(stmt)).unique()
    job_with_rels = result.scalar_one()
    return success_response(JobRead.model_validate(job_with_rels))


@router.patch("/{job_id}/status", response_model=APIResponse[JobRead])
async def update_job_status(
    job_id: UUID,
    body: JobStatusUpdate,
    session: AsyncSession = Depends(deps.get_db_session),
    current_user: User = Depends(deps.require_role(["admin", "recruiter"])),
) -> APIResponse[JobRead]:
    stmt = (
        select(Job)
        .options(
            joinedload(Job.company),
            joinedload(Job.joined_candidates).joinedload(Joined_candidates.candidate),
        )
        .where(Job.id == job_id)
    )
    result = (await session.execute(stmt)).unique()
    job = result.scalar_one_or_none()
    if job is None or not job.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    job.status = body.status.value
    await session.commit()
    stmt = (
        select(Job)
        .options(
            joinedload(Job.company),
            joinedload(Job.joined_candidates).joinedload(Joined_candidates.candidate),
        )
        .where(Job.id == job_id)
    )
    result = (await session.execute(stmt)).unique()
    job_with_rels = result.scalar_one()
    return success_response(JobRead.model_validate(job_with_rels))


@router.post("/{job_id}/attachments", response_model=APIResponse[JobRead])
async def upload_job_attachments(
    job_id: UUID,
    files: List[UploadFile] = FastAPIFile(...),
    session: AsyncSession = Depends(deps.get_db_session),
    current_user: User = Depends(deps.require_role(["admin", "recruiter"])),
) -> APIResponse[JobRead]:
    stmt = (
        select(Job)
        .options(
            joinedload(Job.company),
            joinedload(Job.joined_candidates).joinedload(Joined_candidates.candidate),
        )
        .where(Job.id == job_id)
    )
    result = (await session.execute(stmt)).unique()
    job = result.scalar_one_or_none()
    if job is None or not job.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    file_service = FileService(session)

    attachments = list(job.attachments or [])
    for upload in files:
        stored = await file_service.save_upload(upload, current_user)
        attachments.append(stored.url)

    job.attachments = attachments

    await session.commit()
    stmt = (
        select(Job)
        .options(
            joinedload(Job.company),
            joinedload(Job.joined_candidates).joinedload(Joined_candidates.candidate),
        )
        .where(Job.id == job_id)
    )
    result = (await session.execute(stmt)).unique()
    job_with_rels = result.scalar_one()
    return success_response(JobRead.model_validate(job_with_rels))
