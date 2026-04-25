import { Suspense, lazy, startTransition, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { getProjects, getProject, getPlantInfo, getBlocks, getTrackers, getPiers, getPier, getPierStatuses, updatePierStatus, bulkUpdatePierStatus, createProject, getElectricalDevices, getCurrentUser, logout, type AuthUser } from "./api";
import Login from "./components/Login";
// LanguageSwitcher + PreferencesPanel are now rendered inside SettingsModal
// only; no direct imports needed here.
import SettingsModal from "./components/SettingsModal";
import StatusChangeModal from "./components/StatusChangeModal";
const UsersManager = lazy(() => import("./components/UsersManager"));
import { useFieldConfigs, applyFieldConfigs } from "./hooks/useFieldConfigs";
const FieldConfigManager = lazy(() => import("./components/FieldConfigManager"));
import SimpleGrid from "./components/SimpleGrid";
import StatusDashboard from "./components/StatusDashboard";
import LayerTogglePanel from "./components/LayerTogglePanel";
import PierModal from "./components/PierModal";
import TrackerModal from "./components/TrackerModal";
import SystemPanel from "./components/SystemPanel";
import { BusyOverlay, ConfirmModal, PromptModal } from "./components/Modals";
import SyncQueuePanel from "./components/SyncQueuePanel";
import { useResponsive } from "./hooks/useResponsive";
import { useOnlineStatus } from "./hooks/useOnlineStatus";
import { userPrefs } from "./userPrefs";

// MapLibre is our single map engine. Lazy-loaded so the initial bundle
// doesn't pay for it until the user opens the Map tab.
const SiteMapMapLibre = lazy(() => import("./components/SiteMapMapLibre"));

const STATUS_OPTIONS = ["New", "In Progress", "Implemented", "Approved", "Rejected", "Fixed"] as const;

// Shared style for the compact topbar icon buttons (buildings-manager
// look). Sized for mobile tap-target compliance.
const iconBtn: React.CSSProperties = {
  width: 36, height: 36,
  display: "inline-flex", alignItems: "center", justifyContent: "center",
  background: "#f1f5f9", border: "1px solid #e2e8f0", borderRadius: 10,
  color: "#334155", cursor: "pointer", padding: 0, lineHeight: 1,
};

function SlidersIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <line x1="4" y1="21" x2="4" y2="14" />
      <line x1="4" y1="10" x2="4" y2="3" />
      <line x1="12" y1="21" x2="12" y2="12" />
      <line x1="12" y1="8" x2="12" y2="3" />
      <line x1="20" y1="21" x2="20" y2="16" />
      <line x1="20" y1="12" x2="20" y2="3" />
      <line x1="1" y1="14" x2="7" y2="14" />
      <line x1="9" y1="8" x2="15" y2="8" />
      <line x1="17" y1="16" x2="23" y2="16" />
    </svg>
  );
}

function LogoutIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <polyline points="16 17 21 12 16 7" />
      <line x1="21" y1="12" x2="9" y2="12" />
    </svg>
  );
}

/** Render a pier status as a coloured pill with a status-specific icon.
 * Used as ag-grid `cellRenderer`.
 */
function StatusPill({ value }: { value?: string }) {
  const v = value || "New";
  const slug = v.toLowerCase().replace(/\s+/g, "-");
  return (
    <span className={`status-pill status-pill-${slug}`}>
      <StatusIcon status={v} />
      {v}
    </span>
  );
}

/** Tiny inline-SVG icon per status, with `currentColor` so it inherits
 * the pill's text colour. Kept out of the cellRenderer hot path so the
 * grid can reuse React instances. */
