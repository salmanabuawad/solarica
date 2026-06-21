import { useState } from "react";
import { Box, Tabs, Tab } from "@mui/material";
import { PageHeader, Panel, StatTiles } from "../components/ui";
import { INVERTERS } from "../data/ops";
import { BORDER } from "../theme";

export default function Operations() {
  const [sel, setSel] = useState(INVERTERS[0]?.id);
  const [tab, setTab] = useState(3);
  const inv = INVERTERS.find((i) => i.id === sel) || INVERTERS[0];
  const lifecycle = ["Construction", "QA", "Commissioning", "Operations", "Maintenance", "Cyber"];

  return (
    <Box>
      <PageHeader title="Operations" subtitle="Asset-centric — every device carries its full lifecycle" />
      <StatTiles items={[
        { label: "Plant power", value: `${INVERTERS.reduce((a, i) => a + i.power, 0).toFixed(1)} MW`, color: "#16a34a" },
        { label: "Avg availability", value: `${(INVERTERS.reduce((a, i) => a + i.availability, 0) / INVERTERS.length).toFixed(1)}%` },
        { label: "Active alarms", value: INVERTERS.reduce((a, i) => a + i.alarms, 0), color: "#dc2626" },
        { label: "Revenue / day", value: `₪${INVERTERS.reduce((a, i) => a + i.revenue, 0).toLocaleString()}` },
      ]} />
      <Box sx={{ display: "flex", gap: 1.5 }}>
        <Panel sx={{ width: 200, maxHeight: "calc(100vh - 260px)", overflow: "auto" }}>
          {INVERTERS.map((i) => (
            <Box key={i.id} onClick={() => setSel(i.id)} sx={{ px: 1.5, py: 1, cursor: "pointer", borderBottom: `1px solid ${BORDER}`, bgcolor: i.id === sel ? "#eff6ff" : "transparent", borderLeft: i.id === sel ? "3px solid #1e3a8a" : "3px solid transparent" }}>
              <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <b style={{ fontSize: 13 }}>{i.id}</b>
                <Box sx={{ width: 8, height: 8, borderRadius: "50%", bgcolor: i.alarms ? "#dc2626" : "#16a34a" }} />
              </Box>
              <Box sx={{ fontSize: 11, color: "#64748b" }}>{i.power} MW · {i.availability}%</Box>
            </Box>
          ))}
        </Panel>
        <Panel sx={{ flex: 1 }}>
          <Box sx={{ p: 1.5, borderBottom: `1px solid ${BORDER}` }}>
            <Box sx={{ fontWeight: 800, fontSize: 16 }}>{inv.id}</Box>
            <Box sx={{ fontSize: 12, color: "#64748b" }}>{inv.vendor} · {inv.model}</Box>
          </Box>
          <StatTiles items={[
            { label: "Current Power", value: `${inv.power} MW`, color: "#16a34a" },
            { label: "Availability", value: `${inv.availability}%` },
            { label: "Alarms", value: inv.alarms, color: inv.alarms ? "#dc2626" : "#16a34a" },
            { label: "Revenue", value: `₪${inv.revenue.toLocaleString()}/day` },
          ]} />
          <Tabs value={tab} onChange={(_, v) => setTab(v)} variant="scrollable" scrollButtons={false} sx={{ px: 1, borderTop: `1px solid ${BORDER}`, minHeight: 40, "& .MuiTab-root": { minHeight: 40, fontSize: 12.5 } }}>
            {lifecycle.map((l) => <Tab key={l} label={l} />)}
          </Tabs>
          <Box sx={{ p: 2, fontSize: 13, color: "#475569" }}>
            <b>{lifecycle[tab]}</b> view for {inv.id} — {[
              "as-built strings, optimizers and cabling",
              "voltage / megger / IV-curve test records",
              "commissioning checklist & sign-off",
              "live power, availability, alarms, revenue",
              "work orders, repairs and spare parts",
              "firmware, CVEs and attack-graph exposure",
            ][tab]}.
          </Box>
        </Panel>
      </Box>
    </Box>
  );
}
