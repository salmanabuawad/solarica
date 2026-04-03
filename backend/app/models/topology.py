"""
Topology models: ProjectInverter, ProjectMPPT, MapZone.
These store the design topology detected from PDF/DXF scans.
"""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import Integer, String, Float, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class ProjectInverter(Base):
    __tablename__ = "project_inverters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    inverter_label: Mapped[str] = mapped_column(String(32), nullable=False)   # e.g. "1.16"
    section_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    block_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    icb_zone: Mapped[str | None] = mapped_column(String(32), nullable=True)   # e.g. "ICB-area-1.1"
    color_group: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expected_string_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detected_string_count: Mapped[int] = mapped_column(Integer, default=0)
    detection_pattern: Mapped[str | None] = mapped_column(String(32), nullable=True)  # frequency_scan / gap_fill / inferred
    is_inferred: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    mpputs: Mapped[list["ProjectMPPT"]] = relationship("ProjectMPPT", back_populates="inverter", cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "inverter_label": self.inverter_label,
            "section_no": self.section_no,
            "block_no": self.block_no,
            "icb_zone": self.icb_zone,
            "color_group": self.color_group,
            "expected_string_count": self.expected_string_count,
            "detected_string_count": self.detected_string_count,
            "detection_pattern": self.detection_pattern,
            "is_inferred": self.is_inferred,
        }


class ProjectMPPT(Base):
    __tablename__ = "project_mpputs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    inverter_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("project_inverters.id", ondelete="CASCADE"), nullable=True)
    inverter_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    icb_zone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    dc_terminal_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mppt_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detected_string_count: Mapped[int] = mapped_column(Integer, default=0)
    expected_string_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    channel_labels: Mapped[list | None] = mapped_column(JSON, nullable=True)  # list of raw channel strings

    inverter: Mapped["ProjectInverter | None"] = relationship("ProjectInverter", back_populates="mpputs")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "inverter_label": self.inverter_label,
            "icb_zone": self.icb_zone,
            "dc_terminal_no": self.dc_terminal_no,
            "mppt_no": self.mppt_no,
            "detected_string_count": self.detected_string_count,
            "expected_string_count": self.expected_string_count,
            "channel_labels": self.channel_labels or [],
        }


class MapZone(Base):
    __tablename__ = "map_zones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    zone_label: Mapped[str] = mapped_column(String(64), nullable=False)       # e.g. "Zone-A" or "ICB-area-1.1"
    color_code: Mapped[str | None] = mapped_column(String(32), nullable=True) # e.g. "#FF0000" or "red"
    inverter_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    geometry_ref: Mapped[str | None] = mapped_column(String(256), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "zone_label": self.zone_label,
            "color_code": self.color_code,
            "inverter_label": self.inverter_label,
            "geometry_ref": self.geometry_ref,
            "notes": self.notes,
        }
