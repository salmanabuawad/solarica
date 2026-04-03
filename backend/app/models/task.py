from datetime import datetime
from sqlalchemy import String, DateTime, Text, Boolean, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class MaintenanceTask(Base):
    __tablename__ = "maintenance_tasks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    site_name: Mapped[str] = mapped_column(String(255), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(50), nullable=False)
    asset_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_type: Mapped[str] = mapped_column(String(50), nullable=False, default="maintenance")
    priority: Mapped[str] = mapped_column(String(50), nullable=False, default="medium")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="open")
    assigned_to: Mapped[str | None] = mapped_column(String(255), nullable=True)
    requires_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    requires_test_result: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    messages: Mapped[list["TaskMessage"]] = relationship(
        "TaskMessage", back_populates="task", cascade="all, delete-orphan",
        order_by="TaskMessage.created_at"
    )
    attachments: Mapped[list["TaskAttachment"]] = relationship(
        "TaskAttachment", back_populates="task", cascade="all, delete-orphan"
    )
    approvals: Mapped[list["TaskApproval"]] = relationship(
        "TaskApproval", back_populates="task", cascade="all, delete-orphan"
    )
    test_results: Mapped[list["TaskTestResult"]] = relationship(
        "TaskTestResult", back_populates="task", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "site_name": self.site_name,
            "asset_type": self.asset_type,
            "asset_ref": self.asset_ref,
            "title": self.title,
            "description": self.description,
            "task_type": self.task_type,
            "priority": self.priority,
            "status": self.status,
            "assigned_to": self.assigned_to,
            "requires_approval": self.requires_approval,
            "requires_test_result": self.requires_test_result,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "messages": [m.to_dict() for m in self.messages],
            "approvals": [a.to_dict() for a in self.approvals],
            "test_results": [tr.to_dict() for tr in self.test_results],
        }


class TaskMessage(Base):
    __tablename__ = "task_messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("maintenance_tasks.id", ondelete="CASCADE"), nullable=False)
    author_name: Mapped[str] = mapped_column(String(255), nullable=False)
    message_type: Mapped[str] = mapped_column(String(50), nullable=False, default="text")
    message_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    task: Mapped["MaintenanceTask"] = relationship("MaintenanceTask", back_populates="messages")

    def to_dict(self) -> dict:
        return {
            "author_name": self.author_name,
            "message_type": self.message_type,
            "message_text": self.message_text,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class TaskAttachment(Base):
    __tablename__ = "task_attachments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("maintenance_tasks.id", ondelete="CASCADE"), nullable=False)
    message_id: Mapped[int | None] = mapped_column(ForeignKey("task_messages.id", ondelete="SET NULL"), nullable=True)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    uploaded_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    task: Mapped["MaintenanceTask"] = relationship("MaintenanceTask", back_populates="attachments")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "file_type": self.file_type,
            "file_name": self.file_name,
            "mime_type": self.mime_type,
            "uploaded_by": self.uploaded_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class TaskApproval(Base):
    __tablename__ = "task_approvals"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("maintenance_tasks.id", ondelete="CASCADE"), nullable=False)
    approval_level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    approval_role: Mapped[str] = mapped_column(String(100), nullable=False, default="manager")
    approver_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    task: Mapped["MaintenanceTask"] = relationship("MaintenanceTask", back_populates="approvals")

    def to_dict(self) -> dict:
        return {
            "approver_name": self.approver_name,
            "decision_note": self.decision_note,
            "status": self.status,
            "decided_at": self.decided_at.isoformat() if self.decided_at else None,
        }


class TaskTestResult(Base):
    __tablename__ = "task_test_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("maintenance_tasks.id", ondelete="CASCADE"), nullable=False)
    test_type: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="informational")
    raw_result_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    task: Mapped["MaintenanceTask"] = relationship("MaintenanceTask", back_populates="test_results")

    def to_dict(self) -> dict:
        return {
            "test_type": self.test_type,
            "title": self.title,
            "summary": self.summary,
            "status": self.status,
            "raw_result_json": self.raw_result_json,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
