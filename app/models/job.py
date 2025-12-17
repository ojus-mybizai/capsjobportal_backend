import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GUID, TimestampMixin


class JobStatus(str, enum.Enum):
    OPEN = "OPEN"
    FULFILLED = "FULFILLED"
    DROPPED = "DROPPED"

class JobType(str, enum.Enum):
    FULL_TIME = "FULL_TIME"
    PART_TIME = "PART_TIME"
    INTERNSHIP = "INTERNSHIP"

class Job(TimestampMixin, Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint("num_vacancies >= 0", name="ck_jobs_num_vacancies_positive"),
        CheckConstraint(
            "salary_min IS NULL OR salary_max IS NULL OR salary_min <= salary_max",
            name="ck_jobs_salary_bounds",
        ),
        Index("ix_jobs_company_id", "company_id"),
        Index("ix_jobs_title", "title"),
        Index("ix_jobs_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("companies.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    qualification: Mapped[str | None] = mapped_column(Text, nullable=True)
    experience: Mapped[str | None] = mapped_column(Text, nullable=True)
    salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    num_vacancies: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    job_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default=JobType.FULL_TIME.value
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    responsibilities: Mapped[str | None] = mapped_column(Text, nullable=True)
    skills: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    education: Mapped[list | None] = mapped_column(JSON, nullable=True)
    location_area_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("master_location.id"), nullable=True
    )
    contact_person: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=JobStatus.OPEN.value
    )
    attachments: Mapped[list | None] = mapped_column(JSON, nullable=True)
    joined_candidates: Mapped[list["Joined_candidates"]] = relationship("Joined_candidates", back_populates="job")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    company: Mapped["Company"] = relationship("Company", back_populates="jobs")

    @property
    def company_name(self) -> str | None:
        if self.company is None:
            return None
        return self.company.name


class Joined_candidates(TimestampMixin, Base):
    __tablename__ = "joined_candidates"
    __table_args__ = (
        Index("ix_joined_candidates_job_id", "job_id"),
        Index("ix_joined_candidates_candidate_id", "candidate_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("jobs.id"), nullable=False)
    candidate_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("candidates.id"), nullable=False)
    Date_of_joining: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    salary: Mapped[int] = mapped_column(Integer, nullable=False)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    job: Mapped["Job"] = relationship("Job", back_populates="joined_candidates")
    candidate: Mapped["Candidate"] = relationship("Candidate")

    @property
    def candidate_name(self) -> str | None:
        if self.candidate is None:
            return None
        return self.candidate.full_name