"""
TestType — lookup table of test codes (megger, isolation, continuity, iv_curve, polarity)
TestRecord — individual field test result linked to a project + entity (string, inverter, section)
"""
from __future__ import annotations
from datetime import datetime, timezone

from sqlalchemy import String, Text, JSON, Integer, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TestType(Base):
    __tablename__ = "test_types"

    id:        Mapped[int] = mapped_column(primary_key=True)
    test_code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    test_name: Mapped[str] = mapped_column(String(100))
    unit:      Mapped[str | None] = mapped_column(String(40), nullable=True)   # e.g. "MΩ", "V", "A"
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    records: Mapped[list[TestRecord]] = relationship("TestRecord", back_populates="test_type", cascade="all, delete-orphan")


class TestRecord(Base):
    __tablename__ = "test_records"

    id:            Mapped[int] = mapped_column(primary_key=True)
    project_id:    Mapped[int] = mapped_column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    test_type_id:  Mapped[int] = mapped_column(Integer, ForeignKey("test_types.id"))
    entity_type:   Mapped[str] = mapped_column(String(50))   # "string" | "inverter" | "section" | "array"
    entity_ref:    Mapped[str | None] = mapped_column(String(100), nullable=True)  # e.g. "S.1.2.3"
    test_date:     Mapped[str | None] = mapped_column(String(20), nullable=True)   # ISO date string
    result_status: Mapped[str] = mapped_column(String(30))   # "pass" | "fail" | "inconclusive"
    measured_values: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # flexible numeric payload
    notes:         Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by:   Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at:    Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    test_type: Mapped[TestType] = relationship("TestType", back_populates="records")

    def to_dict(self) -> dict:
        return {
            "id":              self.id,
            "project_id":      self.project_id,
            "test_type_id":    self.test_type_id,
            "test_code":       self.test_type.test_code if self.test_type else None,
            "test_name":       self.test_type.test_name if self.test_type else None,
            "unit":            self.test_type.unit if self.test_type else None,
            "entity_type":     self.entity_type,
            "entity_ref":      self.entity_ref,
            "test_date":       self.test_date,
            "result_status":   self.result_status,
            "measured_values": self.measured_values,
            "notes":           self.notes,
            "recorded_by":     self.recorded_by,
            "created_at":      self.created_at.isoformat() if self.created_at else None,
        }
