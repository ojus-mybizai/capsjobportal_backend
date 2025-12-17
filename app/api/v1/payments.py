from uuid import UUID

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import cast, func, literal, select, String
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.response import APIResponse, success_response
from app.models.base import GUID
from app.models.candidate import Candidate, CandidatePayment
from app.models.company import Company, CompanyPayment
from app.models.job import Job
from app.models.placement_income import PlacementIncome, PlacementIncomePayment
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.company import CompanyPaymentCreate, CompanyPaymentRead
from app.schemas.payment_ledger import PaymentLedgerItem


router = APIRouter(prefix="/payments", tags=["payments"])


@router.get("/ledger", response_model=APIResponse[PaginatedResponse[PaymentLedgerItem]])
async def list_payment_ledger(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    source: list[str] | None = Query(None),
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    company_id: UUID | None = Query(None),
    candidate_id: UUID | None = Query(None),
    job_id: UUID | None = Query(None),
    min_amount: int | None = Query(None, ge=0),
    max_amount: int | None = Query(None, ge=0),
    include_inactive: bool = Query(False),
    session: AsyncSession = Depends(deps.get_db_session),
    current_user: User = Depends(deps.require_role(["admin", "recruiter"])),
) -> APIResponse[PaginatedResponse[PaymentLedgerItem]]:
    null_uuid = cast(literal(None), GUID())
    null_text = cast(literal(None), String())

    company_stmt = (
        select(
            CompanyPayment.id.label("id"),
            literal("COMPANY_PAYMENT").label("source"),
            CompanyPayment.payment_date.label("payment_date"),
            CompanyPayment.amount.label("amount"),
            CompanyPayment.created_at.label("created_at"),
            literal(True).label("is_active"),
            null_uuid.label("placement_income_id"),
            CompanyPayment.company_id.label("company_id"),
            Company.name.label("company_name"),
            null_uuid.label("candidate_id"),
            null_text.label("candidate_name"),
            null_uuid.label("job_id"),
            null_text.label("job_title"),
            null_uuid.label("interview_id"),
            null_text.label("remarks"),
        )
        .select_from(CompanyPayment)
        .join(Company, Company.id == CompanyPayment.company_id)
    )

    candidate_stmt = (
        select(
            CandidatePayment.id.label("id"),
            literal("CANDIDATE_PAYMENT").label("source"),
            CandidatePayment.payment_date.label("payment_date"),
            CandidatePayment.amount.label("amount"),
            CandidatePayment.created_at.label("created_at"),
            CandidatePayment.is_active.label("is_active"),
            null_uuid.label("placement_income_id"),
            null_uuid.label("company_id"),
            null_text.label("company_name"),
            CandidatePayment.candidate_id.label("candidate_id"),
            Candidate.full_name.label("candidate_name"),
            null_uuid.label("job_id"),
            null_text.label("job_title"),
            null_uuid.label("interview_id"),
            CandidatePayment.remarks.label("remarks"),
        )
        .select_from(CandidatePayment)
        .join(Candidate, Candidate.id == CandidatePayment.candidate_id)
    )

    placement_stmt = (
        select(
            PlacementIncomePayment.id.label("id"),
            literal("PLACEMENT_INCOME").label("source"),
            PlacementIncomePayment.paid_date.label("payment_date"),
            PlacementIncomePayment.amount.label("amount"),
            PlacementIncomePayment.created_at.label("created_at"),
            PlacementIncomePayment.is_active.label("is_active"),
            PlacementIncomePayment.placement_income_id.label("placement_income_id"),
            Job.company_id.label("company_id"),
            Company.name.label("company_name"),
            PlacementIncome.candidate_id.label("candidate_id"),
            Candidate.full_name.label("candidate_name"),
            PlacementIncome.job_id.label("job_id"),
            Job.title.label("job_title"),
            PlacementIncome.interview_id.label("interview_id"),
            PlacementIncomePayment.remarks.label("remarks"),
        )
        .select_from(PlacementIncomePayment)
        .join(PlacementIncome, PlacementIncome.id == PlacementIncomePayment.placement_income_id)
        .join(Job, Job.id == PlacementIncome.job_id)
        .join(Company, Company.id == Job.company_id)
        .join(Candidate, Candidate.id == PlacementIncome.candidate_id)
    )

    union_subq = company_stmt.union_all(candidate_stmt, placement_stmt).subquery("payment_ledger")

    filters: list = []
    if source:
        filters.append(union_subq.c.source.in_(source))
    if start_date is not None:
        filters.append(union_subq.c.payment_date >= start_date)
    if end_date is not None:
        filters.append(union_subq.c.payment_date <= end_date)
    if company_id is not None:
        filters.append(union_subq.c.company_id == company_id)
    if candidate_id is not None:
        filters.append(union_subq.c.candidate_id == candidate_id)
    if job_id is not None:
        filters.append(union_subq.c.job_id == job_id)
    if min_amount is not None:
        filters.append(union_subq.c.amount >= min_amount)
    if max_amount is not None:
        filters.append(union_subq.c.amount <= max_amount)
    if not include_inactive:
        filters.append(union_subq.c.is_active.is_(True))

    stmt = select(union_subq).order_by(
        union_subq.c.payment_date.desc(),
        union_subq.c.created_at.desc(),
    )
    if filters:
        stmt = stmt.where(*filters)
    stmt = stmt.limit(limit).offset((page - 1) * limit)

    total_stmt = select(func.count()).select_from(union_subq)
    if filters:
        total_stmt = total_stmt.where(*filters)

    res = await session.execute(stmt)
    items = [PaymentLedgerItem.model_validate(row) for row in res.mappings().all()]

    total_res = await session.execute(total_stmt)
    total = int(total_res.scalar_one() or 0)

    return success_response(PaginatedResponse[PaymentLedgerItem](items=items, total=total, page=page, limit=limit))


@router.put("/{payment_id}", response_model=APIResponse[CompanyPaymentRead])
async def update_payment(
    payment_id: UUID,
    body: CompanyPaymentCreate,
    session: AsyncSession = Depends(deps.get_db_session),
    current_user: User = Depends(deps.require_role(["admin", "recruiter"])),
) -> APIResponse[CompanyPaymentRead]:
    payment = await session.get(CompanyPayment, payment_id)
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")

    payment.amount = body.amount
    payment.payment_date = body.payment_date

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Payment update conflict",
        ) from exc
    await session.refresh(payment)
    return success_response(CompanyPaymentRead.model_validate(payment))


@router.delete("/{payment_id}", response_model=APIResponse[CompanyPaymentRead])
async def delete_payment(
    payment_id: UUID,
    session: AsyncSession = Depends(deps.get_db_session),
    current_user: User = Depends(deps.require_role(["admin"])),
) -> APIResponse[CompanyPaymentRead]:
    payment = await session.get(CompanyPayment, payment_id)
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")

    data = CompanyPaymentRead.model_validate(payment)
    await session.delete(payment)
    await session.commit()
    return success_response(data)
