/**
 * App.tsx — Solarica shell built on KortexdUI ui-base pattern.
 *   • h-12 navy header  (logo · title · settings · user menu)
 *   • 72px icon-only sidebar with fly-out submenus
 *   • Tabs bar (border-b-2 indicator, × close)
 *   • Full-height content area, no page scroll
 */
import { useState, useCallback, useRef, useEffect, lazy, Suspense } from 'react';
import {
  Sun, Settings, Home, LayoutDashboard, ClipboardCheck,
  Package, BarChart2, Shield, Database,
  X, Menu, Loader2,
  SlidersHorizontal, LogOut, User as UserIcon, Globe,
  Smartphone,
} from 'lucide-react';
import { useApp, LANGUAGES } from './contexts/AppContext';
import type { LanguageCode, LanguageOption } from './contexts/AppContext';
import { useTranslation } from 'react-i18next';
import { useDirection } from './hooks/useDirection';

/* ── Lazy pages ─────────────────────────────────────────────── */
const Login              = lazy(() => import('./pages/Login'));
const Dashboard          = lazy(() => import('./pages/Dashboard'));
const ProjectList        = lazy(() => import('./pages/projects/ProjectList'));
const ProjectDashboard   = lazy(() => import('./pages/projects/ProjectDashboard'));
const ProjectWizard      = lazy(() => import('./pages/projects/ProjectWizard'));
const TaskList           = lazy(() => import('./pages/tasks/TaskList'));
const TaskDetail         = lazy(() => import('./pages/tasks/TaskDetail'));
const TaskCreate         = lazy(() => import('./pages/tasks/TaskCreate'));
const MaterialList       = lazy(() => import('./pages/inventory/MaterialList'));
const WarehouseView      = lazy(() => import('./pages/inventory/WarehouseView'));
const MeasurementList    = lazy(() => import('./pages/measurements/MeasurementList'));
const UserManagement     = lazy(() => import('./pages/admin/UserManagement'));
const Settings_          = lazy(() => import('./pages/admin/Settings'));
const AuditLog_          = lazy(() => import('./pages/admin/AuditLog'));
const FieldConfigManager = lazy(() => import('./pages/admin/FieldConfigManager'));
const MobileHome         = lazy(() => import('./pages/mobile/MobileHome'));
const MobileTaskList     = lazy(() => import('./pages/mobile/MobileTaskList'));
const MobileTaskExecute  = lazy(() => import('./pages/mobile/MobileTaskExecute'));
const MobileWarehouseActions = lazy(() => import('./pages/mobile/MobileWarehouseActions'));
const MobileProjectList  = lazy(() => import('./pages/mobile/MobileProjectList'));
const MobileProjectDetail = lazy(() => import('./pages/mobile/MobileProjectDetail'));
const AnalyticsDashboard = lazy(() => import('./pages/analytics/AnalyticsDashboard'));
const SecurityDashboard  = lazy(() => import('./pages/security/SecurityDashboard'));
const DeviceRegistry     = lazy(() => import('./pages/security/DeviceRegistry'));
const VulnerabilityList  = lazy(() => import('./pages/security/VulnerabilityList'));
const DeviceInventoryList = lazy(() => import('./pages/devices/DeviceInventoryList'));
const SolarCatalogBrowser = lazy(() => import('./pages/devices/SolarCatalogBrowser'));

/* ── Loading fallback ───────────────────────────────────────── */
function TabFallback() {
  return (
    <div className="flex-1 flex items-center justify-center" style={{ background: 'rgb(var(--theme-content))' }}>
      <Loader2 className="w-8 h-8 animate-spin" style={{ color: 'rgb(var(--theme-tab-active))' }} />
    </div>
  );
}

/* ── Nav group definition ───────────────────────────────────── */
interface NavItem {
  label:     string;
  icon:      React.ReactNode;
  activeFor: string[];
  items:     { label: string; onClick: () => void }[];
}

