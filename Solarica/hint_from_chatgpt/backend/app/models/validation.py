from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Boolean, Integer, ForeignKey, Text, JSON
from app.core.db import Base

class ValidationRule(Base):
    __tablename__ = "validation_rules"
    id: Mapped[int] = mapped_column(primary_key=True)
    rule_code: Mapped[str] = mapped_column(String(100), unique=True)
    rule_name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(50))
    scope: Mapped[str] = mapped_column(String(50))
    severity: Mapped[str] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    engine_type: Mapped[str] = mapped_column(String(50))
    message_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version_no: Mapped[int] = mapped_column(Integer, default=1)

class ValidationRuleParameter(Base):
    __tablename__ = "validation_rule_parameters"
    id: Mapped[int] = mapped_column(primary_key=True)
    rule_id: Mapped[int] = mapped_column(ForeignKey("validation_rules.id", ondelete="CASCADE"))
    param_key: Mapped[str] = mapped_column(String(100))
    param_value: Mapped[str] = mapped_column(Text)
    param_type: Mapped[str] = mapped_column(String(30))

class ValidationRun(Base):
    __tablename__ = "validation_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    design_file_id: Mapped[int | None] = mapped_column(ForeignKey("design_files.id", ondelete="SET NULL"), nullable=True)
    run_status: Mapped[str] = mapped_column(String(30), default="pending")

class ValidationIssue(Base):
    __tablename__ = "validation_issues"
    id: Mapped[int] = mapped_column(primary_key=True)
    validation_run_id: Mapped[int] = mapped_column(ForeignKey("validation_runs.id", ondelete="CASCADE"))
    rule_code: Mapped[str] = mapped_column(String(100))
    severity: Mapped[str] = mapped_column(String(20))
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_key: Mapped[str] = mapped_column(String(200))
    issue_message: Mapped[str] = mapped_column(Text)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    suggested_fix: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="open")

class ValidationException(Base):
    __tablename__ = "validation_exceptions"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    rule_code: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_key: Mapped[str] = mapped_column(String(200))
    reason: Mapped[str] = mapped_column(Text)
