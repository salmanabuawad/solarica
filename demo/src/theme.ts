import { createTheme } from "@mui/material/styles";

// Solarica visual language — matched to the MVP (solarica.kortexd.com):
// dark-navy sidebar gradient, light-gray workspace, BLUE action accent, dense
// engineering tables. Amber is reserved for the brand mark only.
export const NAV_BG = "#0f172a";        // sidebar top — matches the MVP gradient
export const NAV_BG2 = "#1e293b";       // sidebar bottom / hover / active
export const NAV_TEXT = "#cbd5e1";      // slate-300
export const NAV_MUTED = "#94a3b8";     // slate-400 — section labels on the dark nav
export const BRAND = "#f59e0b";         // amber — logo mark only
export const ACCENT = "#2196f3";        // blue — UI accent (buttons, active, links)
export const WORKSPACE = "#f1f5f9";     // slate-100 — workspace
export const BORDER = "#e2e8f0";        // slate-200
export const INK = "#0f172a";

// Operational status palette (string commissioning pipeline + exceptions).
export const STATUS: Record<string, { label: string; color: string; bg: string }> = {
  new:               { label: "New", color: "#64748b", bg: "#f1f5f9" },
  avl:               { label: "AVL", color: "#94a3b8", bg: "#eef2f6" },
  optimizer:         { label: "Optimizers Installed", color: "#f59e0b", bg: "#fef3c7" },
  connection:        { label: "Panel Connected", color: "#2563eb", bg: "#dbeafe" },
  assembled:         { label: "String Assembled", color: "#7c3aed", bg: "#ede9fe" },
  cable_to_tga:      { label: "Connected to TGA", color: "#a855f7", bg: "#f3e8ff" },
  volt_checked:      { label: "Volt Tested", color: "#0891b2", bg: "#cffafe" },
  megger:            { label: "Megger Tested", color: "#0e7490", bg: "#cffafe" },
  iv_curve:          { label: "IV Curve Passed", color: "#059669", bg: "#d1fae5" },
  ready:             { label: "Ready for Commissioning", color: "#16a34a", bg: "#dcfce7" },
  tga_commissioning: { label: "Commissioned", color: "#15803d", bg: "#dcfce7" },
  error:             { label: "Error", color: "#ea580c", bg: "#ffedd5" },
  blocked:           { label: "Blocked", color: "#dc2626", bg: "#fee2e2" },
};

export const SEVERITY: Record<string, string> = {
  critical: "#dc2626", high: "#ea580c", medium: "#f59e0b", low: "#0891b2", info: "#64748b",
};

export const theme = createTheme({
  palette: {
    mode: "light",
    primary: { main: ACCENT },
    secondary: { main: BRAND },
    background: { default: WORKSPACE, paper: "#ffffff" },
    text: { primary: INK, secondary: "#475569" },
    divider: BORDER,
  },
  shape: { borderRadius: 8 },
  typography: {
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    fontSize: 13,
    h6: { fontWeight: 800, fontSize: 16 },
    subtitle2: { fontWeight: 700 },
    button: { textTransform: "none", fontWeight: 700 },
  },
  components: {
    MuiPaper: { styleOverrides: { root: { backgroundImage: "none", border: `1px solid ${BORDER}` } } },
    MuiButton: { defaultProps: { disableElevation: true }, styleOverrides: { root: { borderRadius: 8 } } },
    MuiChip: { styleOverrides: { root: { fontWeight: 700, borderRadius: 6 } } },
    MuiTableCell: { styleOverrides: { root: { padding: "6px 10px", fontSize: 12.5 } } },
    MuiTab: { styleOverrides: { root: { textTransform: "none", fontWeight: 700, minHeight: 42 } } },
  },
});
