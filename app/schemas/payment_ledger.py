from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class PaymentLedgerItem(BaseModel):
    id: UUID
    source: str
    payment_date: datetime
    amount: int
    created_at: datetime
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


class PaymentDueItem(BaseModel):
    source: str  # PLACEMENT_INCOME_PENDING or JOC_FEE_PENDING
    candidate_id: UUID
    candidate_name: str | None = None
    candidate_contact_number: str | None = None
    total_amount: int
    balance: int
    total_received: int
