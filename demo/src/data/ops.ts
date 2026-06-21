// Additional realistic mock datasets for the remaining V2 modules.
import { STRINGS, ASSETS } from "./catalog";

function h(s: string): number { let x = 2166136261; for (let i = 0; i < s.length; i++) { x ^= s.charCodeAt(i); x = Math.imul(x, 16777619); } return (x >>> 0) / 4294967295; }
const pick = <T,>(arr: T[], seed: string) => arr[Math.floor(h(seed) * arr.length)];

// ---- Engineering -----------------------------------------------------------
export const DESIGN_FILES = [
  { name: "BHK_E_10_Color_Map_rev01.pdf", type: "PDF", size: "7.1 MB", uploaded: "2026-01-12", status: "Parsed" },
  { name: "BHK_E_20_Cable_Plan_rev01.pdf", type: "PDF", size: "5.1 MB", uploaded: "2026-01-12", status: "Parsed" },
  { name: "BHK_E_41_Panels_Plan_rev01.pdf", type: "PDF", size: "1.6 MB", uploaded: "2026-01-12", status: "Parsed" },
  { name: "BHK_layout_rev03.dwg", type: "DWG", size: "12.4 MB", uploaded: "2026-01-10", status: "Imported" },
  { name: "BHK_trackers.dxf", type: "DXF", size: "3.2 MB", uploaded: "2026-01-10", status: "Imported" },
];
export const EPL_SUMMARY = [
  { entity: "Rows", count: 107 },
  { entity: "Strings", count: STRINGS.length },
  { entity: "Trackers", count: 312 },
  { entity: "Inverters", count: ASSETS.filter((a) => a.kind === "Inverter").length },
  { entity: "BESS containers", count: ASSETS.filter((a) => a.kind === "Battery Container").length },
  { entity: "Security assets", count: ASSETS.filter((a) => a.layer === "SECURITY").length },
];
const VAL_TYPES = ["Missing string", "Duplicate string", "Invalid naming", "Missing asset", "Cross-row string"];
export const VALIDATION = STRINGS.filter((_, i) => i % 23 === 0).slice(0, 12).map((s, i) => ({
  id: `V-${i + 1}`, type: VAL_TYPES[i % VAL_TYPES.length], target: s.id,
  severity: (["High", "Medium", "Low"][i % 3]), detail: pick(["Not found in E20 cable plan", "Two strings share an ID", "Label breaks naming rule", "No matching tracker", "Crosses 2 physical rows"], s.id),
}));
export const ENG_CHANGES = [
  { id: "ECR-001", title: "Aerial DC → Underground DC (Block 2)", impact: "37 strings re-routed", cost: "₪ 180,000", schedule: "+9 days", affected: "Block 2 · INV-1.2 · TR-01", status: "Under review" },
  { id: "ECR-002", title: "Add string monitoring on Block 1", impact: "12 combiner changes", cost: "₪ 42,000", schedule: "+3 days", affected: "Block 1", status: "Approved" },
];

// ---- Toolbox ---------------------------------------------------------------
const TOOL_TYPES = ["IV Tester", "Megger", "Torque Wrench", "Tablet", "Thermal Camera"];
export const TOOLS = Array.from({ length: 22 }, (_, i) => {
  const t = TOOL_TYPES[i % TOOL_TYPES.length]; const r = h("tool" + i);
  return {
    id: `TL-${100 + i}`, type: t, serial: `${t.slice(0, 2).toUpperCase()}-${2000 + i}`,
    status: r > 0.8 ? "Calibration Due" : r > 0.45 ? "Assigned" : "Available",
    assignedTo: r > 0.45 && r <= 0.8 ? pick(["A. Cohen", "M. Levi", "Crew A", "Crew B"], "as" + i) : "—",
    calDue: `2026-0${(i % 9) + 1}-15`,
  };
});
export const TECH_READINESS = ["A. Cohen", "M. Levi", "R. Haddad", "Crew A", "Crew B"].map((name, i) => ({
  name, access: h("acc" + i) > 0.2, tools: h("to" + i) > 0.3, training: h("tr" + i) > 0.15, materials: h("ma" + i) > 0.4,
}));

// ---- Inventory -------------------------------------------------------------
export const INVENTORY = [
  { item: "PV Modules 580W", onHand: 9120, reserved: 7800, required: 12672, unit: "pcs" },
  { item: "Optimizers", onHand: 4100, reserved: 3900, required: 6336, unit: "pcs" },
  { item: "Mounting Bolts M10", onHand: 18000, reserved: 12000, required: 16000, unit: "pcs" },
  { item: "DC Cable 6mm²", onHand: 4200, reserved: 3800, required: 5200, unit: "m" },
  { item: "MC4 Connectors", onHand: 1100, reserved: 980, required: 1300, unit: "pcs" },
].map((x) => ({ ...x, shortage: Math.max(0, x.required - x.onHand) }));

// ---- Site Access -----------------------------------------------------------
const STATES = ["Requested", "Approved", "Entered", "Exited"];
export const ACCESS_REQUESTS = Array.from({ length: 16 }, (_, i) => {
  const st = STATES[Math.min(3, Math.floor(h("ar" + i) * 4))];
  return {
    id: `AR-${500 + i}`, person: pick(["A. Cohen", "M. Levi", "R. Haddad", "D. Mizrahi", "Y. Bar"], "p" + i),
    company: pick(["Solarica Field", "DC Crew Ltd", "AC Contractor", "BESS Team"], "c" + i),
    vehicle: pick(["Truck 12-345-67", "Van 88-221-04", "Pickup 33-119-22", "—"], "v" + i),
    task: pick(["Install optimizers", "Megger test", "Cable pulling", "Repair INV-09"], "t" + i),
    status: st, approvalMin: st === "Requested" ? null : 4 + Math.floor(h("am" + i) * 40),
  };
});

// ---- Operations ------------------------------------------------------------
export const INVERTERS = ASSETS.filter((a) => a.kind === "Inverter").map((a) => ({
  ...a, power: +(a.mw! * (0.6 + h(a.id) * 0.38)).toFixed(2), availability: +(97 + h(a.id + "av") * 2.9).toFixed(1),
  alarms: a.status === "fault" ? 2 : a.status === "warning" ? 1 : 0, revenue: Math.round(1800 + h(a.id + "r") * 1400),
}));

// ---- Maintenance -----------------------------------------------------------
const WO_STATES = ["Created", "Assigned", "Tech En-route", "On Site", "Repaired", "Approved"];
const ALARMS = ["String underperformance", "Inverter overtemp", "Comm loss", "Ground fault", "Fan failure"];
export const WORK_ORDERS = Array.from({ length: 18 }, (_, i) => {
  const cost = [800, 1500, 3200, 6500, 14000][i % 5];
  return {
    id: `WO-${700 + i}`, asset: pick(["INV-09", "INV-04", "TR-01", "BESS-01", "EMS-01"], "wa" + i),
    alarm: ALARMS[i % ALARMS.length], status: WO_STATES[i % WO_STATES.length],
    technician: pick(["A. Cohen", "M. Levi", "R. Haddad"], "wt" + i),
    cost, approval: cost <= 2000 ? "Auto" : cost <= 10000 ? "Manager" : "Owner",
    partsReady: h("pr" + i) > 0.3,
  };
});
export const COST_RULES = [
  { range: "0 – 2,000 ₪", approver: "Auto-approved", color: "#16a34a" },
  { range: "2,000 – 10,000 ₪", approver: "Site / O&M Manager", color: "#f59e0b" },
  { range: "10,000 ₪ +", approver: "Asset Owner", color: "#dc2626" },
];
