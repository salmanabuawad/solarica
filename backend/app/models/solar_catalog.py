"""
SQLAlchemy models for the real solar equipment catalog.
Mirrors solar_db_dump_real/schema.sql — loaded from official public sources:
  - NREL/SAM CEC Modules Library (16,199 PV modules)
  - California Energy Commission lists (inverters, batteries, meters, ESS, PCS)

Total: 28,470 device models, 607,830 specs, 527 manufacturers, 8 CVEs.
"""
from sqlalchemy import (
    BigInteger, Boolean, Column, Date, Double, ForeignKey,
    Integer, String, Text, Index
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class CatalogDataSource(Base):
    __tablename__ = "catalog_data_sources"

    id = Column(Integer, primary_key=True)
    source_code = Column(String(100), unique=True, nullable=False)
    name = Column(String(300), nullable=False)
    publisher = Column(String(200))
    source_url = Column(Text)
    retrieved_on = Column(Date)
    release_date = Column(Date)
    notes = Column(Text)

    devices = relationship("CatalogDevice", back_populates="source")

    def to_dict(self):
        return {
            "id": self.id,
            "source_code": self.source_code,
            "name": self.name,
            "publisher": self.publisher,
            "source_url": self.source_url,
            "retrieved_on": str(self.retrieved_on) if self.retrieved_on else None,
            "release_date": str(self.release_date) if self.release_date else None,
            "notes": self.notes,
        }


class CatalogCategory(Base):
    __tablename__ = "catalog_categories"

    id = Column(Integer, primary_key=True)
    category_code = Column(String(80), unique=True, nullable=False)
    category_name = Column(String(200), nullable=False)

    devices = relationship("CatalogDevice", back_populates="category")

    def to_dict(self):
        return {
            "id": self.id,
            "category_code": self.category_code,
            "category_name": self.category_name,
        }


class CatalogManufacturer(Base):
    __tablename__ = "catalog_manufacturers"

    id = Column(Integer, primary_key=True)
    manufacturer_name = Column(String(300), unique=True, nullable=False, index=True)

    devices = relationship("CatalogDevice", back_populates="manufacturer")

    def to_dict(self):
        return {"id": self.id, "manufacturer_name": self.manufacturer_name}


class CatalogDevice(Base):
    __tablename__ = "catalog_devices"

    id = Column(BigInteger, primary_key=True)
    category_id = Column(Integer, ForeignKey("catalog_categories.id"), nullable=False)
    source_id = Column(Integer, ForeignKey("catalog_data_sources.id"), nullable=False)
    manufacturer_id = Column(Integer, ForeignKey("catalog_manufacturers.id"), nullable=False)
    model_name = Column(String(400), nullable=False, index=True)
    brand_name = Column(String(200))
    technology = Column(String(100))
    description = Column(Text)
    source_release_date = Column(Date)
    source_last_update = Column(Date)
    is_hybrid = Column(Boolean)

    category = relationship("CatalogCategory", back_populates="devices")
    source = relationship("CatalogDataSource", back_populates="devices")
    manufacturer = relationship("CatalogManufacturer", back_populates="devices")
    specs = relationship("CatalogSpec", back_populates="device", cascade="all, delete-orphan")

    def to_dict(self, include_specs: bool = False):
        d = {
            "id": self.id,
            "category_code": self.category.category_code if self.category else None,
            "category_name": self.category.category_name if self.category else None,
            "manufacturer_name": self.manufacturer.manufacturer_name if self.manufacturer else None,
            "model_name": self.model_name,
            "brand_name": self.brand_name,
            "technology": self.technology,
            "description": self.description,
            "source_code": self.source.source_code if self.source else None,
            "source_release_date": str(self.source_release_date) if self.source_release_date else None,
            "source_last_update": str(self.source_last_update) if self.source_last_update else None,
            "is_hybrid": self.is_hybrid,
        }
        if include_specs:
            d["specs"] = [s.to_dict() for s in (self.specs or [])]
        return d


class CatalogSpec(Base):
    __tablename__ = "catalog_specs"

    id = Column(BigInteger, primary_key=True)
    device_id = Column(BigInteger, ForeignKey("catalog_devices.id", ondelete="CASCADE"), nullable=False)
    spec_group = Column(String(100), nullable=False)
    spec_key = Column(String(200), nullable=False)
    spec_value_text = Column(Text)
    spec_value_num = Column(Double)
    unit = Column(String(50))

    device = relationship("CatalogDevice", back_populates="specs")

    def to_dict(self):
        return {
            "id": self.id,
            "device_id": self.device_id,
            "spec_group": self.spec_group,
            "spec_key": self.spec_key,
            "spec_value_text": self.spec_value_text,
            "spec_value_num": self.spec_value_num,
            "unit": self.unit,
        }


class CatalogVulnerability(Base):
    __tablename__ = "catalog_vulnerabilities"

    id = Column(Integer, primary_key=True)
    cve_id = Column(String(30), index=True)
    advisory_id = Column(String(50), index=True)
    source_name = Column(String(200))
    title = Column(String(500), nullable=False)
    severity = Column(String(20))
    cvss_v3 = Column(Double)
    published_date = Column(Date)
    description = Column(Text)
    affected_product = Column(String(300))

    matches = relationship("CatalogVulnMatch", back_populates="vulnerability", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "cve_id": self.cve_id,
            "advisory_id": self.advisory_id,
            "source_name": self.source_name,
            "title": self.title,
            "severity": self.severity,
            "cvss_v3": self.cvss_v3,
            "published_date": str(self.published_date) if self.published_date else None,
            "description": self.description,
            "affected_product": self.affected_product,
        }


class CatalogVulnMatch(Base):
    """Pattern-based vulnerability matching (manufacturer ILIKE + model ILIKE)."""
    __tablename__ = "catalog_vuln_matches"

    id = Column(Integer, primary_key=True)
    vulnerability_id = Column(Integer, ForeignKey("catalog_vulnerabilities.id", ondelete="CASCADE"), nullable=False)
    manufacturer_pattern = Column(String(300))
    model_pattern = Column(String(300))
    notes = Column(Text)

    vulnerability = relationship("CatalogVulnerability", back_populates="matches")

    def to_dict(self):
        return {
            "id": self.id,
            "vulnerability_id": self.vulnerability_id,
            "manufacturer_pattern": self.manufacturer_pattern,
            "model_pattern": self.model_pattern,
            "notes": self.notes,
        }


# ── Indexes (additional, beyond primary keys) ─────────────────────────────────

Index("idx_catalog_devices_category", CatalogDevice.category_id)
Index("idx_catalog_devices_manufacturer", CatalogDevice.manufacturer_id)
Index("idx_catalog_specs_device", CatalogSpec.device_id)
Index("idx_catalog_specs_key", CatalogSpec.spec_key)
Index("idx_catalog_specs_group", CatalogSpec.spec_group)
Index("idx_catalog_vulns_cve", CatalogVulnerability.cve_id)
