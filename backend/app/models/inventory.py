from datetime import datetime
from sqlalchemy import String, DateTime, Numeric, Text, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Material(Base):
    __tablename__ = "materials"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    sku: Mapped[str | None] = mapped_column(String(100), nullable=True)
    min_threshold: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False, default=0)
    unit_cost: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "unit": self.unit,
            "sku": self.sku,
            "min_threshold": float(self.min_threshold),
            "unit_cost": float(self.unit_cost) if self.unit_cost is not None else None,
        }


class Warehouse(Base):
    __tablename__ = "warehouses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    manager_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    stock: Mapped[list["WarehouseStock"]] = relationship(
        "WarehouseStock", back_populates="warehouse", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "name": self.name,
            "location": self.location,
            "manager_name": self.manager_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class WarehouseStock(Base):
    __tablename__ = "warehouse_stock"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id", ondelete="CASCADE"), nullable=False)
    quantity_available: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False, default=0)
    quantity_reserved: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False, default=0)
    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    warehouse: Mapped["Warehouse"] = relationship("Warehouse", back_populates="stock")
    material: Mapped["Material"] = relationship("Material")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "warehouse_id": self.warehouse_id,
            "material_id": self.material_id,
            "material_name": self.material.name if self.material else None,
            "quantity_available": float(self.quantity_available),
            "quantity_reserved": float(self.quantity_reserved),
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
        }


class MaterialIssueTransaction(Base):
    __tablename__ = "material_issue_transactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("maintenance_tasks.id", ondelete="SET NULL"), nullable=True)
    issued_to_user: Mapped[str | None] = mapped_column(String(255), nullable=True)
    issued_by_user: Mapped[str | None] = mapped_column(String(255), nullable=True)
    site_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    asset_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    asset_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="issued")
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expected_usage_by_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    items: Mapped[list["MaterialIssueItem"]] = relationship(
        "MaterialIssueItem", back_populates="transaction", cascade="all, delete-orphan"
    )
    variance_flags: Mapped[list["InventoryVarianceFlag"]] = relationship(
        "InventoryVarianceFlag", back_populates="transaction", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "warehouse_id": self.warehouse_id,
            "task_id": self.task_id,
            "issued_to_user": self.issued_to_user,
            "issued_by_user": self.issued_by_user,
            "site_name": self.site_name,
            "asset_type": self.asset_type,
            "asset_ref": self.asset_ref,
            "status": self.status,
            "issued_at": self.issued_at.isoformat() if self.issued_at else None,
            "expected_usage_by_date": self.expected_usage_by_date.isoformat() if self.expected_usage_by_date else None,
            "notes": self.notes,
            "items": [i.to_dict() for i in self.items],
            "red_flags": [f.to_dict() for f in self.variance_flags],
        }


class MaterialIssueItem(Base):
    __tablename__ = "material_issue_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("material_issue_transactions.id", ondelete="CASCADE"), nullable=False)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id", ondelete="CASCADE"), nullable=False)
    quantity_issued: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False, default=0)
    quantity_returned: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False, default=0)
    quantity_consumed: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False, default=0)
    quantity_missing: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False, default=0)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)

    transaction: Mapped["MaterialIssueTransaction"] = relationship("MaterialIssueTransaction", back_populates="items")
    material: Mapped["Material"] = relationship("Material")

    def to_dict(self) -> dict:
        return {
            "material_id": self.material_id,
            "material_name": self.material.name if self.material else None,
            "quantity_issued": float(self.quantity_issued),
            "quantity_returned": float(self.quantity_returned),
            "quantity_consumed": float(self.quantity_consumed),
            "quantity_missing": float(self.quantity_missing),
            "unit": self.unit,
        }


class InventoryVarianceFlag(Base):
    __tablename__ = "inventory_variance_flags"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("material_issue_transactions.id", ondelete="CASCADE"), nullable=False)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id", ondelete="CASCADE"), nullable=False)
    expected_quantity: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False)
    actual_quantity: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False)
    variance_quantity: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False)
    severity: Mapped[str] = mapped_column(String(50), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="open")
    reviewed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    transaction: Mapped["MaterialIssueTransaction"] = relationship("MaterialIssueTransaction", back_populates="variance_flags")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "transaction_id": self.transaction_id,
            "material_id": self.material_id,
            "expected_quantity": float(self.expected_quantity),
            "actual_quantity": float(self.actual_quantity),
            "variance_quantity": float(self.variance_quantity),
            "rule_type": "variance",
            "severity": self.severity,
            "description": self.reason or "Inventory variance detected",
            "status": self.status,
            "reviewed_by": self.reviewed_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }
