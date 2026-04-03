from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class Measurement(Base):
    __tablename__ = "measurements"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    string_id: Mapped[int | None] = mapped_column(ForeignKey("strings.id", ondelete="SET NULL"), nullable=True)
    source_file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    device_serial: Mapped[str | None] = mapped_column(String(255), nullable=True)
    site_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    string_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    module_part_number: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def to_dict(self) -> dict:
        payload = self.payload_json or {}
        records = payload.get("records", [])
        return {
            "id": self.id,
            "project_id": self.project_id,
            "string_id": self.string_id,
            "file_name": self.source_file_name,
            "device_serial": self.device_serial or payload.get("device_serial"),
            "site_label": self.site_label or payload.get("site_label"),
            "string_label": self.string_label or payload.get("string_label"),
            "module_part_number": self.module_part_number or payload.get("module_part_number"),
            "records": records,
            "record_count": len(records),
            "uploaded_at": self.created_at.isoformat() if self.created_at else None,
            # Key metrics from first record if available
            "pmax_w": records[0].get("pmax_w") if records else None,
            "voc_v": records[0].get("voc_v") if records else None,
            "isc_a": records[0].get("isc_a") if records else None,
        }
