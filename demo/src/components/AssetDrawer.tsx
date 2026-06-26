import { createContext, useContext, useState, type ReactNode } from "react";
import { Box, Tabs, Tab, Chip, IconButton, Button, LinearProgress } from "@mui/material";
import CloseOutlined from "@mui/icons-material/CloseOutlined";
import PhotoCameraOutlined from "@mui/icons-material/PhotoCameraOutlined";
import { STATUS, BORDER, SEVERITY, ACCENT } from "../theme";
import type { StringRow, Asset } from "../data/catalog";

type DrawerItem =
  | { type: "string"; data: StringRow }
  | { type: "asset"; data: Asset };

const Ctx = createContext<{ open: (i: DrawerItem) => void; close: () => void }>({ open: () => {}, close: () => {} });
export const useDrawer = () => useContext(Ctx);

function Row({ k, v }: { k: string; v: ReactNode }) {
  return (
    <Box sx={{ display: "flex", justifyContent: "space-between", py: 0.7, borderBottom: `1px solid ${BORDER}`, fontSize: 12.5 }}>
      <Box sx={{ color: "#64748b" }}>{k}</Box>
      <Box sx={{ fontWeight: 700, color: "#0f172a" }}>{v}</Box>
    </Box>
  );
}
function TestBadge({ v }: { v: string }) {
  const c = v === "pass" ? "#16a34a" : v === "fail" ? "#dc2626" : "#94a3b8";
  return <Chip size="small" label={v.toUpperCase()} sx={{ bgcolor: `${c}22`, color: c, fontWeight: 800 }} />;
}

function StringBody({ s }: { s: StringRow }) {
  const [tab, setTab] = useState(0);
  const tabs = ["Overview", "Tests", "Photos", "Tasks", "History", "Blockers"];
  return (
    <>
      <Tabs value={tab} onChange={(_, v) => setTab(v)} variant="scrollable" scrollButtons={false}
        sx={{ borderBottom: `1px solid ${BORDER}`, minHeight: 40, "& .MuiTab-root": { minHeight: 40, fontSize: 12, py: 0 } }}>
        {tabs.map((t) => <Tab key={t} label={t} />)}
      </Tabs>
      <Box sx={{ p: 1.5, overflowY: "auto", flex: 1 }}>
        {tab === 0 && (
          <Box>
            <Row k="Row" v={s.row} />
            <Row k="Inverter" v={s.inverter} />
            <Row k="MPPT" v={`MPPT-${(s.id.charCodeAt(s.id.length - 1) % 6) + 1}`} />
            <Row k="Modules" v={s.modules} />
            <Row k="Optimizers" v={s.optimizers} />
            <Row k="Voltage" v={s.voltage != null ? <span style={{ color: s.voltOk ? "#16a34a" : "#dc2626" }}>{s.voltage.toFixed(2)} V</span> : "—"} />
            {s.comment && <Box sx={{ mt: 1, p: 1, bgcolor: "#fff7ed", border: `1px solid #fed7aa`, borderRadius: 1, fontSize: 12 }}>{s.comment}</Box>}
          </Box>
        )}
        {tab === 1 && (
          <Box sx={{ display: "grid", gap: 1 }}>
            <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}><span>Voltage</span>{s.voltage != null ? <TestBadge v={s.voltOk ? "pass" : "fail"} /> : <TestBadge v="pending" />}</Box>
            <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}><span>Megger (insulation)</span><TestBadge v={s.megger} /></Box>
            <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}><span>IV Curve</span><TestBadge v={s.ivCurve} /></Box>
            <Box sx={{ mt: 1, p: 1.2, border: `1px solid ${BORDER}`, borderRadius: 1, bgcolor: "#f8fafc" }}>
              <Box sx={{ fontSize: 11, color: "#64748b", mb: 0.5 }}>IV CURVE — expected vs actual</Box>
              <svg width="100%" height="90" viewBox="0 0 220 90">
                <path d="M5 75 C 90 75, 150 70, 175 18 L 200 16" fill="none" stroke="#94a3b8" strokeWidth="2" strokeDasharray="4 3" />
                <path d={s.ivCurve === "fail" ? "M5 75 C 80 75, 130 72, 150 45 L 185 42" : "M5 74 C 90 74, 150 69, 174 19 L 199 17"} fill="none" stroke={s.ivCurve === "fail" ? "#dc2626" : "#16a34a"} strokeWidth="2.4" />
              </svg>
              {s.ivCurve === "fail" && <Box sx={{ fontSize: 11.5, color: "#dc2626", fontWeight: 700 }}>Likely cause: broken / missing module or optimizer failure</Box>}
            </Box>
          </Box>
        )}
        {tab === 2 && (
          <Box sx={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 1 }}>
            {Array.from({ length: s.photos }, (_, i) => (
              <Box key={i} sx={{ aspectRatio: "1", bgcolor: "#e2e8f0", borderRadius: 1, display: "flex", alignItems: "center", justifyContent: "center", color: "#94a3b8" }}><PhotoCameraOutlined /></Box>
            ))}
            {s.photos === 0 && <Box sx={{ gridColumn: "1 / -1", color: "#94a3b8", fontSize: 12 }}>No photos uploaded.</Box>}
          </Box>
        )}
        {tab === 3 && <Box sx={{ fontSize: 12.5 }}>{s.tasks > 0 ? `${s.tasks} task(s) linked to this string.` : "No open tasks."}</Box>}
        {tab === 4 && (
          <Box sx={{ display: "grid", gap: 0.8, fontSize: 12 }}>
            {["Created","Optimizers installed","Panel connected","Connected to TGA"].map((h, i) => (
              <Box key={i} sx={{ display: "flex", gap: 1 }}><Box sx={{ width: 8, height: 8, borderRadius: "50%", bgcolor: ACCENT, mt: 0.5 }} /><Box><b>{h}</b><Box sx={{ color: "#94a3b8" }}>2026-0{i + 1}-1{i} · Crew A</Box></Box></Box>
            ))}
          </Box>
        )}
        {tab === 5 && (s.blockers > 0
          ? <Box sx={{ p: 1, border: `1px solid ${SEVERITY.high}`, borderRadius: 1, bgcolor: "#fff7ed", fontSize: 12.5 }}><b style={{ color: SEVERITY.high }}>⚠ Blocker:</b> Construction not ready (קונסטרוקציה לא מוכנה)</Box>
          : <Box sx={{ color: "#16a34a", fontSize: 12.5 }}>No active blockers.</Box>)}
      </Box>
    </>
  );
}