/* ── Unsaved-changes modal ──────────────────────────────────── */
function UnsavedModal({ onConfirm, onCancel }: { onConfirm: () => void; onCancel: () => void }) {
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[500]" onClick={onCancel}>
      <div className="bg-white rounded-2xl shadow-2xl p-6 max-w-sm w-full mx-4" onClick={e => e.stopPropagation()}>
        <h3 className="text-base font-semibold text-gray-800 mb-2">Unsaved Changes</h3>
        <p className="text-gray-500 text-sm mb-5">You have unsaved changes. Leave anyway?</p>
        <div className="flex gap-3 justify-end">
          <button onClick={onCancel}  className="btn btn-cancel btn-md">Stay</button>
          <button onClick={onConfirm} className="btn btn-danger btn-md">Leave</button>
        </div>
      </div>
    </div>
  );
}

/* ── Language-change confirmation modal ─────────────────────── */
function LangConfirmModal({ lang, onConfirm, onCancel }: { lang: LanguageOption; onConfirm: () => void; onCancel: () => void }) {
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[500]" onClick={onCancel}>
      <div dir="ltr" className="bg-white rounded-2xl shadow-2xl p-6 max-w-sm w-full mx-4" onClick={e => e.stopPropagation()}>
        <h3 className="text-base font-semibold text-gray-800 mb-2">Change Language</h3>
        <p className="text-gray-500 text-sm mb-5">
          Switch to <strong>{lang.flag} {lang.nativeLabel}</strong>? The app will reload to apply the new language.
        </p>
        <div className="flex gap-3 justify-end">
          <button onClick={onCancel}  className="btn btn-cancel btn-md">Cancel</button>
          <button onClick={onConfirm} className="btn btn-primary btn-md">Confirm</button>
        </div>
      </div>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════ */
export default function App() {
  const { user, isAuthenticated, logout, brightness, setBrightness, fontSize, setFontSize, language, setLanguage, tabs, activeTabId, openTab, closeTab, hasUnsavedChanges } = useApp();
  const { t } = useTranslation();
  const dir = useDirection(); // applies dir + lang attrs to <html>; returns 'ltr'|'rtl'

  /* ── Language-change confirmation ── */
  const [pendingLang, setPendingLang] = useState<LanguageCode | null>(null);

  /* ── Mobile task navigation ── */
  const [mobileTaskId, setMobileTaskId] = useState<number | null>(null);

  /* ── Mobile project navigation ── */
  const [mobileProject, setMobileProject] = useState<import('./lib/types').Project | null>(null);

  /* ── Unsaved guard ── */
  const [showUnsaved, setShowUnsaved] = useState(false);
  const pendingNav = useRef<(() => void) | null>(null);
  const guardedNav = useCallback((action: () => void) => {
    if (hasUnsavedChanges.current) { pendingNav.current = action; setShowUnsaved(true); }
    else { action(); }
  }, [hasUnsavedChanges]);

  /* ── Menu state ── */
  const [sidebarOpen,  setSidebarOpen]  = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [openMenuId,   setOpenMenuId]   = useState<string | null>(null);
  const settingsRef = useRef<HTMLDivElement>(null);
  const userRef     = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const h = (e: MouseEvent) => {
      if (settingsRef.current && !settingsRef.current.contains(e.target as Node)) setSettingsOpen(false);
      if (userRef.current     && !userRef.current.contains(e.target as Node))     setUserMenuOpen(false);
    };
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, []);

  const closeAllMenus = useCallback(() => {
    setSidebarOpen(false); setOpenMenuId(null); setSettingsOpen(false); setUserMenuOpen(false);
  }, []);

  /* ── Tab helpers ── */
  function go(tab: Parameters<typeof openTab>[0]) {
    closeAllMenus();
    guardedNav(() => openTab(tab));
  }

  /* ── Nav groups ── */
  const NAV: NavItem[] = [
    {
      label: t('dashboard.overview'), icon: <LayoutDashboard className="h-5 w-5 shrink-0" />,
      activeFor: ['dashboard'],
      items: [{ label: t('dashboard.overview'), onClick: () => go({ id:'dashboard', type:'dashboard', label:t('dashboard.overview'), pinned:true }) }],
    },
    {
      label: t('nav.projects'), icon: <Home className="h-5 w-5 shrink-0" />,
      activeFor: ['projects','project','project-wizard','project-detail'],
      items: [
        { label: t('projects.list_title'), onClick: () => go({ id:'projects', type:'projects', label:t('projects.list_title'), pinned:true }) },
        { label: t('projects.create'),     onClick: () => go({ id:'project-wizard', type:'project-wizard', label:t('projects.create') }) },
      ],
    },
    {
      label: t('nav.tasks'), icon: <ClipboardCheck className="h-5 w-5 shrink-0" />,
      activeFor: ['tasks','task','task-detail','task-create'],
      items: [
        { label: t('tasks.list_title'), onClick: () => go({ id:'tasks', type:'tasks', label:t('tasks.list_title'), pinned:true }) },
        { label: t('tasks.create'),     onClick: () => go({ id:'task-create', type:'task-create', label:t('tasks.create') }) },
      ],
    },
    {
      label: t('nav.inventory'), icon: <Package className="h-5 w-5 shrink-0" />,
      activeFor: ['inventory','warehouse'],
      items: [
        { label: t('inventory.materials'), onClick: () => go({ id:'inventory', type:'inventory', label:t('inventory.materials'), pinned:true }) },
        { label: t('inventory.warehouse'), onClick: () => go({ id:'warehouse', type:'warehouse', label:t('inventory.warehouse'), pinned:true }) },
      ],
    },
    {
      label: t('nav.measurements'), icon: <BarChart2 className="h-5 w-5 shrink-0" />,
      activeFor: ['measurements','analytics'],
      items: [
        { label: t('nav.measurements'), onClick: () => go({ id:'measurements', type:'measurements', label:t('nav.measurements'), pinned:true }) },
        { label: t('nav.analytics', 'Analytics'), onClick: () => go({ id:'analytics', type:'analytics', label:t('nav.analytics', 'Analytics'), pinned:true }) },
      ],
    },
    {
      label: t('nav.mobile', 'Mobile'), icon: <Smartphone className="h-5 w-5 shrink-0" />,
      activeFor: ['mobile','mobile-tasks','mobile-task-execute','mobile-warehouse','mobile-projects'],
      items: [
        { label: t('mobile.projects', 'Projects'),   onClick: () => { setMobileProject(null); go({ id:'mobile-projects', type:'mobile-projects', label:t('mobile.projects', 'Projects'), pinned:true }); } },
        { label: t('mobile.tasks', 'Tasks'),         onClick: () => { setMobileTaskId(null); go({ id:'mobile-tasks', type:'mobile-tasks', label:t('mobile.tasks', 'Tasks'), pinned:true }); } },
        { label: t('mobile.warehouse', 'Warehouse'), onClick: () => go({ id:'mobile-warehouse', type:'mobile-warehouse', label:t('mobile.warehouse', 'Warehouse'), pinned:true }) },
      ],
    },
    {
      label: t('nav.security'), icon: <Shield className="h-5 w-5 shrink-0" />,
      activeFor: ['security','security-devices','security-vulnerabilities'],
      items: [
        { label: t('security.dashboard'),        onClick: () => go({ id:'security',                type:'security',                label:t('security.dashboard'), pinned:true }) },
        { label: t('security.devices'),          onClick: () => go({ id:'security-devices',        type:'security-devices',        label:t('security.devices') }) },
        { label: t('security.vulnerabilities'),  onClick: () => go({ id:'security-vulnerabilities',type:'security-vulnerabilities',label:t('security.vulnerabilities') }) },
      ],
    },
    {
      label: 'Devices', icon: <Database className="h-5 w-5 shrink-0" />,
      activeFor: ['device-inventory', 'solar-catalog'],
      items: [
        { label: 'Device Inventory', onClick: () => go({ id:'device-inventory', type:'device-inventory', label:'Device Inventory', pinned:true }) },
        { label: 'Solar Catalog',    onClick: () => go({ id:'solar-catalog',    type:'solar-catalog',    label:'Solar Catalog',    pinned:true }) },
      ],
    },
    {
      label: t('nav.admin'), icon: <Settings className="h-5 w-5 shrink-0" />,
      activeFor: ['users','settings','audit','field-config'],
      items: [
        { label: 'Users',            onClick: () => go({ id:'users',        type:'users',        label:'Users' }) },
        { label: t('nav.settings'), onClick: () => go({ id:'settings',     type:'settings',     label:t('nav.settings') }) },
        { label: t('nav.audit', 'Audit Log'), onClick: () => go({ id:'audit', type:'audit', label:t('nav.audit', 'Audit Log') }) },
        { label: 'Field Configuration', onClick: () => go({ id:'field-config', type:'field-config', label:'Field Configuration' }) },
      ],
    },
  ];

  /* ── Page renderer ── */
  const activeTab = tabs.find(t => t.id === activeTabId);
  function renderPage() {
    if (!activeTab) return <Suspense fallback={<TabFallback/>}><Dashboard /></Suspense>;
    switch (activeTab.type) {
      case 'dashboard':             return <Suspense fallback={<TabFallback/>}><Dashboard /></Suspense>;
      case 'projects':              return <Suspense fallback={<TabFallback/>}><ProjectList /></Suspense>;
      case 'project-wizard':        return <Suspense fallback={<TabFallback/>}><ProjectWizard onClose={() => closeTab(activeTab.id)} onCreated={(info) => { closeTab(activeTab.id); if (info?.id) openTab({ id: `project-${info.id}`, type: 'project', label: info.name || 'Project', projectId: String(info.id) }); }} /></Suspense>;
      case 'project':
      case 'project-detail':        return <Suspense fallback={<TabFallback/>}><ProjectDashboard projectId={String(activeTab.projectId||'')} /></Suspense>;
      case 'tasks':                 return <Suspense fallback={<TabFallback/>}><TaskList /></Suspense>;
      case 'task':
      case 'task-detail':           return <Suspense fallback={<TabFallback/>}><TaskDetail taskId={String(activeTab.projectId||'')} /></Suspense>;
      case 'task-create':           return <Suspense fallback={<TabFallback/>}><TaskCreate onClose={() => closeTab(activeTab.id)} /></Suspense>;
      case 'inventory':             return <Suspense fallback={<TabFallback/>}><MaterialList /></Suspense>;
      case 'warehouse':             return <Suspense fallback={<TabFallback/>}><WarehouseView /></Suspense>;
      case 'measurements':          return <Suspense fallback={<TabFallback/>}><MeasurementList /></Suspense>;
      case 'analytics':             return <Suspense fallback={<TabFallback/>}><AnalyticsDashboard /></Suspense>;
      case 'users':                 return <Suspense fallback={<TabFallback/>}><UserManagement /></Suspense>;
      case 'settings':              return <Suspense fallback={<TabFallback/>}><Settings_ /></Suspense>;
      case 'audit':                 return <Suspense fallback={<TabFallback/>}><AuditLog_ /></Suspense>;
      case 'field-config':          return <Suspense fallback={<TabFallback/>}><FieldConfigManager /></Suspense>;
      case 'mobile':                return <Suspense fallback={<TabFallback/>}><MobileHome role={user?.role || 'technician'} /></Suspense>;
      case 'mobile-tasks':
        return (
          <Suspense fallback={<TabFallback/>}>
            {mobileTaskId !== null
              ? <MobileTaskExecute taskId={mobileTaskId} onBack={() => setMobileTaskId(null)} />
              : <MobileTaskList onSelectTask={(id) => setMobileTaskId(id)} />
            }
          </Suspense>
        );
      case 'mobile-warehouse':      return <Suspense fallback={<TabFallback/>}><MobileWarehouseActions /></Suspense>;
      case 'mobile-projects':
        return (
          <Suspense fallback={<TabFallback/>}>
            {mobileProject !== null
              ? <MobileProjectDetail project={mobileProject} onBack={() => setMobileProject(null)} />
              : <MobileProjectList onSelectProject={(p) => setMobileProject(p)} />
            }
          </Suspense>
        );
      case 'security':              return <Suspense fallback={<TabFallback/>}><SecurityDashboard /></Suspense>;
      case 'security-devices':      return <Suspense fallback={<TabFallback/>}><DeviceRegistry /></Suspense>;
      case 'security-vulnerabilities': return <Suspense fallback={<TabFallback/>}><VulnerabilityList /></Suspense>;
      case 'device-inventory':       return <Suspense fallback={<TabFallback/>}><DeviceInventoryList /></Suspense>;
      case 'solar-catalog':          return <Suspense fallback={<TabFallback/>}><SolarCatalogBrowser /></Suspense>;
      default:                      return <Suspense fallback={<TabFallback/>}><Dashboard /></Suspense>;
    }
  }

  /* ── Auth guard ── */
  if (!isAuthenticated) {
    return <Suspense fallback={<TabFallback />}><Login /></Suspense>;
  }

  const isActive = (group: NavItem) => activeTab ? group.activeFor.includes(activeTab.type) : false;

  /* ══════════════════════════════════════════════════════════
     RENDER
  ══════════════════════════════════════════════════════════ */
  return (
    <div className="h-screen flex flex-col overflow-hidden bg-app-bg" onClick={closeAllMenus}>

      {/* ═══ HEADER ═══ — always LTR so logo stays on left, controls on right */}
      <header
        dir="ltr"
        className="shrink-0 h-12 flex items-center justify-between px-4 text-white shadow-md z-50"
        style={{ background: 'rgb(var(--theme-header))' }}
        onClick={e => e.stopPropagation()}
      >
        {/* Logo + title */}
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'rgba(255,255,255,0.15)' }}>
            <Sun className="h-5 w-5 text-yellow-300" />
          </div>
          <span className="font-bold text-sm hidden sm:inline tracking-wide">{t('app.title')}</span>
          <span className="hidden md:inline text-white/40 text-xs ms-1">{t('app.tagline')}</span>
        </div>

        {/* Right controls */}
        <div className="flex items-center gap-0.5">

          {/* Settings */}
          <div className="relative" ref={settingsRef}>
            <button
              onClick={() => { setSettingsOpen(v => !v); setUserMenuOpen(false); }}
              className={`p-2.5 rounded hover:bg-white/10 transition-colors ${settingsOpen ? 'bg-white/10' : 'opacity-75'}`}
              title="Appearance"
            >
              <SlidersHorizontal className="h-4 w-4" />
            </button>
            {settingsOpen && (
              <div className="absolute top-full mt-1 w-56 rounded-lg shadow-xl py-2 z-[100] border border-white/10"
                style={{ background: 'rgb(var(--theme-sidebar))', insetInlineEnd: 0 }}>
                {/* Brightness */}
                <div className="px-3 py-1.5 border-b border-white/10">
                  <span className="text-xs font-medium text-white/60">Brightness</span>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {(['light','normal','dark','contrast'] as const).map(b => (
                      <button key={b} onClick={() => { setBrightness(b); setSettingsOpen(false); }}
                        className={`flex-1 min-w-0 py-1 rounded text-xs ${brightness === b ? 'bg-white/25 text-white' : 'text-white/70 hover:bg-white/10'}`}>
                        {b}
                      </button>
                    ))}
                  </div>
                </div>
                {/* Font size */}
                <div className="px-3 py-1.5 border-b border-white/10">
                  <span className="text-xs font-medium text-white/60">Font Size</span>
                  <div className="flex gap-1 mt-1">
                    {(['small','normal','large'] as const).map(f => (
                      <button key={f} onClick={() => { setFontSize(f); setSettingsOpen(false); }}
                        className={`flex-1 py-1 rounded text-xs capitalize ${fontSize === f ? 'bg-white/25 text-white' : 'text-white/70 hover:bg-white/10'}`}>
                        {f}
                      </button>
                    ))}
                  </div>
                </div>
                {/* Language */}
                <div className="px-3 py-1.5">
                  <div className="flex items-center gap-1.5 mb-1">
                    <Globe className="h-3 w-3 text-white/60" />
                    <span className="text-xs font-medium text-white/60">Language</span>
                  </div>
                  <div className="flex flex-col gap-0.5">
                    {LANGUAGES.map(lang => (
                      <button
                        key={lang.code}
                        onClick={() => {
                          if (lang.code === language) { setSettingsOpen(false); return; }
                          setSettingsOpen(false);
                          setPendingLang(lang.code);
                        }}
                        className={`flex items-center gap-2 px-2 py-1 rounded text-xs text-left transition-colors
                          ${language === lang.code ? 'bg-white/25 text-white' : 'text-white/70 hover:bg-white/10'}`}
                      >
                        <span>{lang.flag}</span>
                        <span className="flex-1">{lang.nativeLabel}</span>
                        {language === lang.code && <span className="text-white/40">✓</span>}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* User */}
          <div className="relative" ref={userRef}>
            <button
              onClick={() => { setUserMenuOpen(v => !v); setSettingsOpen(false); }}
              className={`p-2.5 rounded hover:bg-white/10 transition-colors ${userMenuOpen ? 'bg-white/10' : 'opacity-75'}`}
              title="Account"
            >
              <UserIcon className="h-4 w-4" />
            </button>
            {userMenuOpen && (
              <div className="absolute top-full mt-1 w-48 rounded-lg shadow-xl py-2 z-[100] border border-white/10"
                style={{ background: 'rgb(var(--theme-sidebar))', insetInlineEnd: 0 }}>
                <div className="px-3 py-2 border-b border-white/10">
                  <p className="text-sm font-semibold text-white truncate">{user?.display_name || user?.username}</p>
                  <p className="text-xs text-white/60 capitalize">{user?.role}</p>
                </div>
                <button
                  onClick={() => { setUserMenuOpen(false); logout(); }}
                  className="w-full flex items-center justify-center gap-2 py-2 px-3 text-sm text-white/80 hover:bg-red-600/30 hover:text-white transition-colors rounded-b-lg"
                >
                  <LogOut className="h-4 w-4" /> {t('nav.logout')}
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* ═══ BODY ═══ */}
      <div className="flex-1 flex flex-row min-h-0">

        {/* Mobile hamburger */}
        <button
          onClick={e => { e.stopPropagation(); setSidebarOpen(v => !v); }}
          className="md:hidden fixed z-50 p-3 left-2 rounded-xl shadow-lg border border-white/20"
          style={{ top: '3.25rem', background: 'rgb(var(--theme-sidebar))' }}
        >
          <Menu className="h-5 w-5 text-white" />
        </button>

        {/* ── Sidebar — always dir=ltr so flyout always opens to the right of icons ── */}
        <div
          dir="ltr"
          className={`${sidebarOpen ? 'fixed inset-0 z-40 md:relative md:z-auto' : 'hidden md:flex'}
                       md:w-[72px] flex flex-col shrink-0 overflow-visible`}
          style={{ background: 'rgb(var(--theme-sidebar))', borderInlineEnd: '1px solid rgba(255,255,255,0.1)' }}
          onClick={e => e.stopPropagation()}
        >
          {sidebarOpen && (
            <button onClick={() => setSidebarOpen(false)}
              className="md:hidden absolute p-3 right-2 top-2 rounded-xl text-white"
              style={{ background: 'rgb(var(--theme-sidebar))' }}>
              <X className="h-5 w-5" />
            </button>
          )}

          <nav className="flex-1 p-1.5 space-y-0.5 overflow-visible mt-1">
            {NAV.map((group, gi) => (
              <div key={gi} className="relative">
                <button
                  onClick={() => {
                    if (group.items.length === 1) {
                      group.items[0].onClick();
                    } else {
                      setOpenMenuId(openMenuId === String(gi) ? null : String(gi));
                    }
                  }}
                  title={group.label}
                  className="w-full flex items-center justify-center p-2.5 rounded transition-all duration-150 text-white"
                  style={{
                    background: isActive(group) ? 'rgba(255,255,255,0.12)' : 'transparent',
                    borderInlineEnd: isActive(group) ? '3px solid rgb(var(--theme-sidebar-active-stripe))' : '3px solid transparent',
                  }}
                  onMouseEnter={e => { if (!isActive(group)) e.currentTarget.style.background = 'rgba(255,255,255,0.08)'; }}
                  onMouseLeave={e => { if (!isActive(group)) e.currentTarget.style.background = 'transparent'; }}
                >
                  {group.icon}
                </button>

                {/* Flyout — right-full in RTL (sidebar on right edge), left-full in LTR */}
                {openMenuId === String(gi) && (
                  <div dir={dir} className={`absolute top-0 w-52 rounded-lg shadow-xl py-2 z-[100] max-h-[70vh] overflow-y-auto border border-white/10 ${dir === 'rtl' ? 'right-full mr-1' : 'left-full ml-1'}`}
                    style={{ background: 'rgb(var(--theme-sidebar))' }}>
                    <div className="px-3 py-1 mb-1">
                      <span className="text-xs font-semibold text-white/50 uppercase tracking-wider">{group.label}</span>
                    </div>
                    {group.items.map((item, ii) => (
                      <button key={ii} onClick={item.onClick} className="btn-menu-item">{item.label}</button>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </nav>

          <div className="p-2 border-t border-white/10 flex justify-center">
            <Sun className="h-4 w-4 text-yellow-300/40" />
          </div>
        </div>

        {/* ── Content ── */}
        <div className="flex-1 flex flex-col min-w-0 min-h-0 overflow-hidden pt-10 md:pt-0" onClick={closeAllMenus}>

          {/* Tabs bar — always dir=ltr so tabs flow left-to-right in all languages */}
          <div dir="ltr" className="bg-app-tabs-bg border-b border-app-input-border shrink-0">
            <div className="px-2 py-1">
              <div className="flex items-center gap-0.5 overflow-x-auto scrollbar-hide min-h-[38px]">
                {tabs.map(tab => (
                  <div key={tab.id}
                    className={`flex items-center gap-1.5 px-3 py-1.5 border-b-2 transition-all duration-150 cursor-pointer flex-shrink-0 -mb-px
                      ${activeTabId === tab.id
                        ? 'border-blue-500 text-gray-800 font-semibold bg-white/60'
                        : 'border-transparent text-gray-500 hover:text-gray-700 hover:bg-white/40'}`}
                  >
                    <div className="flex items-center gap-1.5"
                      onClick={() => guardedNav(() => openTab({ ...tab }))}>
                      <span className="whitespace-nowrap text-xs">{tab.label}</span>
                    </div>
                    {!tab.pinned && (
                      <button
                        onClick={e => { e.stopPropagation(); closeTab(tab.id); }}
                        className="p-0.5 rounded text-gray-400 hover:bg-red-100 hover:text-red-600 transition-all"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Page content — dir follows selected language */}
          <div dir={dir} className="flex-1 overflow-hidden flex flex-col min-h-0" style={{ background: 'rgb(var(--theme-content))' }}>
            {renderPage()}
          </div>
        </div>
      </div>

      {/* Unsaved-changes modal */}
      {showUnsaved && (
        <UnsavedModal
          onConfirm={() => { setShowUnsaved(false); hasUnsavedChanges.current = false; pendingNav.current?.(); pendingNav.current = null; }}
          onCancel={()  => { setShowUnsaved(false); pendingNav.current = null; }}
        />
      )}

      {/* Language-change confirmation modal */}
      {pendingLang && (() => {
        const langOpt = LANGUAGES.find(l => l.code === pendingLang)!;
        return (
          <LangConfirmModal
            lang={langOpt}
            onConfirm={() => {
              setLanguage(pendingLang);
              setPendingLang(null);
              setTimeout(() => window.location.reload(), 150);
            }}
            onCancel={() => setPendingLang(null)}
          />
        );
      })()}
    </div>
  );
}
