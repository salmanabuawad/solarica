import { useMemo, useState } from "react";
import { AgGridReact } from "ag-grid-react";
import { AllCommunityModule, ModuleRegistry, themeQuartz, type ColDef } from "ag-grid-community";
import { Box, Chip, ToggleButton, ToggleButtonGroup } from "@mui/material";
import { PageHeader, Panel } from "../components/ui";
import { STATUS } from "../theme";
import { STRINGS, statusCounts, type StringRow } from "../data/catalog";
import { useDrawer } from "../components/AssetDrawer";

ModuleRegistry.registerModules([AllCommunityModule]);

const gridTheme = themeQuartz.withParams({
  accentColor: "#1e3a8a", headerBackgroundColor: "#0f172a", headerTextColor: "#ffffff",
  headerFontWeight: 700, fontSize: 12.5, rowHeight: 34, headerHeight: 38,
  borderColor: "#e2e8f0", oddRowBackgroundColor: "#f8fafc",
});

function badge(v: string) {
  const c = v === "pass" ? "#16a34a" : v === "fail" ? "#dc2626" : "#94a3b8";
  return <Chip size="small" label={v} sx={{ bgcolor: `${c}22`, color: c, fontWeight: 700, height: 20 }} />;
}

export default function DCLayer({ embedded = false }: { embedded?: boolean }) {
  const { open } = useDrawer();
  const [filter, setFilter] = useState<string>("all");
  const counts = useMemo(() => statusCounts(), []);

  const rows = useMemo(() => filter === "all" ? STRINGS
    : filter === "blocked" ? STRINGS.filter((s) => s.status === "blocked")
    : filter === "tested" ? STRINGS.filter((s) => ["volt_checked","megger","iv_curve","ready","tga_commissioning"].includes(s.status))
    : STRINGS.filter((s) => s.status === filter), [filter]);

  const cols: ColDef<StringRow>[] = [
    { field: "id", headerName: "String", width: 120, pinned: "left", cellStyle: { fontWeight: 700 } },
    { field: "row", headerName: "Row", width: 90 },
    { field: "inverter", headerName: "Inverter", width: 110 },
    { field: "modules", headerName: "Modules", width: 95, type: "numericColumn" },
    { field: "optimizers", headerName: "Optimizers", width: 110, type: "numericColumn" },
    { field: "voltage", headerName: "Voltage", width: 110, valueFormatter: (p) => p.value != null ? `${Number(p.value).toFixed(2)} V` : "—",
      cellStyle: (p) => ({ color: p.data && p.data.voltage != null ? (p.data.voltOk ? "#16a34a" : "#dc2626") : "#94a3b8", fontWeight: 700 }) },
    { field: "megger", headerName: "Megger", width: 110, cellRenderer: (p: any) => badge(p.value) },
    { field: "ivCurve", headerName: "IV Curve", width: 110, cellRenderer: (p: any) => badge(p.value) },
    { field: "status", headerName: "Status", width: 200, cellRenderer: (p: any) => {
        const s = STATUS[p.value] || STATUS.new; return <Chip size="small" label={s.label} sx={{ bgcolor: s.bg, color: s.color, fontWeight: 700, height: 22 }} />;
      } },
    { field: "tasks", headerName: "Tasks", width: 85, type: "numericColumn" },
    { field: "photos", headerName: "Photos", width: 85, type: "numericColumn" },
    { field: "blockers", headerName: "Blockers", width: 95, type: "numericColumn",
      cellStyle: (p) => ({ color: p.value > 0 ? "#dc2626" : "#94a3b8", fontWeight: p.value > 0 ? 800 : 400 }) },
  ];

  return (
    <Box>
      {!embedded && <PageHeader title="Construction · DC Layer" subtitle="String-level commissioning pipeline — click a row to open the asset drawer" />}
      <Box sx={{ mb: 1.5 }}>
        <ToggleButtonGroup size="small" exclusive value={filter} onChange={(_, v) => v && setFilter(v)}>
          <ToggleButton value="all" sx={{ fontSize: 12 }}>All {STRINGS.length}</ToggleButton>
          <ToggleButton value="optimizer" sx={{ fontSize: 12 }}>Optimizer {counts.optimizer || 0}</ToggleButton>
          <ToggleButton value="cable_to_tga" sx={{ fontSize: 12 }}>TGA {counts.cable_to_tga || 0}</ToggleButton>
          <ToggleButton value="tested" sx={{ fontSize: 12 }}>Tested</ToggleButton>
          <ToggleButton value="blocked" sx={{ fontSize: 12 }}>Blocked {counts.blocked || 0}</ToggleButton>
        </ToggleButtonGroup>
      </Box>
      <Panel sx={{ p: 0, overflow: "hidden" }}>
        <Box sx={{ height: embedded ? "calc(100vh - 240px)" : "calc(100vh - 210px)" }}>
          <AgGridReact<StringRow>
            theme={gridTheme}
            rowData={rows}
            columnDefs={cols}
            defaultColDef={{ sortable: true, filter: true, resizable: true }}
            getRowId={(p) => p.data.id}
            onRowClicked={(e) => e.data && open({ type: "string", data: e.data })}
            rowStyle={{ cursor: "pointer" }}
          />
        </Box>
      </Panel>
    </Box>
  );
}
