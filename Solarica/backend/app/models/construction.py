from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer, Numeric, Date, ForeignKey, Text
from app.core.db import Base

class WorkPackage(Base):
    __tablename__ = "work_packages"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    package_code: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(200))
    section_id: Mapped[int | None] = mapped_column(ForeignKey("sections.id"), nullable=True)
    inverter_id: Mapped[int | None] = mapped_column(ForeignKey("inverters.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="planned")

class DailyProgressReport(Base):
    __tablename__ = "daily_progress_reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    report_date: Mapped[str] = mapped_column(Date)
    reported_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    crew_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weather_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    blockers: Mapped[str | None] = mapped_column(Text, nullable=True)

class ProgressItem(Base):
    __tablename__ = "progress_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("daily_progress_reports.id", ondelete="CASCADE"))
    work_package_id: Mapped[int | None] = mapped_column(ForeignKey("work_packages.id"), nullable=True)
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[int | None] = mapped_column(nullable=True)
    completed_qty: Mapped[float] = mapped_column(Numeric(12,2), default=0)
    uom: Mapped[str | None] = mapped_column(String(30), nullable=True)
    status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
