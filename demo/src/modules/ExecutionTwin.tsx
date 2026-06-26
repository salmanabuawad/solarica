import { useMemo, useState } from "react";
import { Box, ToggleButton, ToggleButtonGroup, Tooltip } from "@mui/material";
import { PageHeader, Panel, StatTiles, Legend } from "../components/ui";
import { STATUS, BORDER } from "../theme";
import { STRINGS, BLOCKS, ASSETS, statusCounts, type Asset } from "../data/catalog";
import { useDrawer } from "../components/AssetDrawer";

type Layer = "DC" | "AC" | "BESS" | "SECURITY" | "CYBER";

export default function ExecutionTwin() {
  const [layer, setLayer] = useState<Layer>("DC");
  const { open } = useDrawer();
  const counts = useMemo(() => statusCounts(), []);
  const total = STRINGS.length;
  const ready = STRINGS.filter((s) => ["volt_checked","megger","iv_curve","ready","tga_commissioning"].includes(s.status)).length;
  const blocked = STRINGS.filter((s) => s.status === "blocked").length;

  return (
    <Box>
      <PageHeader title="Execution Twin — BHK" subtitle="Single live model of the site · click any asset to inspect"
        right={
          <ToggleButtonGroup size="small" exclusive value={layer} onChange={(_, v) => v && setLayer(v)}>
            {(["DC","AC","BESS","SECURITY","CYBER"] as Layer[]).map((l) => <ToggleButton key={l} value={l} sx={{ px: 1.4, fontSize: 12 }}>{l}</ToggleButton>)}
          </ToggleButtonGroup>
        } />

      <StatTiles items={[
        { label: "Strings", value: total },
        { label: "Ready / Tested", value: ready, color: "#16a34a" },
        { label: "Optimizers", value: counts.optimizer || 0, color: "#f59e0b" },
        { label: "AVL", value: counts.avl || 0, color: "#94a3b8" },
        { label: "Blocked", value: blocked, color: "#dc2626" },
        { label: "AC / BESS / Sec assets", value: ASSETS.length },
      ]} />

      <Panel sx={{ p: 1.5, mb: 1.5 }}>
        <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 1, mb: 1 }}>
          <Box sx={{ fontWeight: 700, fontSize: 13 }}>{layer} Layer</Box>
          <Legend />
        </Box>

        {layer === "DC" && (
          <Box sx={{ maxHeight: "calc(100vh - 330px)", overflow: "auto", display: "grid", gap: 1.2 }}>
            {BLOCKS.map((b) => {
              const rows = STRINGS.filter((s) => s.block === b);
              return (
                <Box key={b} sx={{ border: `1px solid ${BORDER}`, borderRadius: 1, p: 1 }}>
                  <Box sx={{ fontSize: 11, fontWeight: 800, color: "#475569", mb: 0.7 }}>BLOCK {b} · {rows.length} strings</Box>
                  <Box sx={{ display: "flex", flexWrap: "wrap", gap: "3px" }}>
                    {rows.map((s) => (
                      <Tooltip key={s.id} title={`${s.id} · ${STATUS[s.status]?.label}`} arrow>
                        <Box onClick={() => open({ type: "string", data: s })} sx={{
                          width: 16, height: 16, borderRadius: "3px", cursor: "pointer",
                          bgcolor: STATUS[s.status]?.color || "#94a3b8",
                          outline: s.blockers > 0 ? "2px solid #dc2626" : "none",
                          "&:hover": { transform: "scale(1.45)", zIndex: 1, boxShadow: "0 2px 8px rgba(0,0,0,.3)" }, transition: "transform .1s",
                        }} />
                      </Tooltip>
                    ))}
                  </Box>
                </Box>
              );
            })}
          </Box>
        )}

        {layer !== "DC" && (
          <Box sx={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(190px, 1fr))", gap: 1.2 }}>
            {ASSETS.filter((a) => a.layer === (layer === "CYBER" ? "CYBER" : layer)).map((a) => <AssetCard key={a.id} a={a} onClick={() => open({ type: "asset", data: a })} />)}
            {ASSETS.filter((a) => a.layer === layer).length === 0 && <Box sx={{ color: "#94a3b8", fontSize: 13 }}>No assets on this layer.</Box>}
          </Box>
        )}
      </Panel>
    </Box>
  );
}

function AssetCard({ a, onClick }: { a: Asset; onClick: () => void }) {
  const sc = a.status === "online" ? "#16a34a" : a.status === "warning" ? "#f59e0b" : a.status === "fault" ? "#dc2626" : "#94a3b8";
  return (
    <Box onClick={onClick} sx={{ border: `1px solid ${BORDER}`, borderRadius: 1.5, p: 1.2, cursor: "pointer", bgcolor: "#fff", "&:hover": { borderColor: "#94a3b8", boxShadow: "0 2px 10px rgba(15,23,42,.08)" } }}>
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <Box sx={{ fontWeight: 800, fontSize: 13.5 }}>{a.id}</Box>
        <Box sx={{ width: 9, height: 9, borderRadius: "50%", bgcolor: sc }} />
      </Box>
      <Box sx={{ fontSize: 11.5, color: "#64748b" }}>{a.vendor} · {a.model}</Box>
      <Box sx={{ display: "flex", gap: 0.7, mt: 0.8 }}>
        <Box sx={{ fontSize: 10.5, px: 0.7, py: 0.2, borderRadius: 0.5, bgcolor: "#f1f5f9", color: "#475569", fontWeight: 700 }}>{a.criticality}</Box>
        {(a.cves || 0) > 0 && <Box sx={{ fontSize: 10.5, px: 0.7, py: 0.2, borderRadius: 0.5, bgcolor: "#fee2e2", color: "#dc2626", fontWeight: 800 }}>{a.cves} CVE</Box>}
      </Box>
    </Box>
  );
}
