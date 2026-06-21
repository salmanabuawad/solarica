import rawStrings from "./bhkStrings.json";

// ---------------------------------------------------------------------------
// Roles — different roles see different modules / landing pages.
// ---------------------------------------------------------------------------
export interface Role { id: string; label: string; home: string; }
export const ROLES: Role[] = [
  { id: "owner", label: "Developer / Asset Owner", home: "operations" },
  { id: "exec", label: "Executive", home: "operations" },
  { id: "pm", label: "Project Manager", home: "twin" },
  { id: "site", label: "Site Manager", home: "twin" },
  { id: "foreman", label: "Foreman", home: "tasks" },
  { id: "dc", label: "DC Supervisor", home: "construction" },
  { id: "ac", label: "AC Supervisor", home: "construction" },
  { id: "bess", label: "BESS Supervisor", home: "construction" },
  { id: "qa", label: "QA Engineer", home: "qa" },
  { id: "commissioning", label: "Commissioning Engineer", home: "qa" },
  { id: "tech", label: "Technician", home: "tasks" },
  { id: "warehouse", label: "Warehouse Manager", home: "inventory" },
  { id: "security", label: "Security Company", home: "access" },
  { id: "cyber", label: "Cyber Team", home: "cyber" },
  { id: "om", label: "O&M Manager", home: "maintenance" },
];

// ---------------------------------------------------------------------------
// Navigation modules (grouped, OT-console style).
// `roles: "*"` = all roles; otherwise the listed role ids.
// ---------------------------------------------------------------------------
export interface ModuleDef {
  id: string; label: string; group: string; icon: string; roles: string[] | "*";
}
export const MODULES: ModuleDef[] = [
  { id: "twin", label: "Execution Twin", group: "Overview", icon: "map", roles: "*" },
  { id: "engineering", label: "Engineering", group: "Engineering", icon: "engineering", roles: ["owner","pm","site","dc","ac","bess"] },
  { id: "construction", label: "Construction", group: "Construction", icon: "construction", roles: "*" },
  { id: "blockers", label: "Blockers", group: "Construction", icon: "report", roles: "*" },
  { id: "tasks", label: "Tasks", group: "Construction", icon: "task", roles: "*" },
  { id: "access", label: "Site Access", group: "Field Ops", icon: "badge", roles: "*" },
  { id: "toolbox", label: "Toolbox", group: "Field Ops", icon: "build", roles: ["foreman","tech","site","warehouse","om"] },
  { id: "inventory", label: "Inventory", group: "Field Ops", icon: "inventory", roles: ["warehouse","pm","site","om"] },
  { id: "qa", label: "QA & Testing", group: "Quality", icon: "verified", roles: ["qa","commissioning","dc","pm","site"] },
  { id: "operations", label: "Operations", group: "Operate", icon: "bolt", roles: ["owner","exec","om","pm"] },
  { id: "maintenance", label: "Maintenance", group: "Operate", icon: "handyman", roles: ["om","tech","foreman","exec"] },
  { id: "cyber", label: "Cyber", group: "Security", icon: "security", roles: ["cyber","om","exec","owner"] },
  { id: "attackgraph", label: "Attack Graph", group: "Security", icon: "hub", roles: ["cyber","om","exec","owner"] },
];

export function modulesForRole(roleId: string): ModuleDef[] {
  return MODULES.filter((m) => m.roles === "*" || (m.roles as string[]).includes(roleId));
}

// ---------------------------------------------------------------------------
// Deterministic pseudo-random so the demo is stable across reloads.
// ---------------------------------------------------------------------------
function hash(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
  return (h >>> 0) / 4294967295;
}

export type Raw = { id: string; status: string; statuses: string[]; voltage: number | null; comment: string };

// ---------------------------------------------------------------------------
// Strings — real BHK data enriched with realistic DC test / task / blocker
// fields to drive the construction + QA pipeline.
// ---------------------------------------------------------------------------
export interface StringRow extends Raw {
  block: string; row: string; inverter: string;
  modules: number; optimizers: number;
  megger: "pass" | "fail" | "pending";
  ivCurve: "pass" | "fail" | "pending";
  tasks: number; photos: number; blockers: number;
  voltOk: boolean;
}

const STAGE_ORDER = ["avl","new","optimizer","connection","assembled","cable_to_tga","volt_checked","megger","iv_curve","ready","tga_commissioning"];

