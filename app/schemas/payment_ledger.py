from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.schemas.common import DateOnlySerialized


class PaymentLedgerItem(BaseModel):
    id: UUID
    source: str
    payment_date: DateOnlySerialized
    amount: int
    created_at: DateOnlySerialized
    is_active: bool

    placement_income_id: UUID | None = None

    company_id: UUID | None = None
    company_name: str | None = None

    candidate_id: UUID | None = None
    candidate_name: str | None = None

    job_id: UUID | None = None
    job_title: str | None = None

    interview_id: UUID | None = None

    remarks: str | None = None

    # For candidate payments, indicate whether it is a joc fee or a registration fee
    candidate_payment_type: str | None = None


class PaymentDueItem(BaseModel):
    id: UUID  # ID of PlacementIncome or JocStructureFee
    source: str  # PLACEMENT_INCOME_PENDING or JOC_FEE_PENDING
    candidate_id: UUID
    candidate_name: str | None = None
    candidate_contact_number: str | None = None
    total_amount: int
    balance: int
    total_received: int
    due_date: DateOnlySerialized | None = None


class PaymentDueSummary(BaseModel):
    placement_income_pending_count: int
    placement_income_pending_amount: int
    joc_pending_count: int
    joc_pending_amount: int
    total_pending_count: int
    total_pending_amount: int
