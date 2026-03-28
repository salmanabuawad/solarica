from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer, Date, Boolean, ForeignKey, Text
from app.core.db import Base

class MaintenancePlan(Base):
    __tablename__ = "maintenance_plans"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    plan_name: Mapped[str] = mapped_column(String(200))
    interval_days: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class MaintenanceEvent(Base):
    __tablename__ = "maintenance_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    plan_id: Mapped[int | None] = mapped_column(ForeignKey("maintenance_plans.id", ondelete="SET NULL"), nullable=True)
    due_date: Mapped[str] = mapped_column(Date)
    completed_date: Mapped[str | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="scheduled")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
