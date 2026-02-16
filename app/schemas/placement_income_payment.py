from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import DateOnlySerialized


class PlacementIncomePaymentBase(BaseModel):
    amount: int = Field(..., gt=0)
    paid_date: datetime
    remarks: Optional[str] = None


class PlacementIncomePaymentCreate(PlacementIncomePaymentBase):
    pass


class PlacementIncomePaymentUpdate(BaseModel):
    amount: Optional[int] = Field(default=None, gt=0)
    paid_date: Optional[datetime] = None
    remarks: Optional[str] = None
    is_active: Optional[bool] = None


class PlacementIncomePaymentRead(PlacementIncomePaymentBase):
    id: UUID
    placement_income_id: UUID
    is_active: bool
    paid_date: DateOnlySerialized  # output as date only
    created_at: DateOnlySerialized
    updated_at: DateOnlySerialized

    class Config:
        from_attributes = True
