from sqlalchemy import Column, Integer, String, Boolean, UniqueConstraint
from app.core.database import Base


class FieldConfig(Base):
    __tablename__ = "field_configurations"

    id           = Column(Integer, primary_key=True)
    grid_name    = Column(String(100), nullable=False)
    field_name   = Column(String(100), nullable=False)
    visible      = Column(Boolean, nullable=False, default=True)
    width        = Column(Integer, nullable=True)
    column_order = Column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint("grid_name", "field_name", name="uq_field_config_grid_field"),
    )

    def to_dict(self) -> dict:
        return {
            "id":           self.id,
            "grid_name":    self.grid_name,
            "field_name":   self.field_name,
            "visible":      self.visible,
            "width":        self.width,
            "column_order": self.column_order,
        }
