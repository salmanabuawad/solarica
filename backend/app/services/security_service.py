from datetime import datetime, timedelta
import uuid
from typing import Optional


# Known firmware vulnerability database (simulated CVE correlation)
KNOWN_FIRMWARE_CVES: dict[str, list[dict]] = {
    "solaredge": [
        {"cve": "CVE-2023-23333", "cvss": 9.8, "affected_versions": ["<3.2.7"], "title": "SolarEdge Inverter Remote Code Execution", "severity": "critical"},
        {"cve": "CVE-2024-21762", "cvss": 7.2, "affected_versions": ["<4.0.1"], "title": "SolarEdge Communication Board Authentication Bypass", "severity": "high"},
    ],
    "sma": [
        {"cve": "CVE-2023-40043", "cvss": 8.6, "affected_versions": ["<3.10.18"], "title": "SMA Sunny Boy Web Interface CSRF", "severity": "high"},
        {"cve": "CVE-2024-30291", "cvss": 6.1, "affected_versions": ["<2.5.4"], "title": "SMA Data Manager Information Disclosure", "severity": "medium"},
    ],
    "huawei": [
        {"cve": "CVE-2023-52364", "cvss": 8.1, "affected_versions": ["<V100R001C30"], "title": "Huawei SmartLogger Unauthorized Command Execution", "severity": "high"},
    ],
    "enphase": [
        {"cve": "CVE-2024-43199", "cvss": 7.5, "affected_versions": ["<7.0.1"], "title": "Enphase IQ Gateway Authentication Weakness", "severity": "high"},
    ],
    "fronius": [
        {"cve": "CVE-2023-31413", "cvss": 6.5, "affected_versions": ["<1.28.7"], "title": "Fronius Symo Web Interface Stored XSS", "severity": "medium"},
    ],
}

# Wireless protocol risk database
WIRELESS_RISKS: dict[str, dict] = {
    "wifi_open": {"severity": "critical", "cvss": 9.3, "title": "Open WiFi Network Detected on OT Device", "category": "wireless"},
    "wifi_wep": {"severity": "critical", "cvss": 9.0, "title": "WEP Encryption on Device WiFi (Trivially Breakable)", "category": "wireless"},
    "wifi_wpa": {"severity": "high", "cvss": 7.2, "title": "WPA (v1) Encryption on Device WiFi — Upgrade to WPA3", "category": "wireless"},
    "bluetooth_discoverable": {"severity": "high", "cvss": 7.8, "title": "Bluetooth Interface Discoverable and Unsecured", "category": "wireless"},
    "zigbee_unencrypted": {"severity": "high", "cvss": 7.0, "title": "ZigBee Communication Without Network Key Encryption", "category": "wireless"},
    "lora_no_auth": {"severity": "medium", "cvss": 5.5, "title": "LoRa/LoRaWAN Device Without Application-Layer Authentication", "category": "wireless"},
    "cellular_default_apn": {"severity": "medium", "cvss": 5.0, "title": "Cellular Modem Using Default APN Configuration", "category": "wireless"},
}


