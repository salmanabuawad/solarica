from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer, ForeignKey, Numeric, Text
from app.core.db import Base

class DesignFile(Base):
    __tablename__ = "design_files"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    file_name: Mapped[str] = mapped_column(String(255))
    storage_path: Mapped[str] = mapped_column(Text)
    parser_status: Mapped[str] = mapped_column(String(30), default="pending")

class Section(Base):
    __tablename__ = "sections"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    section_code: Mapped[str] = mapped_column(String(50))
    section_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

class Inverter(Base):
    __tablename__ = "inverters"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    section_id: Mapped[int | None] = mapped_column(ForeignKey("sections.id", ondelete="SET NULL"), nullable=True)
    inverter_code: Mapped[str] = mapped_column(String(50))
    model_code: Mapped[str | None] = mapped_column(String(100), nullable=True)

class String(Base):
    __tablename__ = "strings"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    section_id: Mapped[int | None] = mapped_column(ForeignKey("sections.id", ondelete="SET NULL"), nullable=True)
    inverter_id: Mapped[int | None] = mapped_column(ForeignKey("inverters.id", ondelete="SET NULL"), nullable=True)
    string_code: Mapped[str] = mapped_column(String(50))
    string_index: Mapped[int] = mapped_column(Integer)
    module_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="planned")

class PanelGroup(Base):
    __tablename__ = "panel_groups"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    string_id: Mapped[int] = mapped_column(ForeignKey("strings.id", ondelete="CASCADE"))
    panel_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    panel_count: Mapped[int] = mapped_column(Integer)
    optimizer_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

class CablePath(Base):
    __tablename__ = "cable_paths"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    string_id: Mapped[int | None] = mapped_column(ForeignKey("strings.id", ondelete="SET NULL"), nullable=True)
    inverter_id: Mapped[int | None] = mapped_column(ForeignKey("inverters.id", ondelete="SET NULL"), nullable=True)
    path_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    estimated_length_m: Mapped[float | None] = mapped_column(Numeric(12,2), nullable=True)
    actual_length_m: Mapped[float | None] = mapped_column(Numeric(12,2), nullable=True)