function AssetBody({ a }: { a: Asset }) {
  const [tab, setTab] = useState(0);
  const tabs = ["Overview", "Operations", "Cyber", "History"];
  return (
    <>
      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ borderBottom: `1px solid ${BORDER}`, minHeight: 40, "& .MuiTab-root": { minHeight: 40, fontSize: 12 } }}>
        {tabs.map((t) => <Tab key={t} label={t} />)}
      </Tabs>
      <Box sx={{ p: 1.5, overflowY: "auto", flex: 1 }}>
        {tab === 0 && <Box><Row k="Type" v={a.kind} /><Row k="Layer" v={a.layer} /><Row k="Vendor" v={a.vendor} /><Row k="Model" v={a.model} /><Row k="Criticality" v={a.criticality} />{a.mw != null && <Row k="Rated" v={`${a.mw} MW`} />}</Box>}
        {tab === 1 && <Box><Row k="Status" v={a.status} /><Row k="Current Power" v={a.mw != null ? `${(a.mw * 0.82).toFixed(2)} MW` : "—"} />{<Row k="Availability" v="99.2%" />}<Row k="Alarms" v={a.status === "fault" ? "1 active" : "0"} /></Box>}
        {tab === 2 && <Box><Row k="Firmware" v={a.firmware} /><Row k="Latest" v={<span style={{ color: a.firmware !== a.latest && a.latest !== "n/a" ? "#ea580c" : "#16a34a" }}>{a.latest}</span>} /><Row k="Open CVEs" v={<span style={{ color: (a.cves || 0) > 0 ? "#dc2626" : "#16a34a", fontWeight: 800 }}>{a.cves || 0}</span>} />{(a.cves || 0) > 0 && <Button size="small" variant="outlined" color="error" sx={{ mt: 1 }}>View in Attack Graph</Button>}</Box>}
        {tab === 3 && <Box sx={{ fontSize: 12, color: "#64748b" }}>Construction → QA → Commissioning → Operations → Maintenance → Cyber timeline.</Box>}
      </Box>
    </>
  );
}

export function DrawerProvider({ children }: { children: ReactNode }) {
  const [item, setItem] = useState<DrawerItem | null>(null);
  const id = item ? item.data.id : "";
  const status = item?.type === "string" ? STATUS[item.data.status] : undefined;
  return (
    <Ctx.Provider value={{ open: setItem, close: () => setItem(null) }}>
      {children}
      <Box sx={{
        position: "fixed", top: 52, bottom: 0,
        // Desktop: 430px panel sitting left of the 250px nav. Mobile: full-width
        // (no nav gutter) so the closed panel slides fully off-screen instead of
        // covering the right half of the content.
        right: { xs: 0, md: 250 }, width: { xs: "100%", md: 430 }, maxWidth: "100%", zIndex: 35,
        bgcolor: "#fff", borderLeft: `1px solid ${BORDER}`, boxShadow: item ? "-12px 0 32px rgba(15,23,42,0.14)" : "none",
        transform: item ? "translateX(0)" : "translateX(110%)", transition: "transform .22s ease",
        display: "flex", flexDirection: "column",
      }}>
        {item && (
          <>
            <Box sx={{ p: 1.5, borderBottom: `1px solid ${BORDER}`, display: "flex", alignItems: "center", gap: 1 }}>
              <Box sx={{ flex: 1 }}>
                <Box sx={{ fontWeight: 800, fontSize: 15 }}>{item.type === "string" ? `String ${id}` : id}</Box>
                <Box sx={{ fontSize: 11.5, color: "#64748b" }}>{item.type === "string" ? "DC · construction asset" : `${(item.data as Asset).layer} · ${(item.data as Asset).kind}`}</Box>
              </Box>
              {status && <Chip size="small" label={status.label} sx={{ bgcolor: status.bg, color: status.color }} />}
              <IconButton size="small" onClick={() => setItem(null)}><CloseOutlined fontSize="small" /></IconButton>
            </Box>
            {item.type === "string" && (
              <LinearProgress variant="determinate" value={Math.min(100, stageProgress(item.data.status))} sx={{ height: 4 }} />
            )}
            {item.type === "string" ? <StringBody s={item.data} /> : <AssetBody a={item.data} />}
          </>
        )}
      </Box>
    </Ctx.Provider>
  );
}

function stageProgress(status: string): number {
  const order = ["new","optimizer","connection","assembled","cable_to_tga","volt_checked","megger","iv_curve","ready","tga_commissioning"];
  const i = order.indexOf(status);
  return i < 0 ? 0 : (i / (order.length - 1)) * 100;
}