function StatusIcon({ status }: { status: string }) {
  const c = "currentColor";
  const common = { width: 13, height: 13, viewBox: "0 0 16 16", fill: "none", stroke: c, strokeWidth: 2, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  switch (status) {
    case "In Progress":
      // Clock (time-in-motion)
      return (
        <svg {...common}><circle cx="8" cy="8" r="6" /><path d="M8 5 v3 l2 2" /></svg>
      );
    case "Implemented":
      // Wrench / tool
      return (
        <svg {...common}><path d="M11 2 a3 3 0 0 0-2 5 l-5 5 a1.4 1.4 0 1 0 2 2 l5-5 a3 3 0 0 0 5-2 l-2 2 l-2 -2 z" /></svg>
      );
    case "Approved":
      // Filled check-circle
      return (
        <svg width={13} height={13} viewBox="0 0 16 16" fill={c}><path d="M8 0 a8 8 0 1 0 0 16 a8 8 0 0 0 0-16 zm4 5.7 l-5 5 l-3-3 l1.4-1.4 L7 8 l3.6-3.7 z" /></svg>
      );
    case "Rejected":
      // X-circle
      return (
        <svg {...common}><circle cx="8" cy="8" r="6.5" /><path d="M5.5 5.5 l5 5 M10.5 5.5 l-5 5" /></svg>
      );
    case "Fixed":
      // Shield-check
      return (
        <svg {...common}><path d="M8 1.5 l5.5 2 v4 c0 3.4-2.3 6.3-5.5 7-3.2-.7-5.5-3.6-5.5-7 v-4 z" /><path d="M5.5 8 l2 2 l3-3.5" /></svg>
      );
    case "New":
    default:
      // Empty circle (placeholder)
      return (
        <svg {...common}><circle cx="8" cy="8" r="5" /></svg>
      );
  }
}

/** Chip row above the grid listing active column filters. Click × to clear. */
function FilterChipBar({
  model,
  columnLabels,
  gridApiRef,
}: {
  model: Record<string, any>;
  columnLabels: Record<string, string>;
  gridApiRef: React.RefObject<any>;
}) {
  const entries = Object.entries(model);
  if (entries.length === 0) return null;

  const clearOne = (colId: string) => {
    const api = gridApiRef.current;
    if (!api) return;
    const next = { ...model };
    delete next[colId];
    api.setFilterModel(next);
  };
  const clearAll = () => gridApiRef.current?.setFilterModel(null);

  const fmt = (m: any): string => {
    if (!m) return "";
    if (m.filter != null) return String(m.filter);
    if (m.values) return `${(m.values as any[]).length} items`;
    if (m.condition1?.filter != null) return String(m.condition1.filter);
    return "…";
  };

  return (
    <div className="filter-chip-bar">
      {entries.map(([colId, m]) => (
        <span key={colId} className="filter-chip">
          <span className="filter-chip-label">{columnLabels[colId] || colId}</span>
          <span style={{ opacity: 0.75 }}>= {fmt(m)}</span>
          <button
            type="button"
            className="filter-chip-x"
            aria-label={`Clear ${colId} filter`}
            onClick={() => clearOne(colId)}
          >×</button>
        </span>
      ))}
      {entries.length > 1 && (
        <button type="button" className="filter-chip-clear-all" onClick={clearAll}>
          Clear all filters
        </button>
      )}
    </div>
  );
}

// Layer toggle defaults. `label` is a fallback only; the runtime value
// comes from the `layers.*` i18n keys each render (see the useMemo in
// AppMain) so the checkboxes switch language with the rest of the app.
const INITIAL_LAYERS = [
  { key: "row_labels",  label: "Row numbers", visible: true },
  { key: "piers",       label: "Piers",       visible: true },
  { key: "trackers",    label: "Trackers",    visible: true },
  // Single "Blocks" checkbox now drives BOTH the block fill/outline
  // AND the block-number HTML markers — keeps the checkbox row to
  // four entries so it stays on a single line on phones. The map
  // component still reads `blockLabels` for the marker visibility but
  // the App layer to map shim below mirrors `blocks` → `blockLabels`.
  { key: "blocks",      label: "Blocks",      visible: false },
  // Electrical devices (Inverters / DCCB) are loaded and rendered on
  // the map, but their checkboxes are hidden for now until the symbol
  // set and labelling are finalised. To re-expose them, re-add:
  //   { key: "inverters", label: "Inverters", visible: false },
  //   { key: "dccb",      label: "DCCB",      visible: false },
];
const LAYER_LABEL_KEYS: Record<string, string> = {
  row_labels:  "layers.rowNumbers",
  piers:       "layers.piers",
  trackers:    "layers.trackers",
  blocks:      "layers.blocks",
  blockLabels: "layers.blockLabels",  // unused in the toolbar; kept for compat
  inverters:   "layers.inverters",
  dccb:        "layers.dccb",
};

function getInitialProjectId() {
  const params = new URLSearchParams(window.location.search);
  return params.get("project") || "";
}

export default function App() {
  const [authUser, setAuthUser] = useState<AuthUser | null>(() => getCurrentUser());
  if (!authUser) {
    return <Login onLoggedIn={(u) => setAuthUser(u)} />;
  }
  return <AppMain authUser={authUser} />;
}

function AppMain({ authUser }: { authUser: AuthUser }) {
  const { t, i18n } = useTranslation();
  const { isMobile, isTablet } = useResponsive();
  // On phones AND tablets (iPad portrait, iPad landscape @ 1024 is treated
  // as desktop) we use a slide-out sidebar instead of a permanent one.
  const compact = isMobile || isTablet;
  const isRtl = i18n.language === "he" || i18n.language === "ar";
  const { online, pending, syncing, refreshPending } = useOnlineStatus();
  const [showSyncQueue, setShowSyncQueue] = useState(false);
  const [mode, setMode] = useState<"grid" | "map">("map");
  const [activeTab, setActiveTab] = useState<string>("details");
  const [projects, setProjects] = useState<any[]>([]);
  const [projectId, setProjectId] = useState(getInitialProjectId);
  const [project, setProject] = useState<any>(null);
  const [plantInfo, setPlantInfo] = useState<any>(null);
  const [blocks, setBlocks] = useState<any[]>([]);
  const [trackers, setTrackers] = useState<any[]>([]);
  const [piers, setPiers] = useState<any[]>([]);
  // Electrical devices extracted from the construction PDF (security
  // module). Tied to the Inverters + DCCB layer checkboxes.
  const [inverters, setInverters] = useState<any[]>([]);
  const [dccbs, setDccbs] = useState<any[]>([]);
  const [selectedPier, setSelectedPier] = useState<any>(null);
  const [selectedPierFull, setSelectedPierFull] = useState<any>(null);
  // Selected tracker for the read-only details modal (clicking a
  // tracker line / label / chip on the map opens it).
  const [selectedTracker, setSelectedTracker] = useState<any>(null);
  const [gridFilterBy, setGridFilterBy] = useState<"row" | "tracker">("row");
  const [gridFilterValue, setGridFilterValue] = useState("");
  const [pierStatuses, setPierStatuses] = useState<Record<string, string>>({});
  const [layers, setLayers] = useState(INITIAL_LAYERS);
  const [error, setError] = useState("");
  const [showNewProjectModal, setShowNewProjectModal] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [pierLabelThreshold, setPierLabelThreshold] = useState<number>(
    () => userPrefs.getPierLabelThreshold(),
  );
  const [pierDetailThreshold, setPierDetailThreshold] = useState<number>(
    () => userPrefs.getPierDetailThreshold(),
  );
  // How status is encoded on the map dot: "icon" (default — coloured
  // pier_type fill + status icon overlay), "color" (status colour fill,
  // no icon), or "both". Persisted in localStorage via userPrefs.
  const [pierStatusDisplay, setPierStatusDisplay] = useState<"icon" | "color" | "both">(
    () => userPrefs.getPierStatusDisplay(),
  );
  // Map label sampling — when the viewport shows a lot of rows /
  // trackers, render only every Nth label so they don't pile on top
  // of each other. mapLabelDenseThreshold = "show all if visible
  // count is below this".
  const [mapLabelStride, setMapLabelStride] = useState<number>(
    () => userPrefs.getMapLabelStride(),
  );
  const [mapLabelDenseThreshold, setMapLabelDenseThreshold] = useState<number>(
    () => userPrefs.getMapLabelDenseThreshold(),
  );
  // Shared pier selection across Grid and Map. `selectedPierCodes` is the
  // single source of truth — the grid checkboxes and map box-select both
  // feed it.
  const [selectedPierCodes, setSelectedPierCodes] = useState<Set<string>>(() => new Set());
  // Bulk status change UI state.
  const [bulkStatus, setBulkStatus] = useState<string>("");
  const [bulkConfirmOpen, setBulkConfirmOpen] = useState(false);
  // Active column filter model, driven by ag-grid via onFilterChanged.
  const [pierGridFilterModel, setPierGridFilterModel] = useState<Record<string, any>>({});
  const pierGridApiRef = useRef<any>(null);
  // Mobile / narrow-viewport sidebar toggle.
  const [sidebarOpen, setSidebarOpen] = useState(false);
  // Settings popup (language + theme/brightness/font size).
  const [settingsOpen, setSettingsOpen] = useState(false);
  // Pending status-change modal (triggered when a pier is flipped to
  // "Rejected" from the grid — inspector must attach a description and
  // optionally photos / a short video).
  const [statusEvent, setStatusEvent] = useState<null | { pierCode: string; status: string }>(null);

  // Persist user preferences.
  useEffect(() => { userPrefs.setPierLabelThreshold(pierLabelThreshold); }, [pierLabelThreshold]);
  useEffect(() => { userPrefs.setPierDetailThreshold(pierDetailThreshold); }, [pierDetailThreshold]);
  useEffect(() => { userPrefs.setPierStatusDisplay(pierStatusDisplay); }, [pierStatusDisplay]);
  useEffect(() => { userPrefs.setMapLabelStride(mapLabelStride); }, [mapLabelStride]);
  useEffect(() => { userPrefs.setMapLabelDenseThreshold(mapLabelDenseThreshold); }, [mapLabelDenseThreshold]);

  // Clear selection whenever the active project changes so we don't carry
  // stale pier codes between datasets.
  useEffect(() => {
    setSelectedPierCodes(new Set());
  }, [projectId]);

  useEffect(() => {
    let ignore = false;
    setBusy(t("app.loading"));
    getProjects()
      .then((items: any[]) => {
        if (ignore) return;
        setProjects(items);
        // If the URL's ?project=… points at a deleted / renamed project,
        // switch to the first real one AND update the URL so the stale
        // slug stops being fetched (prevents flood of 404s).
        if (items.length > 0 && !items.some((item: any) => item.project_id === projectId)) {
          const firstId = items[0].project_id;
          setProjectId(firstId);
          try {
            const params = new URLSearchParams(window.location.search);
            params.set("project", firstId);
            window.history.replaceState({}, "", `${window.location.pathname}?${params.toString()}`);
          } catch { /* ignore */ }
        }
      })
      .catch((e: any) => { if (!ignore) setError(String(e.message || e)); })
      .finally(() => { if (!ignore) setBusy(null); });
    return () => { ignore = true; };
    // Project list is fetched once on mount.  Re-fetching every time
    // `projectId` changes was causing /api/projects to fire twice on
    // first paint (mount + the inner setProjectId fallback). The
    // handleProjectChanged callback re-fetches explicitly when the
    // user creates / parses a project.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Load lightweight project metadata immediately on project change.
  // We wait until the projects list has loaded AND confirmed that
  // `projectId` is valid — otherwise a stale ?project=<oldname> URL
  // would fire a storm of 404s before the fallback switch.
  useEffect(() => {
    if (!projectId) return;
    if (projects.length > 0 && !projects.some((p: any) => p.project_id === projectId)) {
      // Invalid slug — wait for the fallback effect above to update projectId.
      return;
    }
    let ignore = false;
    setError("");
    setProject(null);
    setPlantInfo(null);
    setSelectedPier(null);
    setSelectedPierFull(null);
    setGridFilterValue("");

    setBusy(t("app.loading"));
    Promise.all([
      getProject(projectId).catch(() => null),
      getPlantInfo(projectId).catch(() => ({})),
    ]).then(([p, pi]) => {
      if (ignore) return;
      setProject(p);
      setPlantInfo(pi);
    })
    .catch((e: any) => { if (!ignore) setError(String(e.message || e)); })
    .finally(() => { if (!ignore) setBusy(null); });

    const params = new URLSearchParams(window.location.search);
    params.set("project", projectId);
    window.history.replaceState({}, "", `${window.location.pathname}?${params.toString()}`);
    return () => { ignore = true; };
    // `projects` was previously listed as a dep so the early-return
    // validation re-ran when the project list arrived. That made the
    // project + plant-info endpoints fire twice on every load — once
    // before /api/projects responded and once after. The other
    // useEffect (line ~290) already calls setProjectId() when the URL
    // slug is invalid, which triggers THIS effect via the projectId
    // dep with the corrected id, so removing `projects` is safe.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, refreshKey]);

  // Load heavy data (blocks, trackers, 25k piers) in the background after
  // project metadata loads. This way the data is ready by the time the user
  // clicks the Details tab — no waiting.
  useEffect(() => {
    if (!projectId || !project) return;
    let ignore = false;
    setBlocks([]);
    setTrackers([]);
    setPiers([]);
    setPierStatuses({});
    setInverters([]);
    setDccbs([]);

    setBusy(t("app.loading"));
    Promise.all([getBlocks(projectId), getTrackers(projectId), getPiers(projectId), getPierStatuses(projectId)])
      .then(([b, tr, pi, st]) => {
        if (ignore) return;
        setBlocks(b);
        setTrackers(tr);
        setPiers(pi);
        setPierStatuses(st || {});
      })
      .catch((e: any) => { if (!ignore) setError(String(e.message || e)); })
      .finally(() => { if (!ignore) setBusy(null); });

    // Fetch the electrical devices in parallel but don't block the
    // overall "loading" spinner — the core map still renders without
    // them. Failures are soft (empty arrays keep the layers blank).
    getElectricalDevices(projectId)
      .then((dev) => {
        if (ignore) return;
        setInverters(dev?.inverters ?? []);
        setDccbs(dev?.dccb ?? []);
      })
      .catch(() => { /* soft failure — layers stay empty */ });
    return () => { ignore = true; };
  }, [projectId, refreshKey, project]);

  function handleStatusChange(pierId: string, status: string) {
    if (!projectId) return;
    // Fast path for single-cell edits:
    //  1. Update ag-grid's internal row via the API — the cell repaints
    //     immediately without invalidating the 24 k-row memoized gridRows.
    //  2. Kick off the IndexedDB + server write without awaiting so the
    //     UI never blocks on the network round-trip.
    //  3. Use React's startTransition for the pierStatuses state update
    //     so the re-render (needed by map pier-status coloring) is run
    //     in a non-urgent slot and doesn't stall the input handler.
    const api = pierGridApiRef.current;
    try {
      const node = api?.getRowNode?.(pierId);
      if (node) node.setDataValue("status", status);
    } catch { /* grid may not be mounted (e.g. Map view) — ignore */ }

    updatePierStatus(projectId, pierId, status).catch((e: any) => setError(String(e.message || e)));

    startTransition(() => {
      setPierStatuses((prev) => {
        const next = { ...prev };
        if (status === "New") delete next[pierId];
        else next[pierId] = status;
        return next;
      });
    });
  }

  async function handleBulkApply() {
    if (!projectId || !bulkStatus || selectedPierCodes.size === 0) return;
    const codes = Array.from(selectedPierCodes);
    const status = bulkStatus;
    const total = codes.length;
    setBusy(`Updating ${total.toLocaleString()} piers…`);
    try {
      // ONE HTTP + one SQL statement instead of N PUTs. Previously 24 k
      // piers took minutes; now it's <1 s.
      await bulkUpdatePierStatus(projectId, codes, status);
      // Merge into the local statuses map.
      setPierStatuses((prev) => {
        const next = { ...prev };
        for (const code of codes) {
          if (status === "New") delete next[code];
          else next[code] = status;
        }
        return next;
      });
      // Clear the selection once the operation finishes.
      setSelectedPierCodes(new Set());
      setBulkStatus("");
    } catch (e: any) {
      setError(String(e.message || e));
    } finally {
      setBusy(null);
    }
  }

  // Stable callbacks for the map component to prevent re-render loops.
  const handleProjectChanged = useCallback((pid: string) => {
    getProjects().then((items: any[]) => {
      setProjects(items);
      if (pid && pid !== projectId) {
        setProjectId(pid);
      } else {
        setRefreshKey((k) => k + 1);
      }
    }).catch(() => {});
  }, [projectId]);

  const handleAreaSelect = useCallback((items: any[]) => {
    setSelectedPierCodes((prev) => {
      const next = new Set(prev);
      for (const it of items) if (it?.pier_code) next.add(it.pier_code);
      return next;
    });
  }, []);

  async function handlePierClick(p: any) {
    if (!projectId) return;
    setSelectedPier(p);
    try {
      const full = await getPier(projectId, p.pier_code);
      setSelectedPierFull(full);
    } catch (e: any) {
      setError(String(e.message || e));
    }
  }

  // Parse comma-separated filter values into a Set for fast lookup.
  const gridFilterSet = useMemo(() => {
    if (!gridFilterValue.trim()) return null;
    const vals = gridFilterValue.split(",").map((s) => s.trim().toUpperCase()).filter(Boolean);
    return vals.length > 0 ? new Set(vals) : null;
  }, [gridFilterValue]);

  // Filtered data based on row/tracker filter
  const filteredPiers = useMemo(() => {
    if (!gridFilterSet) return piers;
    if (gridFilterBy === "row") {
      return piers.filter((p: any) => gridFilterSet.has(String(p.row_num || "").toUpperCase()));
    }
    return piers.filter((p: any) => gridFilterSet.has(String(p.tracker_code || "").toUpperCase()));
  }, [piers, gridFilterBy, gridFilterSet]);

  const filteredTrackers = useMemo(() => {
    if (!gridFilterSet) return trackers;
    if (gridFilterBy === "row") {
      return trackers.filter((t: any) => gridFilterSet.has(String(t.row || "").toUpperCase()));
    }
    return trackers.filter((t: any) => gridFilterSet.has(String(t.tracker_code || "").toUpperCase()));
  }, [trackers, gridFilterBy, gridFilterSet]);

  // Grid rows: apply block/tracker filters, then optionally restrict to
  // whatever piers were visible in the map viewport when the user
  // last interacted with it.
  //
  // Row-number normalization: Ashalim drawings carry two parallel row
  // schemes — plain integers (full-length trackers, e.g. 145, 242) and
  // "S"-prefixed labels (short trackers at block edges, S1..S25). The
  // "S" was displaying as "S12" in the grid which users read as
  // incorrect. We strip the prefix on display and keep the short/full
  // distinction in a separate `row_type` column users can show via
  // Field Config.
  const gridRows = useMemo(() => {
    return filteredPiers.map((p: any) => {
      const raw = String(p.row_num ?? "").trim();
      const isShort = /^S\d+$/i.test(raw);
      const numeric = isShort ? raw.slice(1) : raw;
      return {
        ...p,
        row_num: numeric,           // what the user sees in the "Row" column
        row_num_raw: raw,            // preserved for any downstream code that needs the original label
        row_type: isShort ? "short" : (raw ? "full" : ""),
        status: pierStatuses[p.pier_code] || "New",
      };
    });
  }, [filteredPiers, pierStatuses]);

  const STATUS_BG: Record<string, string> = {
    "New": "#ffffff",
    "In Progress": "#fef3c7",
    "Implemented": "#d1fae5",
    "Approved": "#86efac",
    "Rejected": "#fecaca",
    "Fixed": "#bfdbfe",
  };
  const getRowStyle = (p: any) => {
    const bg = STATUS_BG[p.data?.status] || "#ffffff";
    return { backgroundColor: bg };
  };

  // Grouped nav: top-level project tabs + a "Configurations" section with children.
  interface NavItem { key: string; label: string; }
  interface NavGroup { id?: string; label?: string; items: NavItem[]; }
  const NAV_GROUPS: NavGroup[] = [
    { items: [
      { key: "details", label: t("nav.projectInfo") },
      { key: "mapgrid", label: t("nav.details") },
      { key: "devices", label: t("nav.devices") },
    ]},
    { id: "configurations", label: t("nav.configurations"), items: [
      { key: "config", label: t("nav.config") },
      ...(authUser.role === "admin" ? [
        { key: "fields", label: t("nav.fieldConfig") },
        { key: "users",  label: t("nav.users") },
      ] : []),
    ]},
  ];
  // Which collapsible nav groups are expanded.  Collapsed by default; a
  // group auto-expands if one of its children is the active tab.
  const [navOpen, setNavOpen] = useState<Record<string, boolean>>({});
  const isGroupOpen = (g: NavGroup) =>
    !g.id ? true
    : navOpen[g.id] === true
    || (navOpen[g.id] === undefined && g.items.some((i) => i.key === activeTab));

  // Field configs for each grid. Loaded once; used to reorder / hide /
  // relabel / pin columns before passing them into ag-grid.
  const piersFieldConfigs = useFieldConfigs("piers-list");
  const devicesBomFieldConfigs = useFieldConfigs("devices-bom");
  const devicesPierSpecsFieldConfigs = useFieldConfigs("devices-pier-specs");

  const Pill = ({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) => (
    <button
      onClick={onClick}
      style={{
        padding: compact ? "10px 16px" : "6px 14px",
        borderRadius: 10,
        border: "1px solid #e2e8f0",
        background: active ? "#0f172a" : "white",
        color: active ? "white" : "#0f172a",
        fontSize: compact ? 14 : 13,
        fontWeight: 500,
        cursor: "pointer",
      }}
    >
      {children}
    </button>
  );

  const closeMobileSidebar = () => setSidebarOpen(false);

  const sidebar = (
    <aside
      style={{
        width: compact ? "min(220px, 78vw)" : 200,
        flexShrink: 0,
        background: "linear-gradient(180deg,#0f172a 0%,#1e293b 100%)",
        color: "#e2e8f0",
        display: "flex",
        flexDirection: "column",
        position: compact ? "fixed" : "sticky",
        top: 0,
        bottom: 0,
        ...(isRtl ? { right: 0 } : { left: 0 }),
        height: "100vh",
        zIndex: compact ? 50 : 5,
        transform: compact
          ? (sidebarOpen ? "translateX(0)" : (isRtl ? "translateX(100%)" : "translateX(-100%)"))
          : "none",
        transition: "transform 0.22s ease",
        boxShadow: compact ? `${isRtl ? "-" : ""}4px 0 16px rgba(0,0,0,0.25)` : "none",
      }}
    >
      <div style={{
        // Comfortable breathing room above and below the wordmark
        // (16 px) so the logo doesn't kiss the top of the sidebar
        // or the navigation underneath.  Sides keep tight padding
        // so the logo still extends close to the sidebar edges.
        padding: "16px 6px",
        borderBottom: "1px solid rgba(255,255,255,0.08)",
        background: "#ffffff",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}>
        <img
          src="/logo.png"
          alt="Solarica"
          style={{
            display: "block",
            // `width: 100%` plus `max-width: none` overrides the
            // browser's default `max-width: 100%` on <img> so the
            // bitmap is up-scaled to fill the sidebar (152 → ~190 px
            // on desktop).  The image's natural aspect drives height.
            width: "100%",
            maxWidth: "none",
            height: "auto",
          }}
        />
      </div>
      <nav style={{ padding: "10px 8px", display: "flex", flexDirection: "column", gap: 2, flex: 1, overflowY: "auto" }}>
        {NAV_GROUPS.map((group, gi) => {
          const open = isGroupOpen(group);
          return (
          <div key={gi} style={{ display: "flex", flexDirection: "column", gap: 2, marginTop: group.label ? 10 : 0 }}>
            {group.label && (
              <button
                onClick={() => group.id && setNavOpen((prev) => ({ ...prev, [group.id!]: !open }))}
                style={{
                  display: "flex", alignItems: "center", gap: 6,
                  width: "100%", padding: "6px 14px 4px",
                  background: "transparent", border: "none", cursor: "pointer",
                  fontSize: 10, color: "#64748b", fontWeight: 700, letterSpacing: 1, textTransform: "uppercase",
                  textAlign: "left",
                }}
                aria-expanded={open}
              >
                <span style={{ width: 10, display: "inline-block", transition: "transform 0.15s ease", transform: open ? "rotate(90deg)" : "rotate(0)" }}>▸</span>
                {group.label}
              </button>
            )}
            {open && group.items.map((tab) => {
              const active = activeTab === tab.key;
              const indented = !!group.label;
              return (
                <button
                  key={tab.key}
                  onClick={() => { setActiveTab(tab.key); if (compact) closeMobileSidebar(); }}
                  style={{
                    textAlign: "left",
                    padding: indented ? "8px 14px 8px 26px" : "9px 14px",
                    borderRadius: 8,
                    border: "none",
                    cursor: "pointer",
                    background: active ? "rgba(255,255,255,0.10)" : "transparent",
                    color: active ? "#ffffff" : "#cbd5e1",
                    fontWeight: active ? 600 : 500,
                    fontSize: indented ? 12.5 : 13,
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    transition: "background 0.12s ease",
                  }}
                  onMouseEnter={(e) => { if (!active) (e.currentTarget.style.background = "rgba(255,255,255,0.06)"); }}
                  onMouseLeave={(e) => { if (!active) (e.currentTarget.style.background = "transparent"); }}
                >
                  <span style={{ width: 4, height: 18, borderRadius: 2, background: active ? "#38bdf8" : "transparent" }} />
                  {tab.label}
                </button>
              );
            })}
          </div>
          );
        })}
      </nav>
    </aside>
  );

  return (
    <div style={{ display: "flex", minHeight: "100vh", fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif", background: "#f8fafc" }}>
      {sidebar}
      {compact && sidebarOpen && (
        <div
          onClick={closeMobileSidebar}
          style={{ position: "fixed", inset: 0, background: "rgba(15,23,42,0.45)", zIndex: 40 }}
        />
      )}

      <main style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
        {/* Top bar: project selector + hamburger (mobile/tablet) */}
        <div style={{
          display: "flex", alignItems: "center", gap: 10, padding: compact ? "10px 16px" : "14px 20px",
          background: "#ffffff", borderBottom: "1px solid #e2e8f0", position: "sticky", top: 0, zIndex: 10,
        }}>
          {compact && (
            <button
              onClick={() => setSidebarOpen(true)}
              aria-label="Open menu"
              style={{ background: "#f1f5f9", border: "1px solid #e2e8f0", borderRadius: 8, padding: "6px 10px", fontSize: 18, cursor: "pointer", color: "#0f172a", minWidth: 44, minHeight: 44 }}
            >
              ☰
            </button>
          )}
          <select
            autoComplete="off"
            value={projectId}
            onChange={(e) => {
              const val = e.target.value;
              if (val === "__new__") { setShowNewProjectModal(true); return; }
              setProjectId(val);
            }}
            style={{
              minWidth: 0, flex: 1, maxWidth: 320,
              // Bigger, bolder project name on phones — at the small
              // viewport the picker is the most-used control on the
              // header bar and a 13 px label was hard to read.
              padding: compact ? "8px 12px" : "8px 10px",
              borderRadius: 8,
              border: "1px solid #cbd5e1",
              background: "#fff",
              fontSize: compact ? 16 : 13,
              fontWeight: compact ? 600 : 400,
              color: "#0f172a",
            }}
          >
            <optgroup label="Existing Projects">
              {!projects.length && <option value="">No projects</option>}
              {projects.map((item: any) => (
                <option key={item.project_id} value={item.project_id}>{item.project_id}</option>
              ))}
            </optgroup>
            <optgroup label="New">
              <option value="__new__">+ New Project…</option>
            </optgroup>
          </select>
          <div style={{ flex: 1 }} />

          {/* Online / offline pill — click opens sync queue */}
          <button
            onClick={() => setShowSyncQueue(true)}
            title={pending > 0 ? `${pending} pending sync` : online ? t("app.online") : t("app.offline")}
            aria-label={online ? t("app.online") : t("app.offline")}
            style={{
              height: 36,
              padding: "0 12px",
              display: "inline-flex", alignItems: "center", gap: 6,
              borderRadius: 10,
              border: `1px solid ${online ? "#bbf7d0" : "#fecaca"}`,
              background: online ? "#f0fdf4" : "#fef2f2",
              color: online ? "#166534" : "#991b1b",
              fontSize: 12, fontWeight: 600,
              cursor: "pointer",
              whiteSpace: "nowrap",
              position: "relative",
            }}
          >
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: online ? "#16a34a" : "#dc2626", display: "inline-block" }} />
            {syncing ? t("app.syncing") : online ? t("app.online") : t("app.offline")}
            {pending > 0 && (
              <span style={{
                background: online ? "#16a34a" : "#dc2626", color: "#fff",
                borderRadius: 999, padding: "0 6px", fontSize: 10, fontWeight: 700,
                marginInlineStart: 2,
              }}>{pending}</span>
            )}
          </button>

          {/* Settings / preferences — also shows current user + sign-out inside */}
          <button
            onClick={() => setSettingsOpen(true)}
            title={`${authUser.username} · ${authUser.role}`}
            aria-label={t("settings.title", "Settings")}
            style={iconBtn}
          >
            <SlidersIcon />
          </button>

          {/* Sign out */}
          <button
            onClick={logout}
            title={t("app.signOut")}
            aria-label={t("app.signOut")}
            style={iconBtn}
          >
            <LogoutIcon />
          </button>
        </div>

        <div style={{ padding: compact ? "12px 14px 24px" : "16px 24px 32px", flex: 1, minWidth: 0, boxSizing: "border-box", maxWidth: "100%" }}>
          {error && <div style={{ color: "#b91c1c", background: "#fee2e2", border: "1px solid #fecaca", borderRadius: 8, padding: "8px 12px", marginBottom: 10, fontSize: 13 }}>{error}</div>}

      {/* ---- TAB: Config (upload/parse + display settings) ---- */}
      <div style={{ display: activeTab === "config" ? "block" : "none" }}>
        <SystemPanel projectId={projectId} section="files" project={project} plantInfo={plantInfo} onProjectChanged={handleProjectChanged} onPlantInfoChanged={setPlantInfo} />
        <div style={{ marginTop: 14, border: "1px solid #e2e8f0", borderRadius: 16, padding: compact ? 12 : 16, background: "#fff" }}>
          <div style={{ fontWeight: 800, fontSize: 16, marginBottom: 10 }}>Display Settings</div>
          <div style={{ display: "flex", gap: 16, flexWrap: "wrap", alignItems: "center" }}>
            <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
              <label htmlFor="pierLabelThreshold" style={{ fontSize: 12, color: "#64748b" }}>Show pier codes when ≤</label>
              <input id="pierLabelThreshold" type="number" min={0} max={500} step={1} value={pierLabelThreshold} onChange={(e) => { const v = parseInt(e.target.value || "0", 10); setPierLabelThreshold(Number.isFinite(v) ? Math.max(0, Math.min(500, v)) : 0); }} style={{ width: 60, padding: "6px 8px", fontSize: 13, borderRadius: 8, border: "1px solid #d1d5db" }} />
              <span style={{ fontSize: 12, color: "#94a3b8" }}>piers visible</span>
            </div>
            <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
              <label htmlFor="pierDetailThreshold" style={{ fontSize: 12, color: "#64748b" }}>Show detail cards when ≤</label>
              <input id="pierDetailThreshold" type="number" min={0} max={50} step={1} value={pierDetailThreshold} onChange={(e) => { const v = parseInt(e.target.value || "0", 10); setPierDetailThreshold(Number.isFinite(v) ? Math.max(0, Math.min(50, v)) : 0); }} style={{ width: 60, padding: "6px 8px", fontSize: 13, borderRadius: 8, border: "1px solid #d1d5db" }} />
              <span style={{ fontSize: 12, color: "#94a3b8" }}>piers visible</span>
            </div>
            {/* Map label sampling: every Nth label when zoomed out,
                every label when fewer than threshold are in view. */}
            <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
              <label htmlFor="mapLabelStride" style={{ fontSize: 12, color: "#64748b" }}>
                {t("prefs.mapLabelStride", "Show every Nth row/tracker label")}
              </label>
              <input id="mapLabelStride" type="number" min={1} max={50} step={1} value={mapLabelStride}
                onChange={(e) => { const v = parseInt(e.target.value || "10", 10); setMapLabelStride(Number.isFinite(v) ? Math.max(1, Math.min(50, v)) : 10); }}
                style={{ width: 60, padding: "6px 8px", fontSize: 13, borderRadius: 8, border: "1px solid #d1d5db" }} />
            </div>
            <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
              <label htmlFor="mapLabelDenseThreshold" style={{ fontSize: 12, color: "#64748b" }}>
                {t("prefs.mapLabelDenseThreshold", "Show all when ≤")}
              </label>
              <input id="mapLabelDenseThreshold" type="number" min={1} max={500} step={1} value={mapLabelDenseThreshold}
                onChange={(e) => { const v = parseInt(e.target.value || "20", 10); setMapLabelDenseThreshold(Number.isFinite(v) ? Math.max(1, Math.min(500, v)) : 20); }}
                style={{ width: 60, padding: "6px 8px", fontSize: 13, borderRadius: 8, border: "1px solid #d1d5db" }} />
              <span style={{ fontSize: 12, color: "#94a3b8" }}>{t("prefs.mapLabelInView", "in view")}</span>
            </div>
            {/* How status is shown on the map dot — icon, colour, or both. */}
            <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
              <label htmlFor="pierStatusDisplay" style={{ fontSize: 12, color: "#64748b" }}>{t("prefs.pierStatusDisplay", "Show pier status as")}</label>
              <select
                id="pierStatusDisplay"
                value={pierStatusDisplay}
                onChange={(e) => {
                  const v = e.target.value as "icon" | "color" | "both";
                  setPierStatusDisplay(v);
                  userPrefs.setPierStatusDisplay(v);
                }}
                style={{ padding: "6px 8px", fontSize: 13, borderRadius: 8, border: "1px solid #d1d5db", background: "#fff" }}
              >
                <option value="icon">{t("prefs.pierStatusDisplay.icon", "Icon")}</option>
                <option value="color">{t("prefs.pierStatusDisplay.color", "Colour")}</option>
                <option value="both">{t("prefs.pierStatusDisplay.both", "Icon + Colour")}</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* ---- TAB: Project Info (metadata only) ---- */}
      <div style={{ display: activeTab === "details" ? "block" : "none" }}>
        <SystemPanel projectId={projectId} section="info" project={project} plantInfo={plantInfo} onProjectChanged={handleProjectChanged} onPlantInfoChanged={setPlantInfo} />
      </div>

      {/* ---- TAB: Details (Grid / Map) ---- */}
      <div style={{ display: activeTab === "mapgrid" ? "block" : "none" }}>
        {/* Status dashboard — total piers + breakdown by status. Lives
            above the Grid/Map toggle so the operator sees the rollout
            at a glance regardless of which view they're in. */}
        <StatusDashboard piers={piers} pierStatuses={pierStatuses} />

        {/* Grid/Map toggle + Export-to-Excel on the same row. The
            export button sits flush to the right edge so it's always
            visible regardless of which view (grid/map) is active. */}
        <div style={{ display: "flex", gap: 6, marginBottom: 8, alignItems: "center" }}>
          <Pill active={mode === "grid"} onClick={() => setMode("grid")}>{t("details.grid")}</Pill>
          <Pill active={mode === "map"} onClick={() => setMode("map")}>{t("details.map")}</Pill>
          <span style={{ flex: 1 }} />
          <button
            type="button"
            title={t("details.exportTooltip", "Export the current view to a CSV file Excel can open")}
            onClick={() => {
              const api = pierGridApiRef.current;
              if (!api || typeof api.exportDataAsCsv !== "function") return;
              const today = new Date().toISOString().slice(0, 10);
              api.exportDataAsCsv({
                fileName: `piers-${projectId || "export"}-${today}.csv`,
                onlySelectedAllPages: false,
              });
            }}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              fontSize: 13,
              fontWeight: 600,
              padding: "6px 12px",
              borderRadius: 8,
              border: "1px solid #16a34a",
              background: "#16a34a",
              color: "#fff",
              cursor: "pointer",
              boxShadow: "0 1px 2px rgba(15,23,42,0.08)",
              flexShrink: 0,
            }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M12 4v12" />
              <polyline points="6 10 12 16 18 10" />
              <path d="M5 20h14" />
            </svg>
            {t("details.exportExcel", "Export to Excel")}
          </button>
        </div>

        {/* Bulk status toolbar — visible when piers are selected. One
            row even on phones: "N piers" abbreviation, smaller font,
            no wrap (the row scrolls horizontally if absolutely needed). */}
        {selectedPierCodes.size > 0 && (
          <div style={{
            display: "flex", alignItems: "center", gap: 6, padding: "6px 10px",
            marginBottom: 8, borderRadius: 8, background: "#eff6ff",
            border: "1px solid #bfdbfe", flexWrap: "nowrap",
            overflowX: "auto", whiteSpace: "nowrap",
            WebkitOverflowScrolling: "touch",
          }}>
            <span style={{ fontSize: 12, fontWeight: 700, color: "#1e40af", flexShrink: 0 }}>
              {selectedPierCodes.size.toLocaleString()}&nbsp;pier{selectedPierCodes.size === 1 ? "" : "s"}
            </span>
            <select
              value={bulkStatus}
              onChange={(e) => setBulkStatus(e.target.value)}
              style={{ padding: "3px 6px", borderRadius: 6, border: "1px solid #93c5fd", fontSize: 12, flex: "0 1 auto", minWidth: 0 }}
            >
              <option value="">Set status…</option>
              {["New", "In Progress", "Implemented", "Approved", "Rejected", "Fixed"].map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
            <button
              disabled={!bulkStatus}
              onClick={() => setBulkConfirmOpen(true)}
              style={{
                padding: "3px 10px", borderRadius: 6, fontSize: 12, fontWeight: 600,
                border: "none", cursor: bulkStatus ? "pointer" : "default",
                background: bulkStatus ? "#2563eb" : "#93c5fd", color: "#fff", flexShrink: 0,
              }}
            >Apply</button>
            <button
              onClick={() => { setSelectedPierCodes(new Set()); setBulkStatus(""); }}
              style={{
                padding: "3px 8px", borderRadius: 6, fontSize: 12,
                border: "1px solid #bfdbfe", background: "#fff", color: "#64748b", cursor: "pointer", flexShrink: 0,
              }}
            >Clear</button>
          </div>
        )}

        {mode === "map" ? (
          <div>
            <div style={{ display: "flex", gap: 8, marginBottom: 8, flexWrap: "wrap", alignItems: "center" }}>
              <LayerTogglePanel
                layers={layers.map((l) => ({ ...l, label: t(LAYER_LABEL_KEYS[l.key] || l.label) }))}
                onChange={(key: string, visible: boolean) => setLayers((prev) => prev.map((l) => l.key === key ? { ...l, visible } : l))}
                inline
              />
              {gridFilterValue && (
                <span style={{ fontSize: 12, color: "#1d4ed8", fontWeight: 600 }}>
                  {gridFilterBy === "row" ? "Rows" : "Trackers"}: {gridFilterValue}
                </span>
              )}
              {gridFilterValue && (
                <button onClick={() => setGridFilterValue("")} style={{ fontSize: 12, background: "none", border: "none", cursor: "pointer", color: "#64748b" }}>Clear filter</button>
              )}
            </div>
            <div style={{
              // 100svh = "small" viewport height — the smallest the
              // viewport can be with ALL browser chrome visible.  Using
              // `svh` instead of `dvh` (or worse, `vh`) guarantees the
              // map fits even when iOS Safari's address+tab bars are
              // both showing and the user has selected piers (extra
              // bulk toolbar above the map).  Fallback to 100vh for
              // browsers that don't speak svh.
              height: compact
                ? "calc(100svh - 290px)"
                : "calc(100dvh - 200px)",
              minHeight: compact ? 240 : 380,
              maxHeight: "calc(100vh - 120px)",
              borderRadius: 12,
              overflow: "hidden",
              border: "1px solid #e2e8f0",
              // Mobile padding so the map's rounded corners don't bleed
              // off the screen edges; desktop gets none (ample room).
              margin: compact ? "0 6px" : 0,
              // Honour iOS safe-area inset so the bottom edge clears
              // the home indicator / tab bar.
              marginBottom: "env(safe-area-inset-bottom, 0px)",
              boxSizing: "border-box",
            }}>
              <Suspense fallback={<div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", fontSize: 13, color: "#64748b" }}>Loading map…</div>}>
                <SiteMapMapLibre
                  imageWidth={project?.base_image?.width || 1}
                  imageHeight={project?.base_image?.height || 1}
                  blocks={blocks}
                  trackers={filteredTrackers}
                  piers={filteredPiers}
                  inverters={inverters}
                  dccbs={dccbs}
                  pierStatuses={pierStatuses}
                  selectedBlock={null}
                  selectedTracker={gridFilterBy === "tracker" && gridFilterSet ? trackers.find((t: any) => gridFilterSet.has(String(t.tracker_code || "").toUpperCase())) : null}
                  selectedPier={selectedPier}
                  // Mirror "blocks" → "blockLabels" so the single
                  // Blocks checkbox in the layer panel drives both
                  // the block fill/outline AND the block-number
                  // markers on the map.
                  layers={(() => {
                    const blocksOn = layers.find((l) => l.key === "blocks")?.visible ?? false;
                    return [...layers, { key: "blockLabels", label: "Block labels", visible: blocksOn }];
                  })()}
                  onBlockClick={() => {}}
                  onTrackerClick={(t: any) => {
                    if (t && t.__row) {
                      // Row-label click — keeps the legacy filter behaviour.
                      setGridFilterBy("row");
                      setGridFilterValue(String(t.row || t.row_num || ""));
                      return;
                    }
                    // Tracker click on the map → open the details modal.
                    // If the click came from the chip (which only carries
                    // {tracker_code}), look up the full tracker object so
                    // the modal can render block / type / sheet / etc.
                    const code = t?.tracker_code || "";
                    const full = code ? trackers.find((x: any) => x.tracker_code === code) : null;
                    setSelectedTracker(full || t || null);
                  }}
                  onPierClick={handlePierClick}
                  onAreaSelect={handleAreaSelect}
                  bulkSelectedPierCodes={selectedPierCodes}
                  pierLabelThreshold={pierLabelThreshold}
                  pierDetailThreshold={pierDetailThreshold}
                  pierStatusDisplay={pierStatusDisplay}
                  mapLabelStride={mapLabelStride}
                  mapLabelDenseThreshold={mapLabelDenseThreshold}
                />
              </Suspense>
            </div>
            {selectedPierFull && (
              <PierModal selected={selectedPierFull} status={pierStatuses[selectedPier?.pier_code] || ""} onStatusChange={handleStatusChange} onClose={() => { setSelectedPier(null); setSelectedPierFull(null); }} />
            )}
            {selectedTracker && (
              <TrackerModal
                tracker={selectedTracker}
                pierStatuses={pierStatuses}
                piers={piers}
                onShowInGrid={(code) => {
                  setGridFilterBy("tracker");
                  setGridFilterValue(code);
                  setMode("grid");
                }}
                onClose={() => setSelectedTracker(null)}
              />
            )}
          </div>
        ) : (
          <div>
            <div style={{ display: "flex", gap: 8, marginBottom: 10, flexWrap: "wrap", alignItems: "center" }}>
              <span style={{ fontSize: 12, color: "#64748b", fontWeight: 600 }}>Filter by</span>
              <select value={gridFilterBy} onChange={(e) => { setGridFilterBy(e.target.value as any); setGridFilterValue(""); }} style={{ padding: "6px 10px", borderRadius: 8, border: "1px solid #d1d5db", fontSize: 13 }}>
                <option value="row">Rows</option>
                <option value="tracker">Trackers</option>
              </select>
              <input
                value={gridFilterValue}
                onChange={(e) => setGridFilterValue(e.target.value)}
                placeholder={gridFilterBy === "row" ? "e.g. 1, 2, 107" : "e.g. T0001, T0002"}
                style={{ flex: 1, minWidth: 140, padding: "6px 10px", borderRadius: 8, border: "1px solid #d1d5db", fontSize: 13 }}
              />
              {gridFilterValue && (
                <button onClick={() => setGridFilterValue("")} style={{ fontSize: 13, padding: "6px 10px", borderRadius: 8, border: "1px solid #d1d5db", background: "#fff", cursor: "pointer" }}>Clear</button>
              )}
              <span style={{ fontSize: 12, color: "#64748b" }}>{filteredPiers.length.toLocaleString()} piers</span>
            </div>
            <FilterChipBar
              model={pierGridFilterModel}
              columnLabels={{
                block_code: "Block",
                pier_code: "Pier",
                tracker_code: "Tracker",
                row_num: "Row",
                pier_type: "Pier Type",
                status: "Status",
                structure_code: "Structure",
                slope_band: "Slope",
                tracker_type_code: "Tracker Type",
              }}
              gridApiRef={pierGridApiRef}
            />
            <SimpleGrid
              rows={gridRows}
              columns={applyFieldConfigs(compact ? [
                // No dedicated `__select` column — ag-grid v33 renders
                // the row + header checkboxes inside the first column
                // automatically (rowSelection.checkboxes / headerCheckbox
                // wired up in SimpleGrid). Reserving a separate column
                // produced an extra empty header row above the real
                // headers (`ag-header-parent-hidden` group cell).
                { field: "pier_code", headerName: "Pier", headerTooltip: "Pier code", pinned: "left" },
                { field: "block_code", headerName: "Block", headerTooltip: "Block code" },
                { field: "tracker_code", headerName: "Tracker", headerTooltip: "Tracker code" },
                { field: "row_num", headerName: "Row", headerTooltip: "Row number" },
                { field: "pier_type", headerName: "Pier Type", headerTooltip: "Pier type" },
                {
                  field: "status", headerName: "Status", headerTooltip: "Click a cell to change status",
                  cellRenderer: StatusPill, cellClass: "status-cell",
                  editable: true, singleClickEdit: true,
                  cellEditor: "agSelectCellEditor",
                  cellEditorParams: { values: [...STATUS_OPTIONS] },
                },
              ] : [
                // No dedicated `__select` column — ag-grid v33 renders
                // the row + header checkboxes inside the first regular
                // column (pier_code) automatically. A reserved
                // selection column added an extra empty header row
                // (`ag-header-parent-hidden`) above the real headers.
                //
                // Widths are content-driven: a one-time DB scan measured
                // the actual max length of each field across every pier,
                // and the result was upserted into `field_configurations`
                // for grid_name='piers-list'.  The values below are the
                // React-side fallback (used only if the field-config API
                // is unreachable) and match the DB defaults exactly.
                // Formula: chars * 7 + 30 px (24 px L+R padding + ~6 px
                // for the sort / filter icon).
                { field: "pier_code",         headerName: "Pier",         headerTooltip: "Pier code",       pinned: "left", width: 84 },
                { field: "block_code",        headerName: "Block",        headerTooltip: "Block code",      width: 58 },
                { field: "tracker_code",      headerName: "Tracker",      headerTooltip: "Tracker code",    width: 72 },
                { field: "row_num",           headerName: "Row",          headerTooltip: "Row number",      width: 52 },
                { field: "pier_type",         headerName: "Type",         headerTooltip: "HAP / HMP / SAP / SAPE / SAPEND / SMP", width: 64 },
                { field: "structure_code",    headerName: "Struct.",      headerTooltip: "Structure code",  width: 72 },
                { field: "slope_band",        headerName: "Slope",        headerTooltip: "Slope band",      width: 64 },
                { field: "tracker_type_code", headerName: "Tracker Type", headerTooltip: "Tracker type code", width: 130 },
                { field: "row_type",          headerName: "Row Type",     headerTooltip: "full = regular row, short = S-prefixed short tracker at block edge", width: 76 },
                {
                  field: "status", headerName: "Status",
                  headerTooltip: "Click a cell to change status",
                  width: 92,
                  cellRenderer: StatusPill, cellClass: "status-cell",
                  editable: true, singleClickEdit: true,
                  cellEditor: "agSelectCellEditor",
                  cellEditorParams: { values: [...STATUS_OPTIONS] },
                  pinned: "right",
                },
              ], piersFieldConfigs)}
              height={compact ? "calc(100vh - 230px)" : "calc(100vh - 210px)"}
              enableQuickFilter
              quickFilterPlaceholder="Search piers..."
              getRowId={(p: any) => p.data?.pier_code}
              getRowStyle={getRowStyle}
              onRowClick={handlePierClick}
              rowSelection="multiple"
              selectedIds={selectedPierCodes}
              onSelectionChange={(ids: Set<string>) => setSelectedPierCodes(ids)}
              gridApiRef={pierGridApiRef}
              onFilterChanged={(model: Record<string, any>) => setPierGridFilterModel(model)}
              onCellValueChanged={(e: any) => {
                if (e?.colDef?.field !== "status") return;
                const code = e.data?.pier_code;
                const newStatus = e.newValue;
                if (!code || !newStatus || e.oldValue === newStatus) return;
                if (newStatus === "Rejected") {
                  // Open the description+attachments modal. The backend
                  // endpoint writes the history row AND updates the pier
                  // status — so we hold off on the optimistic update
                  // here and apply it on successful submit.
                  setStatusEvent({ pierCode: code, status: newStatus });
                  return;
                }
                handleStatusChange(code, newStatus);
              }}
            />
            {selectedPierFull && (
              <PierModal selected={selectedPierFull} status={pierStatuses[selectedPier?.pier_code] || ""} onStatusChange={handleStatusChange} onClose={() => { setSelectedPier(null); setSelectedPierFull(null); }} />
            )}
          </div>
        )}
      </div>

      {/* ---- TAB: Devices ---- */}
      <div style={{ display: activeTab === "devices" ? "block" : "none" }}>
        {project?.electrical ? (() => {
          const e = project.electrical;
          const bom: any[] = (e.bill_of_materials || []).map((item: any, i: number) => {
            const nameParts = (item.name || "").split(",").map((s: string) => s.trim());
            const rowType = nameParts.length >= 3 ? nameParts.slice(2).join(", ").replace(/ - XTR.*$/, "") : "";
            return { ...item, id: i, device_type: `${item.module_count}M-${item.pier_count}P ${rowType}`.trim() };
          });
          const pierSpecRows: any[] = (e.pier_type_specs || []).flatMap((spec: any) =>
            (spec.zones || []).map((z: any, zi: number) => ({
              id: `${spec.pier_type}-${zi}`,
              pier_type: spec.pier_type,
              pier_type_full: spec.pier_type_full,
              zone: z.zone,
              size: z.size,
              part_no: z.part_no,
            }))
          );
          return (
            <div style={{ display: "grid", gap: 14 }}>
              {/* Summary cards */}
              <div style={{ display: "grid", gridTemplateColumns: compact ? "1fr 1fr" : "repeat(4, 1fr)", gap: "8px 20px", fontSize: 13 }}>
                {[
                  ["Inverters", e.inverters],
                  ["DCCB", e.dccb?.toLocaleString?.() ?? e.dccb],
                  ["String Groups", e.string_groups],
                  ["Total Strings", e.total_strings?.toLocaleString?.() ?? e.total_strings],
                  ["Total Modules", e.total_modules?.toLocaleString?.() ?? e.total_modules],
                  ["Output (MW)", e.total_output_mw],
                  ["Module Power (W)", e.module_capacity_w],
                  ["Modules/String", e.modules_per_string],
                ].map(([label, val]) => (
                  <div key={String(label)}>
                    <div style={{ fontSize: 11, color: "#64748b", marginBottom: 2 }}>{label}</div>
                    <div style={{ fontWeight: 600, fontSize: 14 }}>{val ?? "-"}</div>
                  </div>
                ))}
              </div>

              {/* BOM ag-grid */}
              {bom.length > 0 && (
                <div>
                  <div style={{ fontSize: 12, fontWeight: 700, color: "#475569", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 6, borderBottom: "1px solid #e2e8f0", paddingBottom: 3 }}>Bill of Materials</div>
                  <SimpleGrid
                    rows={bom}
                    columns={applyFieldConfigs([
                      { field: "part_no", headerName: "Part No", maxWidth: 180 },
                      { field: "device_type", headerName: "Device Type", maxWidth: 220 },
                      { field: "name", headerName: "Name" },
                      { field: "qty", headerName: "Qty", maxWidth: 80, type: "numericColumn" },
                      { field: "module_count", headerName: "Modules", maxWidth: 100, type: "numericColumn" },
                      { field: "pier_count", headerName: "Piers", maxWidth: 80, type: "numericColumn" },
                    ], devicesBomFieldConfigs)}
                    height={Math.min(400, 56 + bom.length * 42)}
                    getRowId={(p: any) => String(p.data?.id)}
                    enableQuickFilter
                    quickFilterPlaceholder="Search devices..."
                  />
                </div>
              )}

              {/* Pier Type Specs ag-grid */}
              {pierSpecRows.length > 0 && (
                <div>
                  <div style={{ fontSize: 12, fontWeight: 700, color: "#475569", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 6, borderBottom: "1px solid #e2e8f0", paddingBottom: 3 }}>Pier Type Specifications</div>
                  <SimpleGrid
                    rows={pierSpecRows}
                    columns={applyFieldConfigs([
                      { field: "pier_type", headerName: "Type", maxWidth: 100 },
                      { field: "pier_type_full", headerName: "Full Name", maxWidth: 220 },
                      { field: "zone", headerName: "Zone" },
                      { field: "size", headerName: "Size", maxWidth: 150 },
                      { field: "part_no", headerName: "Part No", maxWidth: 120 },
                    ], devicesPierSpecsFieldConfigs)}
                    height={Math.min(400, 56 + pierSpecRows.length * 42)}
                    getRowId={(p: any) => String(p.data?.id)}
                  />
                </div>
              )}
            </div>
          );
        })() : (
          <div style={{ fontSize: 12, color: "#64748b" }}>No electrical metadata available. Parse a project first.</div>
        )}
      </div>

      {/* ---- TAB: Field Config (admin only) ---- */}
      {/* Admin tabs are conditionally rendered (not just hidden via
          display:none) so their internal data fetch only fires when
          the tab is actually opened. Previously these mounted on
          first paint and each fired /api/field-configs and /api/users
          immediately, contributing to the visible blink. */}
      {authUser.role === "admin" && activeTab === "fields" && (
        <div>
          <Suspense fallback={<div style={{ padding: 16, fontSize: 13, color: "#64748b" }}>{t("app.loading")}</div>}>
            <FieldConfigManager />
          </Suspense>
        </div>
      )}

      {/* ---- TAB: Users (admin only) ---- */}
      {authUser.role === "admin" && activeTab === "users" && (
        <div>
          <Suspense fallback={<div style={{ padding: 16, fontSize: 13, color: "#64748b" }}>{t("app.loading")}</div>}>
            <UsersManager />
          </Suspense>
        </div>
      )}
        </div> {/* /content padding */}
      </main>

      {showNewProjectModal && (
        <PromptModal
          title="New Project"
          message={online ? "Enter a project id (e.g. ashalim4):" : "Creating a project requires an internet connection."}
          placeholder="project_id"
          confirmLabel="Create"
          onCancel={() => setShowNewProjectModal(false)}
          onConfirm={async (id) => {
            setShowNewProjectModal(false);
            if (!online) {
              setError("Cannot create a project while offline.");
              return;
            }
            try {
              setBusy(`Creating project ${id}…`);
              await createProject({ project_id: id });
              const items = await getProjects();
              setProjects(items);
              setProjectId(id);
              setMode("system");
            } catch (err: any) {
              setError(String(err.message || err));
            } finally {
              setBusy(null);
            }
          }}
        />
      )}
      {bulkConfirmOpen && (
        <ConfirmModal
          title="Change status for selected piers"
          message={`Change the status of ${selectedPierCodes.size.toLocaleString()} pier${selectedPierCodes.size === 1 ? "" : "s"} to "${bulkStatus}"?`}
          confirmLabel="Apply"
          danger
          onCancel={() => setBulkConfirmOpen(false)}
          onConfirm={async () => {
            setBulkConfirmOpen(false);
            await handleBulkApply();
          }}
        />
      )}
      {showSyncQueue && (
        <SyncQueuePanel
          online={online}
          onClose={() => setShowSyncQueue(false)}
          onChanged={() => { refreshPending(); }}
        />
      )}
      {busy && <BusyOverlay message={busy} />}
      {settingsOpen && <SettingsModal onClose={() => setSettingsOpen(false)} />}
      {statusEvent && projectId && (
        <StatusChangeModal
          projectId={projectId}
          pierCode={statusEvent.pierCode}
          newStatus={statusEvent.status}
          onCancel={() => setStatusEvent(null)}
          onSubmitted={() => {
            // Backend already wrote both the event + the pier status —
            // just fold it into our local status map so the grid + map
            // reflect the change.
            setPierStatuses((prev) => ({ ...prev, [statusEvent.pierCode]: statusEvent.status }));
            setStatusEvent(null);
          }}
        />
      )}
    </div>
  );
}
