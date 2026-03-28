from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Date, ForeignKey, Numeric
from app.core.db import Base

class Site(Base):
    __tablename__ = "sites"
    id: Mapped[int] = mapped_column(primary_key=True)
    site_code: Mapped[str] = mapped_column(String(100), unique=True)
    site_name: Mapped[str] = mapped_column(String(200))
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)

class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"))
    project_code: Mapped[str] = mapped_column(String(100), unique=True)
    project_name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(50), default="planning")
    dc_capacity_mwp: Mapped[float | None] = mapped_column(Numeric(12,3), nullable=True)
    ac_capacity_mw: Mapped[float | None] = mapped_column(Numeric(12,3), nullable=True)
    start_date: Mapped[str | None] = mapped_column(Date, nullable=True)
    planned_end_date: Mapped[str | None] = mapped_column(Date, nullable=True)
