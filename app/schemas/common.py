from typing import Generic, List, TypeVar
from uuid import UUID

from pydantic import BaseModel
from pydantic.generics import GenericModel


T = TypeVar("T")


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
