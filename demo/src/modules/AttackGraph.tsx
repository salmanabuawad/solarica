import { useMemo } from "react";
import ReactFlow, { Background, Controls, MarkerType, type Node, type Edge } from "reactflow";
import "reactflow/dist/style.css";
import { Box } from "@mui/material";
import { PageHeader, Panel, StatTiles } from "../components/ui";
import { ATTACK_CHAIN, ASSETS } from "../data/catalog";
import { BORDER } from "../theme";

const KIND_COLOR: Record<string, { bg: string; bd: string }> = {
  entry: { bg: "#fee2e2", bd: "#dc2626" },
  pivot: { bg: "#fef3c7", bd: "#f59e0b" },
  target: { bg: "#ffedd5", bd: "#ea580c" },
  impact: { bg: "#0f172a", bd: "#0f172a" },
};

export default function AttackGraph() {
  const { nodes, edges } = useMemo(() => {
    const nodes: Node[] = ATTACK_CHAIN.map((n, i) => {
      const c = KIND_COLOR[n.kind];
      const dark = n.kind === "impact";
      return {
        id: n.id,
        position: { x: 40 + i * 215, y: 120 + (i % 2) * 70 },
        data: {
          label: (
            <div style={{ textAlign: "left", padding: "2px 4px" }}>
              <div style={{ fontWeight: 800, fontSize: 13, color: dark ? "#fff" : "#0f172a" }}>{n.label}</div>
              <div style={{ fontSize: 10.5, color: dark ? "#cbd5e1" : "#64748b" }}>{n.sub}</div>
            </div>
          ),
        },
        style: { background: c.bg, border: `2px solid ${c.bd}`, borderRadius: 8, width: 180, padding: 6 },
        sourcePosition: "right" as any, targetPosition: "left" as any,
      };
    });
    const edges: Edge[] = ATTACK_CHAIN.slice(0, -1).map((n, i) => ({
      id: `e-${i}`, source: n.id, target: ATTACK_CHAIN[i + 1].id, animated: true,
      style: { stroke: "#dc2626", strokeWidth: 2 },
      markerEnd: { type: MarkerType.ArrowClosed, color: "#dc2626" },
    }));
    return { nodes, edges };
  }, []);

  return (
    <Box>
      <PageHeader title="Attack Graph" subtitle="From a real site asset to operational & financial impact — OTORIO-style reachability" />
      <StatTiles items={[
        { label: "Entry asset", value: "CAM-PTZ-07", color: "#dc2626" },
        { label: "Affected", value: "14 Inverters" },
        { label: "MW at risk", value: "4.9 MW", color: "#ea580c" },
        { label: "Revenue impact", value: "₪40k/day", color: "#dc2626" },
        { label: "Critical CVEs", value: ASSETS.reduce((a, x) => a + (x.cves || 0), 0) },
      ]} />
      <Box sx={{ display: "flex", gap: 1.5 }}>
        <Panel sx={{ flex: 1, height: "calc(100vh - 250px)", overflow: "hidden" }}>
          <ReactFlow nodes={nodes} edges={edges} fitView proOptions={{ hideAttribution: true }} nodesDraggable={false} nodesConnectable={false}>
            <Background color="#cbd5e1" gap={18} />
            <Controls showInteractive={false} />
          </ReactFlow>
        </Panel>
        <Panel sx={{ width: 300, p: 1.5 }}>
          <Box sx={{ fontWeight: 800, mb: 1 }}>Impact & Mitigation</Box>
          {[
            ["Criticality", "Critical"],
            ["Vector", "PTZ → NVR → Switch → SCADA"],
            ["Reachability", "Flat VLAN, default creds"],
            ["MW impact", "4.9 MW (14 inverters)"],
            ["Revenue", "₪40,000 / day"],
          ].map(([k, v]) => (
            <Box key={k} sx={{ display: "flex", justifyContent: "space-between", py: 0.7, borderBottom: `1px solid ${BORDER}`, fontSize: 12.5 }}>
              <span style={{ color: "#64748b" }}>{k}</span><b>{v}</b>
            </Box>
          ))}
          <Box sx={{ mt: 1.5, fontWeight: 800, fontSize: 12.5 }}>Recommended mitigation</Box>
          <Box component="ul" sx={{ pl: 2, m: 0, fontSize: 12, color: "#475569", "& li": { mb: 0.5 } }}>
            <li>Segment camera VLAN from OT</li>
            <li>Rotate NVR / SCADA credentials</li>
            <li>Patch CAM-PTZ-07 to V2.840</li>
            <li>Restrict Modbus on inverter gateway</li>
          </Box>
        </Panel>
      </Box>
    </Box>
  );
}
