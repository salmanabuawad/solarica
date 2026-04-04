from __future__ import annotations
from datetime import datetime
from sqlalchemy import Integer, String, Text, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class MapLayer(Base):
    __tablename__ = "map_layers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    layer_type: Mapped[str] = mapped_column(String(50), nullable=False)
    is_visible_default: Mapped[bool] = mapped_column(Boolean, default=True)
    z_index: Mapped[int] = mapped_column(Integer, default=0)
    style_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    objects: Mapped[list["MapObject"]] = relationship("MapObject", back_populates="layer", cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "name": self.name,
            "layer_type": self.layer_type,
            "is_visible_default": self.is_visible_default,
            "z_index": self.z_index,
            "style_json": self.style_json or {},
        }


class MapObject(Base):
    __tablename__ = "map_objects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    layer_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("map_layers.id", ondelete="SET NULL"), nullable=True, index=True)
    object_uid: Mapped[str] = mapped_column(String(128), nullable=False)
    object_type: Mapped[str] = mapped_column(String(64), nullable=False)
    subtype: Mapped[str | None] = mapped_column(String(64), nullable=True)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    geometry_type: Mapped[str] = mapped_column(String(32), nullable=False, default="point")
    geometry_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    properties_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    parent_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("map_objects.id", ondelete="SET NULL"), nullable=True)
    source_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    layer: Mapped["MapLayer | None"] = relationship("MapLayer", back_populates="objects")
    parent: Mapped["MapObject | None"] = relationship("MapObject", remote_side=[id])
    links: Mapped[list["MapObjectLink"]] = relationship("MapObjectLink", back_populates="object", cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "layer_id": self.layer_id,
            "object_uid": self.object_uid,
            "object_type": self.object_type,
            "subtype": self.subtype,
            "label": self.label,
            "geometry_type": self.geometry_type,
            "geometry": self.geometry_json or {},
            "properties": self.properties_json or {},
            "parent_id": self.parent_id,
            "source_ref": self.source_ref,
        }


class MapObjectLink(Base):
    __tablename__ = "map_object_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    object_id: Mapped[int] = mapped_column(Integer, ForeignKey("map_objects.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    task_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    qc_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    link_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    object: Mapped["MapObject"] = relationship("MapObject", back_populates="links")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "object_id": self.object_id,
            "asset_id": self.asset_id,
            "task_id": self.task_id,
            "qc_id": self.qc_id,
            "link_type": self.link_type,
            "note": self.note,
        }
