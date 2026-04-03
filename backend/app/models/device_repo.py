"""
SQLAlchemy models for the device inventory repository.
Mirrors the device_repo/device_repository/schema.sql schema.
"""
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, ForeignKey
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class DeviceSite(Base):
    __tablename__ = "device_sites"

    id = Column(Integer, primary_key=True, index=True)
    site_name = Column(String(200), unique=True, nullable=False)
    country = Column(String(100))
    region = Column(String(100))
    source_notes = Column(Text)

    devices = relationship("DeviceInventory", back_populates="site", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "site_name": self.site_name,
            "country": self.country,
            "region": self.region,
            "source_notes": self.source_notes,
            "device_count": len(self.devices) if self.devices is not None else 0,
        }


class DeviceInventory(Base):
    __tablename__ = "device_inventory"

    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(Integer, ForeignKey("device_sites.id"), nullable=False)
    area = Column(String(200))
    category = Column(String(100), nullable=False)
    manufacturer = Column(String(200))
    model_raw = Column(String(300))
    model_normalized = Column(String(300))
    quantity = Column(Integer)
    unit = Column(String(20), default="ea")
    is_exact_model_confirmed = Column(Boolean, default=False)
    role = Column(String(200))
    source_notes = Column(Text)

    site = relationship("DeviceSite", back_populates="devices")
    specs = relationship("DeviceSpec", back_populates="device", cascade="all, delete-orphan")
    vuln_links = relationship("DeviceVulnLink", back_populates="device", cascade="all, delete-orphan")

    def to_dict(self, include_specs: bool = False, include_vulns: bool = False):
        d = {
            "id": self.id,
            "site_id": self.site_id,
            "site_name": self.site.site_name if self.site else None,
            "area": self.area,
            "category": self.category,
            "manufacturer": self.manufacturer,
            "model_raw": self.model_raw,
            "model_normalized": self.model_normalized,
            "quantity": self.quantity,
            "unit": self.unit,
            "is_exact_model_confirmed": bool(self.is_exact_model_confirmed),
            "role": self.role,
            "source_notes": self.source_notes,
            "vuln_count": len(self.vuln_links) if self.vuln_links is not None else 0,
        }
        if include_specs:
            d["specs"] = [s.to_dict() for s in (self.specs or [])]
        if include_vulns:
            d["vulnerabilities"] = [
                lnk.vuln.to_dict() for lnk in (self.vuln_links or []) if lnk.vuln
            ]
        return d


class DeviceSpec(Base):
    __tablename__ = "device_specs"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("device_inventory.id"), nullable=False)
    spec_key = Column(String(200), nullable=False)
    spec_value = Column(String(500), nullable=False)
    source_note = Column(String(500))

    device = relationship("DeviceInventory", back_populates="specs")

    def to_dict(self):
        return {
            "id": self.id,
            "device_id": self.device_id,
            "spec_key": self.spec_key,
            "spec_value": self.spec_value,
            "source_note": self.source_note,
        }


class DeviceCVE(Base):
    """Known CVEs that may affect devices in the repository."""
    __tablename__ = "device_cves"

    id = Column(Integer, primary_key=True, index=True)
    manufacturer = Column(String(200))
    product_scope = Column(String(300), nullable=False)
    cve_id = Column(String(30), unique=True, index=True)
    title = Column(String(500), nullable=False)
    severity = Column(String(20))          # Critical, High, Medium, Low
    affected_versions = Column(String(200))
    fixed_versions = Column(String(200))
    advisory_source = Column(String(300))
    applicability = Column(String(100), nullable=False)
    notes = Column(Text)

    device_links = relationship("DeviceVulnLink", back_populates="vuln", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "manufacturer": self.manufacturer,
            "product_scope": self.product_scope,
            "cve_id": self.cve_id,
            "title": self.title,
            "severity": self.severity,
            "affected_versions": self.affected_versions,
            "fixed_versions": self.fixed_versions,
            "advisory_source": self.advisory_source,
            "applicability": self.applicability,
            "notes": self.notes,
            "affected_device_count": len(self.device_links) if self.device_links is not None else 0,
        }


class DeviceVulnLink(Base):
    """Junction table: which CVEs affect which devices."""
    __tablename__ = "device_vuln_links"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("device_inventory.id"), nullable=False)
    vuln_id = Column(Integer, ForeignKey("device_cves.id"), nullable=False)
    relationship_type = Column(String(50), nullable=False)  # direct, adjacent, indirect

    device = relationship("DeviceInventory", back_populates="vuln_links")
    vuln = relationship("DeviceCVE", back_populates="device_links")

    def to_dict(self):
        return {
            "id": self.id,
            "device_id": self.device_id,
            "vuln_id": self.vuln_id,
            "cve_id": self.vuln.cve_id if self.vuln else None,
            "title": self.vuln.title if self.vuln else None,
            "severity": self.vuln.severity if self.vuln else None,
            "relationship_type": self.relationship_type,
        }
