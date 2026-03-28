import { useState, useRef, useEffect } from "react";
import { Routes, Route, Link, useNavigate, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  LayoutDashboard, FolderOpen, ShieldCheck,
  Package, FlaskConical, Sun, Settings, LogOut,
  ChevronRight, MonitorCheck, Type, Contrast, Palette,
  ChevronDown, MapPin, X, Languages, Plus,
} from "lucide-react";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { AppConfigProvider, useAppConfig } from "./contexts/AppConfigContext";
import { ProjectProvider, useProject } from "./contexts/ProjectContext";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";
import { DashboardPage } from "./pages/DashboardPage";
import { ProjectsPage } from "./pages/ProjectsPage";
import { ValidationRulesPage } from "./pages/ValidationRulesPage";
import { ProgressPage } from "./pages/ProgressPage";
import { InventoryPage } from "./pages/InventoryPage";
import { TestsPage } from "./pages/TestsPage";
import { IVCurvePage } from "./pages/IVCurvePage";
import { DevicePage } from "./pages/DevicePage";
import { SyncPage } from "./pages/SyncPage";
import { SettingsPage } from "./pages/SettingsPage";
import { MeasurementDetailPage } from "./pages/MeasurementDetailPage";
import { LANGUAGES } from "./i18n";
import type { SiteSummary } from "./api/client";

/* ── Nav item descriptor ─────────────────────────────────────────────────── */
interface NavItem {
  labelKey: string;
  icon: React.ReactNode;
  path?: string;
  children?: { labelKey: string; path: string }[];
}

const NAV_ITEMS: NavItem[] = [
  { labelKey: "nav.dashboard", icon: <LayoutDashboard size={18} />, path: "/" },
  {
    labelKey: "nav.projects",
    icon: <FolderOpen size={18} />,
    children: [
      { labelKey: "nav.sitesDesign", path: "/projects" },
      { labelKey: "nav.progress", path: "/progress" },
    ],
  },
  { labelKey: "nav.validationRules", icon: <ShieldCheck size={18} />, path: "/rules" },
  { labelKey: "nav.inventory", icon: <Package size={18} />, path: "/inventory" },
  {
    labelKey: "nav.measurements",
    icon: <FlaskConical size={18} />,
    children: [
      { labelKey: "nav.measurements", path: "/measurements" },
      { labelKey: "nav.ivcurve",      path: "/ivcurve" },
      { labelKey: "nav.sync",         path: "/sync" },
    ],
  },
  { labelKey: "nav.device", icon: <MonitorCheck size={18} />, path: "/device" },
];

const NAV_BOTTOM: NavItem[] = [
  { labelKey: "nav.settings", icon: <Settings size={18} />, path: "/settings" },
];

