import { useRef, useEffect } from 'react';
import {
  X,
  LayoutDashboard,
  FolderKanban,
  ClipboardCheck,
  Package,
  Warehouse,
  Gauge,
  BarChart3,
  Users,
  Settings,
  FileText,
} from 'lucide-react';
import { useTabs } from '../../contexts/AppContext';

/** Maps tab icon string IDs to Lucide icon components. */
const ICON_MAP: Record<string, React.ElementType> = {
  dashboard: LayoutDashboard,
  home: LayoutDashboard,
  projects: FolderKanban,
  tasks: ClipboardCheck,
  inventory: Package,
  warehouse: Warehouse,
  measurements: Gauge,
  reports: BarChart3,
  users: Users,
  settings: Settings,
};

export default function TabBar() {
  const { tabs, activeTabId, setActiveTab, closeTab } = useTabs();
  const activeRef = useRef<HTMLDivElement>(null);

  // Scroll active tab into view when it changes
  useEffect(() => {
    activeRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'nearest' });
  }, [activeTabId]);

  if (tabs.length === 0) return null;

  return (
    <div
      className="flex items-center bg-surface border-b border-border h-10 overflow-x-auto scrollbar-thin"
      role="tablist"
    >
      {tabs.map((tab) => {
        const isActive = tab.id === activeTabId;
        const isDashboard = tab.id === 'dashboard';
        const Icon = (typeof tab.icon === 'string' && ICON_MAP[tab.icon as string]) || FileText;

        return (
          <div
            key={tab.id}
            ref={isActive ? activeRef : undefined}
            className={`
              inline-flex items-center gap-1.5 px-3 py-1.5 text-sm cursor-pointer shrink-0 select-none
              border-r border-border
              ${isActive
                ? 'border-b-2 border-b-primary text-primary font-medium bg-white'
                : 'text-text-secondary hover:text-text-primary bg-surface-alt hover:bg-white/80'
              }
            `}
            onClick={() => setActiveTab(tab.id)}
            role="tab"
            aria-selected={isActive}
          >
            <Icon size={15} className="shrink-0" />
            <span className="truncate max-w-[130px]">{tab.label}</span>

            {!isDashboard && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  closeTab(tab.id);
                }}
                className="p-0.5 ml-1 rounded hover:bg-danger-light hover:text-danger transition-colors"
                aria-label={`Close ${tab.label}`}
              >
                <X size={13} />
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}
