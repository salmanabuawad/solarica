import type { ReactNode } from "react";
import { Box, Chip } from "@mui/material";
import { BORDER, STATUS } from "../theme";

export function PageHeader({ title, subtitle, right }: { title: string; subtitle?: string; right?: ReactNode }) {
  return (
    <Box sx={{ display: "flex", alignItems: "flex-end", flexWrap: "wrap", gap: 1, mb: 1.5 }}>
      <Box>
        <Box sx={{ fontSize: 19, fontWeight: 800, color: "#0f172a" }}>{title}</Box>
        {subtitle && <Box sx={{ fontSize: 12.5, color: "#64748b" }}>{subtitle}</Box>}
      </Box>
      <Box sx={{ flex: 1 }} />
      {right}
    </Box>
  );
}

export function Panel({ children, sx }: { children: ReactNode; sx?: any }) {
  return <Box sx={{ bgcolor: "#fff", border: `1px solid ${BORDER}`, borderRadius: 2, ...sx }}>{children}</Box>;
}

export function StatTiles({ items }: { items: { label: string; value: ReactNode; color?: string }[] }) {
  return (
    <Box sx={{ display: "flex", gap: 1.5, mb: 1.5, flexWrap: "wrap" }}>
      {items.map((it, i) => (
        <Panel key={i} sx={{ px: 2, py: 1, minWidth: 130 }}>
          <Box sx={{ fontSize: 11, color: "#64748b", textTransform: "uppercase", letterSpacing: 0.5 }}>{it.label}</Box>
          <Box sx={{ fontSize: 22, fontWeight: 800, color: it.color || "#0f172a" }}>{it.value}</Box>
        </Panel>
      ))}
    </Box>
  );
}

export function statusChip(status: string) {
  const s = STATUS[status] || STATUS.new;
  return <Chip size="small" label={s.label} sx={{ bgcolor: s.bg, color: s.color, fontWeight: 700 }} />;
}

export function Legend() {
  return (
    <Box sx={{ display: "flex", gap: 1.5, flexWrap: "wrap", alignItems: "center" }}>
      {Object.entries(STATUS).map(([k, s]) => (
        <Box key={k} sx={{ display: "flex", alignItems: "center", gap: 0.5, fontSize: 11, color: "#475569" }}>
          <Box sx={{ width: 10, height: 10, borderRadius: 0.5, bgcolor: s.color }} />{s.label}
        </Box>
      ))}
    </Box>
  );
}