export const STRINGS: StringRow[] = (rawStrings as Raw[]).map((s) => {
  const parts = s.id.split(".");
  const block = parts[0] ?? "?";
  const inverter = `INV-${parts[0]}.${parts[1] ?? "0"}`;
  const row = parts.slice(0, 3).join(".");
  const r = hash(s.id);
  const advanced = STAGE_ORDER.indexOf(s.status) >= STAGE_ORDER.indexOf("volt_checked");
  return {
    ...s,
    block, row, inverter,
    modules: 26 + Math.floor(hash(s.id + "m") * 4),
    optimizers: 13 + Math.floor(hash(s.id + "o") * 2),
    megger: advanced ? (r > 0.12 ? "pass" : "fail") : "pending",
    ivCurve: advanced ? (r > 0.18 ? "pass" : "fail") : "pending",
    tasks: Math.floor(hash(s.id + "t") * 4),
    photos: Math.floor(hash(s.id + "p") * 6),
    blockers: s.status === "blocked" ? 1 : (hash(s.id + "b") > 0.94 ? 1 : 0),
    voltOk: s.voltage != null ? s.voltage >= 22 && s.voltage <= 23 : false,
  };
});

export const BLOCKS = Array.from(new Set(STRINGS.map((s) => s.block))).sort();
export const ROWS = Array.from(new Set(STRINGS.map((s) => s.row))).sort();

export function statusCounts(): Record<string, number> {
  const c: Record<string, number> = {};
  for (const s of STRINGS) c[s.status] = (c[s.status] || 0) + 1;
  return c;
}

// ---------------------------------------------------------------------------
// AC / BESS / Security / Cyber assets (mock, realistic).
// ---------------------------------------------------------------------------
export interface Asset {
  id: string; kind: string; layer: "AC" | "BESS" | "SECURITY" | "CYBER";
  vendor: string; model: string; firmware: string; latest: string;
  criticality: "Critical" | "High" | "Medium" | "Low";
  status: "online" | "warning" | "fault" | "offline";
  mw?: number; cves?: number;
}
export const ASSETS: Asset[] = [
  ...Array.from({ length: 14 }, (_, i) => ({
    id: `INV-${i + 1}`, kind: "Inverter", layer: "AC" as const, vendor: "Sungrow", model: "SG350HX",
    firmware: i % 4 === 0 ? "SAPPHIRE-1.2.3" : "SAPPHIRE-1.3.1", latest: "SAPPHIRE-1.4.0",
    criticality: "Critical" as const, status: (i === 3 ? "warning" : i === 9 ? "fault" : "online") as Asset["status"],
    mw: 0.35, cves: i % 4 === 0 ? 3 : 0,
  })),
  { id: "TR-01", kind: "Transformer", layer: "AC", vendor: "Schneider", model: "Trihal 2500", firmware: "n/a", latest: "n/a", criticality: "Critical", status: "online", mw: 2.5 },
  { id: "TR-02", kind: "Transformer", layer: "AC", vendor: "Schneider", model: "Trihal 2500", firmware: "n/a", latest: "n/a", criticality: "Critical", status: "online", mw: 2.5 },
  { id: "RMU-01", kind: "RMU", layer: "AC", vendor: "Schneider", model: "RM6", firmware: "n/a", latest: "n/a", criticality: "High", status: "online" },
  { id: "SWG-01", kind: "Switchgear", layer: "AC", vendor: "Siemens", model: "8DJH", firmware: "n/a", latest: "n/a", criticality: "High", status: "online" },
  { id: "BESS-01", kind: "Battery Container", layer: "BESS", vendor: "Sungrow", model: "PowerTitan", firmware: "BMS-2.1", latest: "BMS-2.3", criticality: "Critical", status: "online", mw: 2.0, cves: 1 },
  { id: "PCS-01", kind: "PCS", layer: "BESS", vendor: "Sungrow", model: "SC2000", firmware: "PCS-3.0", latest: "PCS-3.0", criticality: "Critical", status: "online" },
  { id: "EMS-01", kind: "EMS", layer: "BESS", vendor: "Sungrow", model: "iEnergyCloud", firmware: "EMS-5.4", latest: "EMS-5.6", criticality: "High", status: "warning", cves: 2 },
  { id: "FIRE-01", kind: "Fire System", layer: "BESS", vendor: "Siemens", model: "FS720", firmware: "n/a", latest: "n/a", criticality: "Critical", status: "online" },
  { id: "CAM-PTZ-07", kind: "PTZ Camera", layer: "SECURITY", vendor: "Dahua", model: "SD6CE", firmware: "V2.800", latest: "V2.840", criticality: "Medium", status: "online", cves: 4 },
  { id: "CAM-12", kind: "Camera", layer: "SECURITY", vendor: "Hikvision", model: "DS-2CD", firmware: "V5.5.0", latest: "V5.7.3", criticality: "Low", status: "online", cves: 2 },
  { id: "NVR-01", kind: "NVR", layer: "SECURITY", vendor: "Dahua", model: "NVR616", firmware: "V4.001", latest: "V4.003", criticality: "Medium", status: "online", cves: 1 },
  { id: "GATE-01", kind: "Gate", layer: "SECURITY", vendor: "Nice", model: "ROBUS", firmware: "n/a", latest: "n/a", criticality: "Low", status: "online" },
  { id: "SW-CORE", kind: "Switch", layer: "CYBER", vendor: "Cisco", model: "IE-4000", firmware: "15.2(7)E3", latest: "15.2(8)E", criticality: "Critical", status: "online", cves: 2 },
  { id: "FW-01", kind: "Firewall", layer: "CYBER", vendor: "Fortinet", model: "FortiGate 60F", firmware: "7.2.5", latest: "7.4.3", criticality: "Critical", status: "online", cves: 3 },
  { id: "SCADA-01", kind: "SCADA Server", layer: "CYBER", vendor: "Schneider", model: "EcoStruxure", firmware: "2023.2", latest: "2024.1", criticality: "Critical", status: "online", cves: 5 },
  { id: "WX-01", kind: "Weather Station", layer: "CYBER", vendor: "Kipp&Zonen", model: "RT1", firmware: "1.1", latest: "1.1", criticality: "Low", status: "online" },
];

