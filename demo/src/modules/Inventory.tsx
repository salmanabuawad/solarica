import { Box, Button } from "@mui/material";
import { PageHeader, Panel, StatTiles } from "../components/ui";
import { SimpleTable, TabPage, pill, type Col } from "../components/Table";
import { INVENTORY } from "../data/ops";
import { BORDER } from "../theme";

function Bar({ onHand, required }: { onHand: number; required: number }) {
  const pct = Math.min(100, Math.round((onHand / required) * 100));
  return (
    <Box sx={{ display: "flex", alignItems: "center", gap: 1, minWidth: 160 }}>
      <Box sx={{ flex: 1, height: 8, bgcolor: "#e2e8f0", borderRadius: 1, overflow: "hidden", border: `1px solid ${BORDER}` }}>
        <Box sx={{ width: `${pct}%`, height: "100%", bgcolor: pct >= 100 ? "#16a34a" : pct >= 70 ? "#f59e0b" : "#dc2626" }} />
      </Box>
      <Box sx={{ fontSize: 11, fontWeight: 700, color: "#475569", width: 34 }}>{pct}%</Box>
    </Box>
  );
}

export default function Inventory() {
  const cols: Col<any>[] = [
    { key: "item", label: "Item", render: (r) => <b>{r.item}</b> },
    { key: "onHand", label: "On Hand", num: true, render: (r) => `${r.onHand.toLocaleString()} ${r.unit}` },
    { key: "reserved", label: "Reserved", num: true, render: (r) => r.reserved.toLocaleString() },
    { key: "required", label: "Required", num: true, render: (r) => r.required.toLocaleString() },
    { key: "cover", label: "Coverage", render: (r) => <Bar onHand={r.onHand} required={r.required} /> },
    { key: "shortage", label: "Shortage", num: true, render: (r) => r.shortage > 0 ? pill(`-${r.shortage.toLocaleString()}`, "#dc2626") : pill("OK", "#16a34a") },
  ];
  const short = INVENTORY.filter((i) => i.shortage > 0);
  return (
    <Box>
      <PageHeader title="Inventory" subtitle="Modules · optimizers · bolts · cables · parts"
        right={<Button size="small" variant="contained">+ Procurement Order</Button>} />
      <StatTiles items={[
        { label: "SKUs", value: INVENTORY.length },
        { label: "Shortages", value: short.length, color: "#dc2626" },
        { label: "Units short", value: short.reduce((a, i) => a + i.shortage, 0).toLocaleString(), color: "#dc2626" },
      ]} />
      <TabPage tabs={[
        { label: "Inventory", node: <SimpleTable cols={cols} rows={INVENTORY.map((x, i) => ({ ...x, id: i }))} /> },
        { label: "Reservations", node: <SimpleTable cols={cols.filter((c) => ["item","onHand","reserved","required"].includes(String(c.key)))} rows={INVENTORY.map((x, i) => ({ ...x, id: i }))} /> },
        { label: "Shortages", node: <SimpleTable cols={cols} rows={short.map((x, i) => ({ ...x, id: i }))} /> },
        { label: "Procurement", node: (
          <Panel sx={{ p: 2 }}>
            <Box sx={{ fontWeight: 800, mb: 1 }}>Suggested procurement (auto from shortages)</Box>
            {short.map((s) => <Box key={s.item} sx={{ display: "flex", justifyContent: "space-between", py: 0.7, borderBottom: `1px solid ${BORDER}`, fontSize: 13 }}><span>{s.item}</span><b style={{ color: "#dc2626" }}>order {s.shortage.toLocaleString()} {s.unit}</b></Box>)}
          </Panel>
        ) },
      ]} />
    </Box>
  );
}
