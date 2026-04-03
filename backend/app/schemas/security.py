from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class DeviceCreate(BaseModel):
    project_id: str
    device_name: str
    device_type: str  # inverter, meter, gateway, scada, plc, rtu, sensor, camera, router, switch
    manufacturer: str
    model: str
    firmware_version: Optional[str] = None
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None
    protocol: Optional[str] = None  # modbus, sunspec, mqtt, opcua, bacnet, dnp3, iec61850
    network_zone: Optional[str] = None  # ot_field, ot_control, dmz, it_corporate
    location: Optional[str] = None
    wireless_interfaces: Optional[list[str]] = None  # wifi, bluetooth, zigbee, lora, cellular
    notes: Optional[str] = None


class DeviceRead(DeviceCreate):
    id: str
    status: str  # active, inactive, decommissioned
    last_scan_date: Optional[str] = None
    vulnerability_count: int = 0
    risk_score: Optional[float] = None
    created_at: str


class VulnerabilityRead(BaseModel):
    id: str
    device_id: str
    device_name: str
    severity: str  # critical, high, medium, low, informational
    category: str  # firmware, authentication, encryption, protocol, network, configuration, physical, supply_chain
    title: str
    description: str
    cve_id: Optional[str] = None
    cvss_score: Optional[float] = None
    affected_component: str
    remediation: str
    status: str  # open, in_progress, mitigated, accepted, false_positive
    detected_date: str
    due_date: Optional[str] = None


class SecurityScanRequest(BaseModel):
    project_id: str
    scan_type: str = "full"  # full, firmware, network, configuration, protocol


class SecurityScanResult(BaseModel):
    scan_id: str
    project_id: str
    scan_type: str
    status: str
    devices_scanned: int
    vulnerabilities_found: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    summary: str
    findings: list[VulnerabilityRead]


class SecurityDashboard(BaseModel):
    total_devices: int
    total_vulnerabilities: int
    critical_vulnerabilities: int
    high_vulnerabilities: int
    devices_at_risk: int
    compliance_score: float
    last_scan_date: Optional[str] = None
    top_risks: list[VulnerabilityRead]
    vulnerability_by_category: dict[str, int]
    vulnerability_by_severity: dict[str, int]