/* ── Sidebar item ─────────────────────────────────────────────────────────── */
function SidebarNavItem({ item }: { item: NavItem }) {
  const { t } = useTranslation();
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const isActive = item.path
    ? item.path === "/" ? location.pathname === "/" : location.pathname.startsWith(item.path)
    : item.children?.some((c) => location.pathname.startsWith(c.path)) ?? false;

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  if (item.path) {
    return (
      <Link to={item.path} title={t(item.labelKey)} style={{ textDecoration: "none" }}>
        <div className={`sidebar-item${isActive ? " active" : ""}`}>{item.icon}</div>
      </Link>
    );
  }

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <div
        className={`sidebar-item${isActive ? " active" : ""}`}
        title={t(item.labelKey)}
        onClick={() => setOpen((p) => !p)}
      >
        {item.icon}
        <ChevronRight size={10} style={{ position: "absolute", right: 3, bottom: 4, opacity: 0.6 }} />
      </div>
      {open && (
        <div className="sidebar-submenu">
          <div style={{ padding: "6px 16px 4px", fontSize: "var(--theme-font-size-xs)", color: "rgb(var(--theme-text-muted))", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em" }}>
            {t(item.labelKey)}
          </div>
          {item.children?.map((child) => (
            <Link key={child.path} to={child.path} style={{ textDecoration: "none" }} onClick={() => setOpen(false)}>
              <div className="sidebar-submenu-item">{t(child.labelKey)}</div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

/* ── Display settings popover ─────────────────────────────────────────────── */
function DisplaySettingsPopover({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const { theme, setTheme, fontSize, setFontSize, brightness, setBrightness, language, setLanguage } = useAppConfig();
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [onClose]);

  const row: React.CSSProperties = { display: "flex", alignItems: "center", gap: 8, marginBottom: 10 };
  const lbl: React.CSSProperties = { fontSize: "var(--theme-font-size-xs)", color: "rgb(var(--theme-text-muted))", minWidth: 80 };
  const grp: React.CSSProperties = { display: "flex", gap: 4, flexWrap: "wrap" };
  const btn = (active: boolean): React.CSSProperties => ({
    padding: "3px 10px", borderRadius: 6,
    border: `1px solid ${active ? "rgb(var(--theme-action-accent))" : "rgb(var(--theme-card-border))"}`,
    background: active ? "rgb(var(--theme-action-accent))" : "#fff",
    color: active ? "#fff" : "rgb(var(--theme-text-primary))",
    cursor: "pointer", fontSize: "var(--theme-font-size-xs)", fontWeight: active ? 600 : 400,
  });

  return (
    <div ref={ref} style={{ position: "absolute", top: 48, right: 8, width: 290, background: "#fff", border: "1px solid rgb(var(--theme-card-border))", borderRadius: 10, boxShadow: "0 8px 24px rgba(0,0,0,0.14)", padding: "14px 16px", zIndex: 200 }}>
      <div style={{ fontWeight: 600, marginBottom: 12, fontSize: "var(--theme-font-size-sm)" }}>{t("header.display")}</div>

      <div style={row}>
        <Palette size={14} style={{ color: "rgb(var(--theme-text-muted))", flexShrink: 0 }} />
        <span style={lbl}>{t("display.theme")}</span>
        <div style={grp}>
          {(["ocean", "mist"] as const).map((t_) => (
            <button key={t_} style={btn(theme === t_)} onClick={() => setTheme(t_)}>
              {t(`display.${t_}`)}
            </button>
          ))}
        </div>
      </div>

      <div style={row}>
        <Type size={14} style={{ color: "rgb(var(--theme-text-muted))", flexShrink: 0 }} />
        <span style={lbl}>{t("display.fontSize")}</span>
        <div style={grp}>
          {(["small", "normal", "large"] as const).map((f) => (
            <button key={f} style={btn(fontSize === f)} onClick={() => setFontSize(f)}>
              {t(`display.${f}`)}
            </button>
          ))}
        </div>
      </div>

      <div style={row}>
        <Contrast size={14} style={{ color: "rgb(var(--theme-text-muted))", flexShrink: 0 }} />
        <span style={lbl}>{t("display.brightness")}</span>
        <div style={grp}>
          {(["light", "dark", "contrast"] as const).map((b) => (
            <button key={b} style={btn(brightness === b)} onClick={() => setBrightness(b)}>
              {t(`display.${b}`)}
            </button>
          ))}
        </div>
      </div>

      <div style={row}>
        <Languages size={14} style={{ color: "rgb(var(--theme-text-muted))", flexShrink: 0 }} />
        <span style={lbl}>{t("display.language")}</span>
        <div style={grp}>
          {LANGUAGES.map((lang) => (
            <button key={lang.code} style={btn(language === lang.code)} onClick={() => setLanguage(lang.code)}>
              {lang.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ── Project selector dropdown ────────────────────────────────────────────── */
function ProjectSelector() {
  const { t } = useTranslation();
  const { sites, sitesLoading, selectedSite, selectSite } = useProject();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const pick = (site: SiteSummary | null) => { selectSite(site); setOpen(false); };
  const newProject = () => { selectSite(null); setOpen(false); navigate("/projects", { state: { newProject: true } }); };

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <button
        onClick={() => setOpen((p) => !p)}
        style={{
          display: "flex", alignItems: "center", gap: 6,
          background: "rgba(255,255,255,0.15)", border: "1px solid rgba(255,255,255,0.25)",
          borderRadius: 8, padding: "4px 10px", cursor: "pointer", color: "#fff",
          fontSize: "var(--theme-font-size-xs)", fontWeight: 600, minWidth: 160,
        }}
      >
        <MapPin size={13} />
        <span style={{ flex: 1, textAlign: "left", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 160 }}>
          {sitesLoading ? t("common.loading") : selectedSite ? selectedSite.site_name : t("header.selectProject")}
        </span>
        <ChevronDown size={13} />
      </button>

      {open && (
        <div style={{ position: "absolute", top: "calc(100% + 6px)", left: 0, minWidth: 260, maxWidth: 360, background: "#fff", border: "1px solid rgb(var(--theme-card-border))", borderRadius: 10, boxShadow: "0 8px 24px rgba(0,0,0,0.14)", zIndex: 300, overflow: "hidden" }}>
          <div style={{ padding: "8px 12px 6px", fontSize: "var(--theme-font-size-xs)", color: "rgb(var(--theme-text-muted))", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", borderBottom: "1px solid rgb(var(--theme-card-border))" }}>
            {t("nav.projects")}
          </div>

          <div
            onClick={() => pick(null)}
            style={{ padding: "9px 14px", cursor: "pointer", fontSize: "var(--theme-font-size-sm)", background: selectedSite === null ? "rgb(var(--theme-highlight))" : undefined, color: selectedSite === null ? "rgb(var(--theme-action-accent))" : "rgb(var(--theme-text-muted))", fontWeight: selectedSite === null ? 600 : 400 }}
          >
            {t("header.allProjects")}
          </div>

          {sites.length === 0 && !sitesLoading && (
            <div style={{ padding: "10px 14px", fontSize: "var(--theme-font-size-xs)", color: "rgb(var(--theme-text-muted))" }}>
              {t("header.noProjectsYet")}{" "}
              <Link to="/projects" style={{ color: "rgb(var(--theme-action-accent))" }} onClick={() => setOpen(false)}>
                {t("header.importSiteDesign")}
              </Link>
            </div>
          )}

          {sites.map((site) => (
            <div
              key={site.id}
              onClick={() => pick(site)}
              style={{ padding: "9px 14px", cursor: "pointer", fontSize: "var(--theme-font-size-sm)", background: selectedSite?.id === site.id ? "rgb(var(--theme-highlight))" : undefined, borderTop: "1px solid rgb(var(--theme-card-border))" }}
            >
              <div style={{ fontWeight: 600, color: selectedSite?.id === site.id ? "rgb(var(--theme-action-accent))" : "rgb(var(--theme-text-primary))" }}>
                {site.site_name}
              </div>
              <div style={{ fontSize: "var(--theme-font-size-xs)", color: "rgb(var(--theme-text-muted))", marginTop: 1 }}>
                {site.site_code}{site.country ? ` · ${site.country}` : ""}{site.plant_capacity_mw ? ` · ${site.plant_capacity_mw} MW` : ""}
              </div>
            </div>
          ))}

          <div
            onClick={newProject}
            style={{ padding: "9px 14px", cursor: "pointer", fontSize: "var(--theme-font-size-sm)", borderTop: "2px solid rgb(var(--theme-card-border))", display: "flex", alignItems: "center", gap: 6, color: "rgb(var(--theme-action-accent))", fontWeight: 600 }}
          >
            <Plus size={14} />
            {t("header.newProject")}
          </div>
        </div>
      )}
    </div>
  );
}

/* ── App shell ────────────────────────────────────────────────────────────── */
function AppShell() {
  const { t } = useTranslation();
  const { user, logout, isManager } = useAuth();
  const { selectedSite, selectSite } = useProject();
  const navigate = useNavigate();
  const [showDisplay, setShowDisplay] = useState(false);

  const handleLogout = () => { logout(); navigate("/login", { replace: true }); };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Header */}
      <header className="solarica-header" style={{ position: "relative", gap: 10 }}>
        <Sun size={20} color="#fff" strokeWidth={2.5} />
        <span style={{ fontWeight: 700, fontSize: "1rem", color: "#fff", letterSpacing: "0.02em", marginRight: 4 }}>
          Solarica
        </span>

        <ProjectSelector />

        {selectedSite && (
          <div style={{ display: "flex", alignItems: "center", gap: 4, background: "rgba(255,255,255,0.12)", borderRadius: 6, padding: "2px 8px 2px 10px" }}>
            <span style={{ fontSize: "var(--theme-font-size-xs)", color: "rgba(255,255,255,0.9)" }}>
              {selectedSite.site_code}
              {selectedSite.string_count > 0 && ` · ${selectedSite.string_count} ${t("header.strings")}`}
            </span>
            <button
              onClick={() => selectSite(null)}
              title={t("header.clearProjectFilter")}
              style={{ background: "none", border: "none", cursor: "pointer", color: "rgba(255,255,255,0.6)", padding: "0 2px", display: "flex", alignItems: "center" }}
            >
              <X size={12} />
            </button>
          </div>
        )}

        <span style={{ flex: 1 }} />

        <span style={{ color: "rgba(255,255,255,0.8)", fontSize: "var(--theme-font-size-xs)" }}>
          {user?.full_name}
          {isManager && (
            <span style={{ marginLeft: 6, background: "rgba(255,255,255,0.2)", color: "#fff", borderRadius: 999, padding: "1px 7px", fontSize: "0.7rem", fontWeight: 600 }}>
              {t("header.manager")}
            </span>
          )}
        </span>

        <button
          onClick={() => setShowDisplay((p) => !p)}
          title={t("header.display")}
          style={{ background: "rgba(255,255,255,0.15)", border: "none", borderRadius: 6, padding: "5px 7px", cursor: "pointer", color: "#fff", display: "flex", alignItems: "center" }}
        >
          <Palette size={15} />
        </button>

        <button
          onClick={handleLogout}
          title={t("header.signOut")}
          style={{ background: "rgba(255,255,255,0.15)", border: "none", borderRadius: 6, padding: "5px 7px", cursor: "pointer", color: "#fff", display: "flex", alignItems: "center", gap: 5 }}
        >
          <LogOut size={15} />
          <span style={{ fontSize: "var(--theme-font-size-xs)" }}>{t("header.signOut")}</span>
        </button>

        {showDisplay && <DisplaySettingsPopover onClose={() => setShowDisplay(false)} />}
      </header>

      {/* Body */}
      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        <nav className="solarica-sidebar">
          {NAV_ITEMS.map((item) => <SidebarNavItem key={item.labelKey} item={item} />)}
          <div style={{ flex: 1 }} />
          {NAV_BOTTOM.map((item) => <SidebarNavItem key={item.labelKey} item={item} />)}
        </nav>

        <main className="solarica-content">
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/projects" element={<ProjectsPage />} />
            <Route path="/rules" element={<ValidationRulesPage />} />
            <Route path="/progress" element={<ProgressPage />} />
            <Route path="/inventory" element={<InventoryPage />} />
            <Route path="/measurements" element={<TestsPage />} />
            <Route path="/ivcurve"      element={<IVCurvePage />} />
            <Route path="/measurements/:id" element={<MeasurementDetailPage />} />
            <Route path="/device" element={<DevicePage />} />
            <Route path="/sync" element={<SyncPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/tests" element={<TestsPage />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}

/* ── Root ─────────────────────────────────────────────────────────────────── */
export default function App() {
  return (
    <AppConfigProvider>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route
            path="/*"
            element={
              <ProtectedRoute>
                <ProjectProvider>
                  <AppShell />
                </ProjectProvider>
              </ProtectedRoute>
            }
          />
        </Routes>
      </AuthProvider>
    </AppConfigProvider>
  );
}
