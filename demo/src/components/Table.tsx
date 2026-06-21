import { useState, type ReactNode } from "react";
import { Box, Table, TableBody, TableCell, TableHead, TableRow, Tabs, Tab, Chip } from "@mui/material";
import { BORDER } from "../theme";
import { Panel } from "./ui";

export interface Col<T> { key: keyof T | string; label: string; render?: (r: T) => ReactNode; num?: boolean; width?: number | string; }

export function SimpleTable<T extends { id?: string | number }>({ cols, rows, onRow }: { cols: Col<T>[]; rows: T[]; onRow?: (r: T) => void }) {
  return (
    <Panel sx={{ overflow: "auto" }}>
      <Table size="small" stickyHeader>
        <TableHead>
          <TableRow>{cols.map((c) => (
            <TableCell key={String(c.key)} align={c.num ? "right" : "left"} sx={{ fontWeight: 800, fontSize: 11.5, color: "#475569", textTransform: "uppercase", letterSpacing: 0.4, bgcolor: "#f8fafc", width: c.width }}>{c.label}</TableCell>
          ))}</TableRow>
        </TableHead>
        <TableBody>
          {rows.map((r, i) => (
            <TableRow key={r.id != null ? String(r.id) : i} hover onClick={onRow ? () => onRow(r) : undefined} sx={{ cursor: onRow ? "pointer" : "default" }}>
              {cols.map((c) => (
                <TableCell key={String(c.key)} align={c.num ? "right" : "left"}>
                  {c.render ? c.render(r) : String((r as any)[c.key] ?? "")}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Panel>
  );
}

export function TabPage({ tabs }: { tabs: { label: string; node: ReactNode }[] }) {
  const [t, setT] = useState(0);
  return (
    <Box>
      <Tabs value={t} onChange={(_, v) => setT(v)} variant="scrollable" scrollButtons={false}
        sx={{ borderBottom: `1px solid ${BORDER}`, mb: 1.5, minHeight: 40, "& .MuiTab-root": { minHeight: 40 } }}>
        {tabs.map((x) => <Tab key={x.label} label={x.label} />)}
      </Tabs>
      {tabs[t]?.node}
    </Box>
  );
}

export function pill(label: string, color: string) {
  return <Chip size="small" label={label} sx={{ bgcolor: `${color}22`, color, fontWeight: 700, height: 20 }} />;
}
