from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import DateOnlySerialized


class CandidatePaymentBase(BaseModel):
    amount: int = Field(..., gt=0)
    payment_date: datetime
    remarks: Optional[str] = None


class CandidatePaymentCreate(CandidatePaymentBase):
    pass


class CandidatePaymentRead(CandidatePaymentBase):
    id: UUID
    candidate_id: UUID
    is_active: bool
    payment_date: DateOnlySerialized  # output as date only
    created_at: DateOnlySerialized
    updated_at: DateOnlySerialized

    class Config:
        from_attributes = True
