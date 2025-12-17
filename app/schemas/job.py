from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, computed_field

from app.models.job import JobStatus, JobType


class JobBase(BaseModel):
    company_id: UUID
    title: str
    qualification: Optional[str] = None
    experience: Optional[str] = None
    salary_min: Optional[int] = Field(default=None, ge=0)
    salary_max: Optional[int] = Field(default=None, ge=0)
    num_vacancies: int = Field(default=1, ge=1)
    job_type: JobType = JobType.FULL_TIME
    description: Optional[str] = None
    responsibilities: Optional[str] = None
    skills: Optional[list[str] | dict] = None
    education: Optional[List[str]] = None
    location_area_id: Optional[UUID] = None
    contact_person: Optional[str] = None

    # @field_validator("salary_max")
    # @classmethod
    # def validate_salary_bounds(cls, v, values):  # type: ignore[override]
    #     salary_min = values["salary_min"]
    #     if v is not None and salary_min is not None and salary_min > v:
    #         raise ValueError("salary_min cannot be greater than salary_max")
    #     return v


class JobCreate(JobBase):
    status: JobStatus = JobStatus.OPEN


class JobUpdate(BaseModel):
    title: Optional[str] = None
    qualification: Optional[str] = None
    experience: Optional[str] = None
    salary_min: Optional[int] = Field(default=None, ge=0)
    salary_max: Optional[int] = Field(default=None, ge=0)
    num_vacancies: Optional[int] = Field(default=None, ge=0)
    job_type: Optional[JobType] = None
    description: Optional[str] = None
    responsibilities: Optional[str] = None
    skills: Optional[list[str] | dict] = None
    education: Optional[List[str]] = None
    location_area_id: Optional[UUID] = None
    contact_person: Optional[str] = None
    status: Optional[JobStatus] = None
    is_active: Optional[bool] = None

    # @field_validator("salary_max")
    # @classmethod
    # def validate_salary_bounds(cls, v, values):  # type: ignore[override]
    #     salary_min = values.get("salary_min")
    #     if v is not None and salary_min is not None and salary_min > v:
    #         raise ValueError("salary_min cannot be greater than salary_max")
    #     return v


class JoinedCandidateRead(BaseModel):
    id: UUID
    job_id: UUID
    candidate_id: UUID
    Date_of_joining: datetime
    candidate_name: Optional[str] = None
    salary: int
    remarks: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @computed_field(return_type=datetime)
    @property
    def doj(self) -> datetime:
        return self.Date_of_joining

    class Config:
        from_attributes = True


class JobRead(JobBase):
    id: UUID
    company_name: Optional[str] = None
    status: JobStatus
    attachments: Optional[List[str]] = None
    joined_candidates: Optional[List[JoinedCandidateRead]] = None
    interviews_count: Optional[int] = None
    num_vacancies: int = Field(ge=0)
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class JobStatusUpdate(BaseModel):
    status: JobStatus