class SecurityService:
    def __init__(self):
        self._devices: dict[str, dict] = {}
        self._vulnerabilities: dict[str, dict] = {}
        self._scans: dict[str, dict] = {}
        self._firmware_alerts: dict[str, dict] = {}
        self._remediation_tasks: list[dict] = []

    def register_device(self, payload) -> dict:
        """Register a new device for security monitoring"""
        device_id = str(uuid.uuid4())[:8]
        device = {
            "id": device_id,
            **payload.model_dump(),
            "status": "active",
            "last_scan_date": None,
            "vulnerability_count": 0,
            "risk_score": 0.0,
            "created_at": datetime.utcnow().isoformat(),
        }
        self._devices[device_id] = device
        return device

    def list_devices(self, project_id: Optional[str] = None) -> list:
        devices = list(self._devices.values())
        if project_id:
            devices = [d for d in devices if d["project_id"] == project_id]
        return devices

    def get_device(self, device_id: str) -> Optional[dict]:
        return self._devices.get(device_id)

    def run_security_scan(self, payload) -> dict:
        """Run a simulated security scan that generates realistic vulnerability findings"""
        scan_id = str(uuid.uuid4())[:8]
        project_devices = [
            d for d in self._devices.values() if d["project_id"] == payload.project_id
        ]

        findings = []
        for device in project_devices:
            device_vulns = self._generate_vulnerabilities(device, payload.scan_type)
            for vuln in device_vulns:
                vuln_id = str(uuid.uuid4())[:8]
                vuln_record = {
                    "id": vuln_id,
                    "device_id": device["id"],
                    "device_name": device["device_name"],
                    **vuln,
                }
                self._vulnerabilities[vuln_id] = vuln_record
                findings.append(vuln_record)
            device["last_scan_date"] = datetime.utcnow().isoformat()
            device["vulnerability_count"] = len(
                [
                    v
                    for v in self._vulnerabilities.values()
                    if v["device_id"] == device["id"] and v["status"] == "open"
                ]
            )
            device["risk_score"] = self._calculate_risk_score(device["id"])

        critical = len([f for f in findings if f["severity"] == "critical"])
        high = len([f for f in findings if f["severity"] == "high"])
        medium = len([f for f in findings if f["severity"] == "medium"])
        low = len([f for f in findings if f["severity"] == "low"])

        scan_result = {
            "scan_id": scan_id,
            "project_id": payload.project_id,
            "scan_type": payload.scan_type,
            "status": "completed",
            "devices_scanned": len(project_devices),
            "vulnerabilities_found": len(findings),
            "critical_count": critical,
            "high_count": high,
            "medium_count": medium,
            "low_count": low,
            "summary": f"Scanned {len(project_devices)} devices. Found {len(findings)} vulnerabilities ({critical} critical, {high} high).",
            "findings": findings,
        }
        self._scans[scan_id] = scan_result
        return scan_result

    def _generate_vulnerabilities(self, device: dict, scan_type: str) -> list:
        """Generate realistic vulnerability findings based on device type and scan type"""
        vulns = []
        now = datetime.utcnow()

        # Firmware vulnerabilities
        if scan_type in ("full", "firmware"):
            if not device.get("firmware_version") or device["firmware_version"] == "unknown":
                vulns.append(
                    {
                        "severity": "high",
                        "category": "firmware",
                        "title": "Unknown or Unverified Firmware Version",
                        "description": f"Device {device['device_name']} has no verified firmware version. Cannot assess patch status.",
                        "cve_id": None,
                        "cvss_score": 7.5,
                        "affected_component": "firmware",
                        "remediation": "Verify firmware version and update to latest manufacturer-recommended version.",
                        "status": "open",
                        "detected_date": now.isoformat(),
                        "due_date": (now + timedelta(days=30)).isoformat(),
                    }
                )

            if device["device_type"] == "inverter":
                vulns.append(
                    {
                        "severity": "medium",
                        "category": "firmware",
                        "title": "Inverter Firmware Update Available",
                        "description": f"Inverter {device['device_name']} ({device['manufacturer']} {device['model']}) may have outdated firmware with known security patches.",
                        "cve_id": "CVE-2024-SOLAR-001",
                        "cvss_score": 5.3,
                        "affected_component": "inverter_firmware",
                        "remediation": "Check manufacturer portal for latest firmware. Schedule maintenance window for update.",
                        "status": "open",
                        "detected_date": now.isoformat(),
                        "due_date": (now + timedelta(days=60)).isoformat(),
                    }
                )

        # Network vulnerabilities
        if scan_type in ("full", "network"):
            if device.get("ip_address") and device.get("network_zone") != "ot_field":
                vulns.append(
                    {
                        "severity": "high",
                        "category": "network",
                        "title": "OT Device Accessible from Non-Field Network",
                        "description": f"Device {device['device_name']} with IP {device['ip_address']} is in network zone '{device.get('network_zone', 'unknown')}' instead of isolated OT field network.",
                        "cve_id": None,
                        "cvss_score": 8.1,
                        "affected_component": "network_segmentation",
                        "remediation": "Move device to isolated OT field network segment. Implement firewall rules per IEC 62443.",
                        "status": "open",
                        "detected_date": now.isoformat(),
                        "due_date": (now + timedelta(days=14)).isoformat(),
                    }
                )

            if device["device_type"] in ("gateway", "router", "switch"):
                vulns.append(
                    {
                        "severity": "critical",
                        "category": "network",
                        "title": "Network Infrastructure Device Requires Security Audit",
                        "description": f"Network device {device['device_name']} ({device['device_type']}) requires security configuration audit for ACLs, unused ports, and management protocols.",
                        "cve_id": None,
                        "cvss_score": 9.1,
                        "affected_component": "network_configuration",
                        "remediation": "Conduct full security audit. Disable unused ports. Implement strict ACLs. Use encrypted management protocols only.",
                        "status": "open",
                        "detected_date": now.isoformat(),
                        "due_date": (now + timedelta(days=7)).isoformat(),
                    }
                )

        # Authentication vulnerabilities
        if scan_type in ("full", "configuration"):
            if device["device_type"] in ("scada", "plc", "rtu", "gateway"):
                vulns.append(
                    {
                        "severity": "critical",
                        "category": "authentication",
                        "title": "Default Credentials May Be Active",
                        "description": f"Control system device {device['device_name']} ({device['device_type']}) should be verified for default credential usage.",
                        "cve_id": None,
                        "cvss_score": 9.8,
                        "affected_component": "authentication",
                        "remediation": "Change all default passwords. Implement multi-factor authentication where supported. Document credential management procedures.",
                        "status": "open",
                        "detected_date": now.isoformat(),
                        "due_date": (now + timedelta(days=3)).isoformat(),
                    }
                )

        # Protocol vulnerabilities
        if scan_type in ("full", "protocol"):
            if device.get("protocol") in ("modbus", "dnp3", "bacnet"):
                vulns.append(
                    {
                        "severity": "high",
                        "category": "protocol",
                        "title": f"Unencrypted {device.get('protocol', '').upper()} Protocol in Use",
                        "description": f"Device {device['device_name']} uses {device.get('protocol', '').upper()} protocol which lacks native encryption and authentication.",
                        "cve_id": None,
                        "cvss_score": 7.4,
                        "affected_component": f"protocol_{device.get('protocol', '')}",
                        "remediation": f"Implement VPN/TLS wrapper for {device.get('protocol', '').upper()} traffic. Consider migration to secure protocol variant. Apply network segmentation as compensating control.",
                        "status": "open",
                        "detected_date": now.isoformat(),
                        "due_date": (now + timedelta(days=30)).isoformat(),
                    }
                )

            if device.get("protocol") == "mqtt":
                vulns.append(
                    {
                        "severity": "medium",
                        "category": "protocol",
                        "title": "MQTT Broker Security Configuration Required",
                        "description": f"Device {device['device_name']} uses MQTT. Verify TLS encryption and authentication on MQTT broker.",
                        "cve_id": None,
                        "cvss_score": 6.5,
                        "affected_component": "mqtt_broker",
                        "remediation": "Enable TLS on MQTT broker. Require client certificates. Implement topic-level ACLs.",
                        "status": "open",
                        "detected_date": now.isoformat(),
                        "due_date": (now + timedelta(days=30)).isoformat(),
                    }
                )

        # Encryption vulnerabilities
        if scan_type in ("full", "configuration"):
            if device["device_type"] in ("camera", "sensor"):
                vulns.append(
                    {
                        "severity": "medium",
                        "category": "encryption",
                        "title": "Data-at-Rest Encryption Not Verified",
                        "description": f"IoT device {device['device_name']} ({device['device_type']}) data-at-rest encryption status unknown.",
                        "cve_id": None,
                        "cvss_score": 5.5,
                        "affected_component": "data_storage",
                        "remediation": "Verify device supports and has enabled data encryption at rest. If not supported, ensure network isolation.",
                        "status": "open",
                        "detected_date": now.isoformat(),
                        "due_date": (now + timedelta(days=45)).isoformat(),
                    }
                )

        # ── Firmware Intelligence (CVE correlation) ───────────────
        if scan_type in ("full", "firmware"):
            manufacturer_key = device.get("manufacturer", "").lower().strip()
            known_cves = KNOWN_FIRMWARE_CVES.get(manufacturer_key, [])
            for cve_entry in known_cves:
                vulns.append(
                    {
                        "severity": cve_entry["severity"],
                        "category": "firmware",
                        "title": cve_entry["title"],
                        "description": (
                            f"Known vulnerability {cve_entry['cve']} affects {device['manufacturer']} "
                            f"devices with firmware versions {', '.join(cve_entry['affected_versions'])}. "
                            f"Current firmware: {device.get('firmware_version', 'unknown')}. "
                            f"Verify if this device is affected."
                        ),
                        "cve_id": cve_entry["cve"],
                        "cvss_score": cve_entry["cvss"],
                        "affected_component": "firmware",
                        "remediation": (
                            f"Check {device['manufacturer']} security advisories for {cve_entry['cve']}. "
                            f"Update firmware to a version not listed in affected range: {', '.join(cve_entry['affected_versions'])}."
                        ),
                        "status": "open",
                        "detected_date": now.isoformat(),
                        "due_date": (now + timedelta(days=14 if cve_entry["severity"] == "critical" else 30)).isoformat(),
                    }
                )

        # ── Wireless Security Checks ──────────────────────────────
        if scan_type in ("full", "network"):
            wireless_interfaces = device.get("wireless_interfaces", [])
            # Also infer wireless from device type
            if device["device_type"] in ("gateway", "router", "sensor", "camera"):
                if not wireless_interfaces:
                    wireless_interfaces = ["wifi"]  # Assume WiFi capable

            for iface in wireless_interfaces:
                iface_lower = iface.lower()
                if "wifi" in iface_lower or "wi-fi" in iface_lower:
                    risk = WIRELESS_RISKS.get("wifi_wpa", {})
                    vulns.append(
                        {
                            "severity": risk.get("severity", "high"),
                            "category": "wireless",
                            "title": f"WiFi Interface Active on {device['device_name']}",
                            "description": (
                                f"Device {device['device_name']} has an active WiFi interface. "
                                f"Verify WPA3 encryption is enabled and WiFi is on a separate VLAN from OT network. "
                                f"Disable WiFi if not operationally required."
                            ),
                            "cve_id": None,
                            "cvss_score": risk.get("cvss", 7.2),
                            "affected_component": "wifi_interface",
                            "remediation": (
                                "1. Verify WPA3 encryption is configured. "
                                "2. Change default SSID and credentials. "
                                "3. Isolate WiFi on separate VLAN. "
                                "4. Disable WiFi if not required for operation."
                            ),
                            "status": "open",
                            "detected_date": now.isoformat(),
                            "due_date": (now + timedelta(days=14)).isoformat(),
                        }
                    )
                elif "bluetooth" in iface_lower or "ble" in iface_lower:
                    risk = WIRELESS_RISKS.get("bluetooth_discoverable", {})
                    vulns.append(
                        {
                            "severity": risk.get("severity", "high"),
                            "category": "wireless",
                            "title": f"Bluetooth Interface on {device['device_name']}",
                            "description": (
                                f"Device {device['device_name']} has Bluetooth capability. "
                                f"Verify pairing is secured and discoverable mode is disabled."
                            ),
                            "cve_id": None,
                            "cvss_score": risk.get("cvss", 7.8),
                            "affected_component": "bluetooth_interface",
                            "remediation": (
                                "1. Disable discoverable mode. "
                                "2. Require secure pairing (PIN/passkey). "
                                "3. Disable Bluetooth if not required."
                            ),
                            "status": "open",
                            "detected_date": now.isoformat(),
                            "due_date": (now + timedelta(days=14)).isoformat(),
                        }
                    )
                elif "zigbee" in iface_lower:
                    risk = WIRELESS_RISKS.get("zigbee_unencrypted", {})
                    vulns.append(
                        {
                            "severity": risk.get("severity", "high"),
                            "category": "wireless",
                            "title": f"ZigBee Interface on {device['device_name']}",
                            "description": f"Verify ZigBee network key encryption is enabled on {device['device_name']}.",
                            "cve_id": None,
                            "cvss_score": risk.get("cvss", 7.0),
                            "affected_component": "zigbee_interface",
                            "remediation": "Enable AES-128 network key encryption. Rotate network keys periodically.",
                            "status": "open",
                            "detected_date": now.isoformat(),
                            "due_date": (now + timedelta(days=21)).isoformat(),
                        }
                    )
                elif "lora" in iface_lower:
                    risk = WIRELESS_RISKS.get("lora_no_auth", {})
                    vulns.append(
                        {
                            "severity": risk.get("severity", "medium"),
                            "category": "wireless",
                            "title": f"LoRa/LoRaWAN Interface on {device['device_name']}",
                            "description": f"Verify application-layer authentication on LoRaWAN device {device['device_name']}.",
                            "cve_id": None,
                            "cvss_score": risk.get("cvss", 5.5),
                            "affected_component": "lora_interface",
                            "remediation": "Enable OTAA (Over-The-Air Activation). Use unique AppKeys per device.",
                            "status": "open",
                            "detected_date": now.isoformat(),
                            "due_date": (now + timedelta(days=30)).isoformat(),
                        }
                    )

            # Cellular modem check for gateways/routers
            if device["device_type"] in ("gateway", "router") and device.get("protocol") in ("cellular", "4g", "5g", "lte"):
                risk = WIRELESS_RISKS.get("cellular_default_apn", {})
                vulns.append(
                    {
                        "severity": risk.get("severity", "medium"),
                        "category": "wireless",
                        "title": f"Cellular Modem on {device['device_name']}",
                        "description": f"Gateway {device['device_name']} uses cellular connectivity. Verify private APN and VPN configuration.",
                        "cve_id": None,
                        "cvss_score": risk.get("cvss", 5.0),
                        "affected_component": "cellular_modem",
                        "remediation": "Use private APN. Configure VPN tunnel to SCADA center. Disable SMS management interface.",
                        "status": "open",
                        "detected_date": now.isoformat(),
                        "due_date": (now + timedelta(days=30)).isoformat(),
                    }
                )

        # ── Supply Chain Risk ─────────────────────────────────────
        if scan_type in ("full", "configuration"):
            high_risk_origins = ["unknown", "unverified"]
            if device.get("manufacturer", "").lower() in high_risk_origins:
                vulns.append(
                    {
                        "severity": "high",
                        "category": "supply_chain",
                        "title": f"Unverified Manufacturer for {device['device_name']}",
                        "description": f"Device {device['device_name']} has manufacturer listed as '{device.get('manufacturer')}'. Supply chain provenance cannot be verified.",
                        "cve_id": None,
                        "cvss_score": 7.0,
                        "affected_component": "supply_chain",
                        "remediation": "Verify device provenance. Obtain manufacturer certificates. Consider replacement with verified equipment.",
                        "status": "open",
                        "detected_date": now.isoformat(),
                        "due_date": (now + timedelta(days=14)).isoformat(),
                    }
                )

        return vulns

    def _calculate_risk_score(self, device_id: str) -> float:
        device_vulns = [
            v
            for v in self._vulnerabilities.values()
            if v["device_id"] == device_id and v["status"] == "open"
        ]
        if not device_vulns:
            return 0.0
        scores = {"critical": 10, "high": 7.5, "medium": 5, "low": 2.5, "informational": 1}
        total = sum(scores.get(v["severity"], 0) for v in device_vulns)
        return min(round(total / len(device_vulns) * (1 + len(device_vulns) * 0.1), 1), 10.0)

    def list_vulnerabilities(
        self,
        project_id: Optional[str] = None,
        severity: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list:
        vulns = list(self._vulnerabilities.values())
        if project_id:
            project_device_ids = {
                d["id"] for d in self._devices.values() if d["project_id"] == project_id
            }
            vulns = [v for v in vulns if v["device_id"] in project_device_ids]
        if severity:
            vulns = [v for v in vulns if v["severity"] == severity]
        if status:
            vulns = [v for v in vulns if v["status"] == status]
        return vulns

    def update_vulnerability_status(
        self, vuln_id: str, new_status: str, notes: Optional[str] = None
    ) -> Optional[dict]:
        vuln = self._vulnerabilities.get(vuln_id)
        if not vuln:
            return None
        vuln["status"] = new_status
        # Recalculate risk score
        device = self._devices.get(vuln["device_id"])
        if device:
            device["vulnerability_count"] = len(
                [
                    v
                    for v in self._vulnerabilities.values()
                    if v["device_id"] == device["id"] and v["status"] == "open"
                ]
            )
            device["risk_score"] = self._calculate_risk_score(device["id"])
        return vuln

    def get_dashboard(self, project_id: Optional[str] = None) -> dict:
        devices = self.list_devices(project_id)
        vulns = self.list_vulnerabilities(project_id)
        open_vulns = [v for v in vulns if v["status"] == "open"]

        by_category = {}
        by_severity = {}
        for v in open_vulns:
            by_category[v["category"]] = by_category.get(v["category"], 0) + 1
            by_severity[v["severity"]] = by_severity.get(v["severity"], 0) + 1

        critical_vulns = [v for v in open_vulns if v["severity"] == "critical"]
        high_vulns = [v for v in open_vulns if v["severity"] == "high"]

        total_possible = max(len(devices) * 10, 1)
        total_risk = sum(d.get("risk_score", 0) for d in devices)
        compliance = max(0, round((1 - total_risk / total_possible) * 100, 1))

        return {
            "total_devices": len(devices),
            "total_vulnerabilities": len(open_vulns),
            "critical_vulnerabilities": len(critical_vulns),
            "high_vulnerabilities": len(high_vulns),
            "devices_at_risk": len([d for d in devices if d.get("risk_score", 0) > 3]),
            "compliance_score": compliance,
            "last_scan_date": max(
                (d.get("last_scan_date") for d in devices if d.get("last_scan_date")),
                default=None,
            ),
            "top_risks": sorted(
                open_vulns, key=lambda v: v.get("cvss_score", 0), reverse=True
            )[:5],
            "vulnerability_by_category": by_category,
            "vulnerability_by_severity": by_severity,
        }


    # ── Firmware Intelligence ──────────────────────────────────────

    def check_firmware_updates(self, project_id: Optional[str] = None) -> list[dict]:
        """Check all devices for known firmware vulnerabilities and generate firmware alerts."""
        devices = self.list_devices(project_id)
        alerts = []
        now = datetime.utcnow()

        for device in devices:
            manufacturer_key = device.get("manufacturer", "").lower().strip()
            known_cves = KNOWN_FIRMWARE_CVES.get(manufacturer_key, [])
            firmware = device.get("firmware_version", "unknown")

            for cve in known_cves:
                alert_id = f"fw-{device['id']}-{cve['cve']}"
                if alert_id not in self._firmware_alerts:
                    alert = {
                        "id": alert_id,
                        "device_id": device["id"],
                        "device_name": device["device_name"],
                        "manufacturer": device.get("manufacturer"),
                        "model": device.get("model"),
                        "current_firmware": firmware,
                        "cve_id": cve["cve"],
                        "cvss_score": cve["cvss"],
                        "severity": cve["severity"],
                        "title": cve["title"],
                        "affected_versions": cve["affected_versions"],
                        "status": "open",
                        "detected_date": now.isoformat(),
                        "recommended_action": f"Update firmware on {device['device_name']} to address {cve['cve']}",
                    }
                    self._firmware_alerts[alert_id] = alert
                    alerts.append(alert)

                    # Auto-create remediation task
                    task = {
                        "id": f"task-{alert_id}",
                        "type": "firmware_update",
                        "device_id": device["id"],
                        "device_name": device["device_name"],
                        "project_id": device.get("project_id"),
                        "title": f"Firmware Update Required: {device['device_name']} — {cve['cve']}",
                        "description": (
                            f"Device {device['device_name']} ({device.get('manufacturer')} {device.get('model')}) "
                            f"has a known vulnerability {cve['cve']} (CVSS {cve['cvss']}). "
                            f"Current firmware: {firmware}. Affected versions: {', '.join(cve['affected_versions'])}. "
                            f"Update firmware to the latest manufacturer-recommended version."
                        ),
                        "priority": "critical" if cve["severity"] == "critical" else "high",
                        "status": "open",
                        "created_date": now.isoformat(),
                        "due_date": (now + timedelta(days=7 if cve["severity"] == "critical" else 14)).isoformat(),
                    }
                    self._remediation_tasks.append(task)

        return alerts

    def get_firmware_alerts(self, project_id: Optional[str] = None) -> list[dict]:
        """Get all firmware-related alerts."""
        alerts = list(self._firmware_alerts.values())
        if project_id:
            project_device_ids = {d["id"] for d in self._devices.values() if d["project_id"] == project_id}
            alerts = [a for a in alerts if a["device_id"] in project_device_ids]
        return sorted(alerts, key=lambda a: a.get("cvss_score", 0), reverse=True)

    def get_remediation_tasks(self, project_id: Optional[str] = None) -> list[dict]:
        """Get auto-generated remediation tasks."""
        tasks = self._remediation_tasks
        if project_id:
            tasks = [t for t in tasks if t.get("project_id") == project_id]
        return tasks

    def get_firmware_summary(self, project_id: Optional[str] = None) -> dict:
        """Get firmware intelligence summary."""
        devices = self.list_devices(project_id)
        alerts = self.get_firmware_alerts(project_id)

        # Categorize devices by firmware status
        unknown_firmware = [d for d in devices if not d.get("firmware_version") or d["firmware_version"] in ("unknown", "")]
        with_known_cves = set()
        for alert in alerts:
            with_known_cves.add(alert["device_id"])

        manufacturers = {}
        for d in devices:
            mfg = d.get("manufacturer", "Unknown")
            manufacturers.setdefault(mfg, {"total": 0, "vulnerable": 0, "unknown_fw": 0})
            manufacturers[mfg]["total"] += 1
            if d["id"] in with_known_cves:
                manufacturers[mfg]["vulnerable"] += 1
            if not d.get("firmware_version") or d["firmware_version"] in ("unknown", ""):
                manufacturers[mfg]["unknown_fw"] += 1

        return {
            "total_devices": len(devices),
            "devices_with_known_cves": len(with_known_cves),
            "devices_unknown_firmware": len(unknown_firmware),
            "total_firmware_alerts": len(alerts),
            "critical_alerts": len([a for a in alerts if a["severity"] == "critical"]),
            "high_alerts": len([a for a in alerts if a["severity"] == "high"]),
            "auto_tasks_created": len(self.get_remediation_tasks(project_id)),
            "manufacturers": manufacturers,
            "known_cve_database_vendors": list(KNOWN_FIRMWARE_CVES.keys()),
            "wireless_risk_types": list(WIRELESS_RISKS.keys()),
        }


security_service = SecurityService()
