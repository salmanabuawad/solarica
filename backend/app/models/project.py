from datetime import datetime
from sqlalchemy import String, DateTime, Numeric, Text, Boolean, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Legacy text field kept for backward compat; prefer customer_id FK
    customer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL"), nullable=True
    )
    site_name: Mapped[str] = mapped_column(String(255), nullable=False)
    project_type: Mapped[str] = mapped_column(String(100), nullable=False)
    phase: Mapped[str] = mapped_column(String(50), nullable=False, default="design")
    progress_percent: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    scan_analytics_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    string_pattern: Mapped[str | None] = mapped_column(String(64), nullable=True)  # e.g. "S.N.N.N" or "S.N.N.N.N"
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    customer: Mapped["Customer | None"] = relationship(  # type: ignore[name-defined]
        "Customer", back_populates="projects", foreign_keys=[customer_id]
    )

    validation_runs: Mapped[list["DesignValidationRun"]] = relationship(
        "DesignValidationRun", back_populates="project", cascade="all, delete-orphan"
    )
    inverters: Mapped[list["Inverter"]] = relationship(
        "Inverter", back_populates="project", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        cust = self.customer
        return {
            "id": self.id,
            "name": self.name,
            "customer_id": self.customer_id,
            "customer_name": (cust.name if cust else None) or self.customer_name,
            "company_id": (cust.company_id if cust else None),
            "company_name": (cust.company.name if cust and cust.company else None),
            "site_name": self.site_name,
            "project_type": self.project_type,
            "phase": self.phase,
            "progress_percent": float(self.progress_percent),
            "description": self.description,
            "is_active": self.is_active,
            "string_pattern": self.string_pattern,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class NamingPattern(Base):
    __tablename__ = "naming_patterns"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(50), nullable=False)
    pattern_name: Mapped[str] = mapped_column(String(100), nullable=False)
    pattern_regex: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DesignValidationRun(Base):
    __tablename__ = "design_validation_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    summary_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped["Project"] = relationship("Project", back_populates="validation_runs")
    issues: Mapped[list["DesignValidationIssue"]] = relationship(
        "DesignValidationIssue", back_populates="run", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "status": self.status,
            "summary_json": self.summary_json,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "issues": [i.to_dict() for i in self.issues],
        }


class DesignValidationIssue(Base):
    __tablename__ = "design_validation_issues"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    validation_run_id: Mapped[int] = mapped_column(ForeignKey("design_validation_runs.id", ondelete="CASCADE"))
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    asset_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    asset_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    issue_type: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    run: Mapped["DesignValidationRun"] = relationship("DesignValidationRun", back_populates="issues")

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "asset_type": self.asset_type,
            "asset_ref": self.asset_ref,
            "issue_type": self.issue_type,
            "message": self.message,
        }


class Inverter(Base):
    __tablename__ = "inverters"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    inverter_no: Mapped[str] = mapped_column(String(255), nullable=False)
    capacity_kw: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    project: Mapped["Project"] = relationship("Project", back_populates="inverters")
    strings: Mapped[list["String"]] = relationship("String", back_populates="inverter")


class String(Base):
    __tablename__ = "strings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    inverter_id: Mapped[int | None] = mapped_column(ForeignKey("inverters.id", ondelete="SET NULL"), nullable=True)
    string_no: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="planned")
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    inverter: Mapped["Inverter | None"] = relationship("Inverter", back_populates="strings")
