import { useMemo } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  Box, Select, MenuItem, InputBase, Button, Tooltip, Divider,
} from "@mui/material";
import MapOutlined from "@mui/icons-material/MapOutlined";
import EngineeringOutlined from "@mui/icons-material/EngineeringOutlined";
import ConstructionOutlined from "@mui/icons-material/ConstructionOutlined";
import ReportProblemOutlined from "@mui/icons-material/ReportProblemOutlined";
import TaskAltOutlined from "@mui/icons-material/TaskAltOutlined";
import BadgeOutlined from "@mui/icons-material/BadgeOutlined";
import BuildOutlined from "@mui/icons-material/BuildOutlined";
import Inventory2Outlined from "@mui/icons-material/Inventory2Outlined";
import VerifiedOutlined from "@mui/icons-material/VerifiedOutlined";
import BoltOutlined from "@mui/icons-material/BoltOutlined";
import HandymanOutlined from "@mui/icons-material/HandymanOutlined";
import SecurityOutlined from "@mui/icons-material/SecurityOutlined";
import HubOutlined from "@mui/icons-material/HubOutlined";
import SearchOutlined from "@mui/icons-material/SearchOutlined";
import FileDownloadOutlined from "@mui/icons-material/FileDownloadOutlined";
import { NAV_BG, NAV_BG2, NAV_TEXT, NAV_MUTED, ACCENT, BORDER, WORKSPACE } from "../theme";
import { ROLES, modulesForRole, type ModuleDef } from "../data/catalog";

const ICONS: Record<string, any> = {
  map: MapOutlined, engineering: EngineeringOutlined, construction: ConstructionOutlined,
  report: ReportProblemOutlined, task: TaskAltOutlined, badge: BadgeOutlined, build: BuildOutlined,
  inventory: Inventory2Outlined, verified: VerifiedOutlined, bolt: BoltOutlined,
  handyman: HandymanOutlined, security: SecurityOutlined, hub: HubOutlined,
};
const NAV_W = 250;

export default function AppShell({ role, setRole }: { role: string; setRole: (r: string) => void }) {
  const nav = useNavigate();
  const loc = useLocation();
  const active = loc.pathname.split("/")[1] || "twin";
  const mods = useMemo(() => modulesForRole(role), [role]);

  // Group modules by their section header.
  const groups = useMemo(() => {
    const g: Record<string, ModuleDef[]> = {};
    for (const m of mods) (g[m.group] ||= []).push(m);
    return g;
  }, [mods]);

  return (
    <Box sx={{ minHeight: "100vh", bgcolor: WORKSPACE, pr: `${NAV_W}px` }}>
      {/* Top bar */}
      <Box sx={{
        position: "fixed", top: 0, left: 0, right: NAV_W, height: 52, zIndex: 30,
        bgcolor: "#fff", borderBottom: `1px solid ${BORDER}`, display: "flex", alignItems: "center", gap: 1.5, px: 2,
      }}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 0.8, mr: 1 }}>
          <img src="/logo.png" alt="Solarica" style={{ height: 26, display: "block" }} />
          <Box sx={{ fontSize: 10, color: "#94a3b8", fontWeight: 700 }}>V2</Box>
        </Box>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1, bgcolor: WORKSPACE, border: `1px solid ${BORDER}`, borderRadius: 2, px: 1, height: 32, width: 280 }}>
          <SearchOutlined sx={{ fontSize: 18, color: "#94a3b8" }} />
          <InputBase placeholder="Search assets, strings, work orders…" sx={{ fontSize: 13, flex: 1 }} />
        </Box>
        <Box sx={{ flex: 1 }} />
        <Box sx={{ fontSize: 12, color: "#64748b", fontWeight: 700 }}>BHK · Execution Twin</Box>
        <Divider orientation="vertical" flexItem sx={{ my: 1.2 }} />
        <Box sx={{ fontSize: 11, color: "#94a3b8" }}>Role</Box>
        <Select size="small" value={role} onChange={(e) => { const r = e.target.value as string; setRole(r); const home = ROLES.find((x) => x.id === r)?.home; if (home) nav(`/${home}`); }}
          sx={{ minWidth: 210, height: 32, fontSize: 12.5, fontWeight: 700 }}>
          {ROLES.map((r) => <MenuItem key={r.id} value={r.id} sx={{ fontSize: 12.5 }}>{r.label}</MenuItem>)}
        </Select>
        <Tooltip title="Export current view">
          <Button size="small" variant="outlined" startIcon={<FileDownloadOutlined />} sx={{ height: 32 }}>Export</Button>
        </Tooltip>
      </Box>

      {/* Right navigation */}
      <Box sx={{
        position: "fixed", top: 0, right: 0, bottom: 0, width: NAV_W,
        background: `linear-gradient(180deg, ${NAV_BG} 0%, ${NAV_BG2} 100%)`, color: NAV_TEXT,
        display: "flex", flexDirection: "column", zIndex: 40, overflowY: "auto",
      }}>
        <Box sx={{ px: 1, py: 1.5, bgcolor: "#fff", borderBottom: `1px solid ${NAV_BG2}`, display: "flex", justifyContent: "center" }}>
          <img src="/logo.png" alt="Solarica" style={{ width: "92%", maxWidth: "none", height: "auto", display: "block" }} />
        </Box>
        <Box sx={{ py: 1, flex: 1 }}>
          {Object.entries(groups).map(([group, items]) => (
            <Box key={group} sx={{ mb: 0.5 }}>
              <Box sx={{ px: 2, pt: 1.2, pb: 0.4, fontSize: 10, letterSpacing: 1.2, color: NAV_MUTED, fontWeight: 800, textTransform: "uppercase" }}>{group}</Box>
              {items.map((m) => {
                const Icon = ICONS[m.icon] || MapOutlined;
                const on = active === m.id;
                return (
                  <Box key={m.id} onClick={() => nav(`/${m.id}`)} sx={{
                    display: "flex", alignItems: "center", gap: 1.2, px: 2, py: 0.9, cursor: "pointer",
                    color: on ? "#fff" : NAV_TEXT,
                    bgcolor: on ? NAV_BG2 : "transparent",
                    borderRight: on ? `3px solid ${ACCENT}` : "3px solid transparent",
                    "&:hover": { bgcolor: NAV_BG2 },
                  }}>
                    <Icon sx={{ fontSize: 19, color: on ? ACCENT : NAV_MUTED }} />
                    <Box sx={{ fontSize: 13, fontWeight: on ? 700 : 600 }}>{m.label}</Box>
                  </Box>
                );
              })}
            </Box>
          ))}
        </Box>
        <Box sx={{ px: 2, py: 1.2, borderTop: `1px solid ${NAV_BG2}`, fontSize: 10.5, color: NAV_MUTED, display: "flex", justifyContent: "space-between" }}>
          <span>Design → EPL → Build → QA → Ops</span><span style={{ color: "#16a34a" }}>● live</span>
        </Box>
      </Box>

      {/* Workspace */}
      <Box sx={{ pt: "52px", minHeight: "100vh" }}>
        <Box sx={{ p: 2 }}><Outlet /></Box>
      </Box>
    </Box>
  );
}
