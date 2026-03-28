from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Date, ForeignKey, JSON, Text
from app.core.db import Base

class TestType(Base):
    __tablename__ = "test_types"
    id: Mapped[int] = mapped_column(primary_key=True)
    test_code: Mapped[str] = mapped_column(String(50), unique=True)
    test_name: Mapped[str] = mapped_column(String(100))

class TestRecord(Base):
    __tablename__ = "test_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    test_type_id: Mapped[int] = mapped_column(ForeignKey("test_types.id"))
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[int] = mapped_column()
    test_date: Mapped[str] = mapped_column(Date)
    result_status: Mapped[str] = mapped_column(String(30))
    measured_values: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    attachment_path: Mapped[str | None] = mapped_column(Text, nullable=True)
