import {
  LayoutDashboard,
  FolderKanban,
  ClipboardCheck,
  Package,
  Warehouse,
  Gauge,
  BarChart3,
  Shield,
  Users,
  Settings,
  ChevronsLeft,
  ChevronsRight,
} from 'lucide-react';
import { useAuth } from '../../contexts/AppContext';
import { useTabs } from '../../contexts/AppContext';
import { useTranslation } from 'react-i18next';
import { useDirection } from '../../hooks/useDirection';
import type { UserRole } from '../../lib/types';

// ── Props ──────────────────────────────────────────────────────

interface SidebarProps {
  collapsed: boolean;
  onToggleCollapse: () => void;
  mobileOpen: boolean;
  onMobileClose: () => void;
}

// ── Nav definition ─────────────────────────────────────────────

interface NavItem {
  id: string;
  type: string;
  labelKey: string;
  icon: React.ElementType;
  roles?: UserRole[];
}

interface NavSeparator {
  separator: true;
  roles?: UserRole[];
}

type NavEntry = NavItem | NavSeparator;

const NAV_ITEMS: NavEntry[] = [
  { id: 'dashboard', type: 'dashboard', labelKey: 'dashboard.overview', icon: LayoutDashboard },
  { id: 'projects', type: 'projects', labelKey: 'nav.projects', icon: FolderKanban, roles: ['admin', 'manager', 'owner'] },
  { id: 'tasks', type: 'tasks', labelKey: 'nav.tasks', icon: ClipboardCheck },
  { id: 'inventory', type: 'inventory', labelKey: 'nav.inventory', icon: Package, roles: ['admin', 'manager', 'warehouse'] },
  { id: 'warehouse', type: 'warehouse', labelKey: 'nav.warehouse', icon: Warehouse, roles: ['admin', 'manager', 'warehouse'] },
  { id: 'measurements', type: 'measurements', labelKey: 'nav.measurements', icon: Gauge },
  { id: 'reports', type: 'reports', labelKey: 'nav.reports', icon: BarChart3, roles: ['admin', 'manager', 'owner'] },
  { id: 'security', type: 'security', labelKey: 'nav.security', icon: Shield, roles: ['admin', 'manager'] },
  { separator: true, roles: ['admin', 'manager'] },
  { id: 'users', type: 'users', labelKey: 'roles.admin', icon: Users, roles: ['admin', 'manager'] },
  { id: 'settings', type: 'settings', labelKey: 'nav.settings', icon: Settings, roles: ['admin', 'manager'] },
];

/**
 * Technicians only see Dashboard, Tasks, Measurements.
 * Other roles see items based on the `roles` array (undefined = visible to all).
 */
function isVisibleForRole(entry: NavEntry, role: UserRole | undefined): boolean {
  if (!role) return false;

  if (role === 'technician') {
    if ('separator' in entry && entry.separator) return false;
    const item = entry as NavItem;
    return ['dashboard', 'tasks', 'measurements'].includes(item.id);
  }

  if ('separator' in entry && entry.separator) {
    return entry.roles ? entry.roles.includes(role) : true;
  }

  const item = entry as NavItem;
  if (!item.roles) return true;
  return item.roles.includes(role);
}

// ── Component ──────────────────────────────────────────────────

export default function Sidebar({ collapsed, onToggleCollapse, mobileOpen, onMobileClose }: SidebarProps) {
  const { user } = useAuth();
  const { activeTabId, openTab } = useTabs();
  const { t } = useTranslation();
  const dir = useDirection();
  const isRTL = dir === 'rtl';

  const role = user?.role;
  const visibleItems = NAV_ITEMS.filter((entry) => isVisibleForRole(entry, role));

  const handleNavClick = (item: NavItem) => {
    openTab({
      id: item.id,
      type: item.type,
      label: t(item.labelKey),
      icon: item.id,
    });
    onMobileClose();
  };

  const sidebarContent = (
    <div className="flex flex-col h-full">
      <nav className="sidebar-nav flex-1 py-2 overflow-y-auto">
        {visibleItems.map((entry, idx) => {
          if ('separator' in entry && entry.separator) {
            return <div key={`sep-${idx}`} className="mx-3 my-2 border-t border-white/10" />;
          }

          const item = entry as NavItem;
          const Icon = item.icon;
          const isActive = activeTabId === item.id;

          return (
            <button
              key={item.id}
              onClick={() => handleNavClick(item)}
              className={`
                nav-item flex items-center gap-3 w-full px-3 py-2.5 text-sm text-white/80
                transition-colors relative
                ${isActive
                  ? `nav-item-active bg-sidebar-active text-white ${isRTL ? 'border-r-[3px] border-primary' : 'border-l-[3px] border-primary'}`
                  : `hover:bg-sidebar-hover hover:text-white ${isRTL ? 'border-r-[3px] border-transparent' : 'border-l-[3px] border-transparent'}`
                }
                ${collapsed ? 'justify-center' : ''}
              `}
              title={collapsed ? t(item.labelKey) : undefined}
            >
              <Icon size={20} className="shrink-0" />
              {!collapsed && <span className="truncate">{t(item.labelKey)}</span>}
            </button>
          );
        })}
      </nav>

      {/* Collapse toggle - desktop only */}
      <button
        onClick={onToggleCollapse}
        className="hidden lg:flex items-center justify-center py-3 text-white/50 hover:text-white hover:bg-sidebar-hover transition-colors border-t border-white/10"
        aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
      >
        {collapsed
          ? (isRTL ? <ChevronsLeft size={18} /> : <ChevronsRight size={18} />)
          : (isRTL ? <ChevronsRight size={18} /> : <ChevronsLeft size={18} />)
        }
      </button>
    </div>
  );

  return (
    <>
      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={onMobileClose}
        />
      )}

      {/* Sidebar panel – uses insetInlineStart so it auto-flips in RTL */}
      <aside
        className={`
          fixed top-14 bottom-0 z-40 bg-sidebar transition-all duration-200
          ${collapsed && !mobileOpen ? 'w-14' : 'w-56'}
        `}
        style={{
          insetInlineStart: 0,
          insetInlineEnd: 'auto',
        }}
      >
        {sidebarContent}
      </aside>
    </>
  );
}