// ---------------------------------------------------------------------------
// Blockers + Tasks (seeded from blocked strings + realistic extras).
// ---------------------------------------------------------------------------
export interface Blocker { id: string; title: string; asset: string; severity: "critical" | "high" | "medium" | "low" | "info"; owner: string; status: "Open" | "In Progress" | "Resolved"; due: string; impact: string; }
const BLOCK_TITLES = ["Broken Module", "Missing Optimizer", "Missing Bolts", "Wrong Label", "Damaged Connector", "Shading Obstruction"];
export const BLOCKERS: Blocker[] = STRINGS.filter((s) => s.blockers > 0).slice(0, 24).map((s, i) => ({
  id: `BLK-${1000 + i}`,
  title: BLOCK_TITLES[i % BLOCK_TITLES.length],
  asset: s.id,
  severity: (["critical","high","medium","high","medium","low"][i % 6]) as Blocker["severity"],
  owner: ["A. Cohen","M. Levi","R. Haddad","Site Crew B"][i % 4],
  status: (["Open","In Progress","Open","Open"][i % 4]) as Blocker["status"],
  due: `2026-0${(i % 6) + 1}-1${i % 9}`,
  impact: `${1 + (i % 3)} strings`,
}));

export interface Task { id: string; title: string; scope: string; assignee: string; status: string; priority: string; }
const TASK_TITLES = ["Install optimizers", "Connect panels to TGA", "Voltage test", "Megger test", "IV curve scan", "Fix labeling", "Re-torque bolts"];
const TASK_STATES = ["Created","Assigned","Accepted","In Progress","Done","Approved"];
export const TASKS: Task[] = STRINGS.slice(0, 60).map((s, i) => ({
  id: `T-${2000 + i}`,
  title: TASK_TITLES[i % TASK_TITLES.length],
  scope: s.id,
  assignee: ["A. Cohen","M. Levi","R. Haddad","Crew A","Crew B"][i % 5],
  status: TASK_STATES[i % TASK_STATES.length],
  priority: ["High","Medium","Low"][i % 3],
}));

// ---------------------------------------------------------------------------
// Attack graph (OTORIO-style): vulnerability -> reachability -> impact.
// ---------------------------------------------------------------------------
export const ATTACK_CHAIN = [
  { id: "ag-cam", label: "CAM-PTZ-07", sub: "Dahua PTZ · CVE-2024-xxxx", kind: "entry" },
  { id: "ag-nvr", label: "NVR-01", sub: "Pivot · default creds", kind: "pivot" },
  { id: "ag-sw", label: "SW-CORE", sub: "Cisco IE-4000 · flat VLAN", kind: "pivot" },
  { id: "ag-scada", label: "SCADA-01", sub: "EcoStruxure · 5 CVEs", kind: "target" },
  { id: "ag-gw", label: "Inverter Gateway", sub: "Modbus exposed", kind: "target" },
  { id: "ag-inv", label: "14 Inverters", sub: "4.9 MW", kind: "impact" },
  { id: "ag-fin", label: "₪40,000 / day", sub: "Revenue at risk", kind: "impact" },
];
