from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Numeric, ForeignKey, Text
from app.core.db import Base

class InventoryItem(Base):
    __tablename__ = "inventory_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    sku: Mapped[str] = mapped_column(String(100))
    item_name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    uom: Mapped[str] = mapped_column(String(30))
    reorder_level: Mapped[float | None] = mapped_column(Numeric(12,2), nullable=True)

class InventoryTransaction(Base):
    __tablename__ = "inventory_transactions"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    inventory_item_id: Mapped[int] = mapped_column(ForeignKey("inventory_items.id", ondelete="CASCADE"))
    txn_type: Mapped[str] = mapped_column(String(30))
    quantity: Mapped[float] = mapped_column(Numeric(12,2))
    reference_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reference_id: Mapped[int | None] = mapped_column(nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
