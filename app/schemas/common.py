from datetime import datetime
from typing import Annotated, Any, Generic, List, TypeVar
from uuid import UUID

from pydantic import BaseModel, PlainSerializer
from pydantic.generics import GenericModel


T = TypeVar("T")


def _serialize_date_only(v: Any) -> str | None:
    """Serialize datetime/date to YYYY-MM-DD for API responses (no time)."""
    if v is None:
        return None
    if hasattr(v, "date"):
        return v.date().isoformat()
    s = str(v)
    return s[:10] if len(s) >= 10 else s


# Use in response/read schemas for datetime fields that should be returned as date-only (YYYY-MM-DD).
# Input validation unchanged; only serialization output is date string.
DateOnlySerialized = Annotated[
    datetime,
    PlainSerializer(_serialize_date_only, return_type=str),
]


class PaginatedResponse(GenericModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    limit: int


class OptionItem(BaseModel):
    """Lightweight schema for dropdown options - only id and name"""
    id: UUID
    name: str

    class Config:
        from_attributes = True
