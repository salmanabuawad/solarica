import { useState, useCallback } from 'react';
import Header from './Header';
import Sidebar from './Sidebar';
import TabBar from './TabBar';
import { useTabs } from '../../contexts/AppContext';

/** Registry mapping tab type strings to lazy-loaded components. */
const TAB_COMPONENTS: Record<string, React.ComponentType> = {
  // Placeholder - real page components will be registered here.
  // Example:
  // dashboard: DashboardPage,
  // projects: ProjectsPage,
};

/**
 * Register a page component for a given tab type.
 * Call this from your page modules so Layout can render them.
 */
export function registerTabComponent(type: string, component: React.ComponentType) {
  TAB_COMPONENTS[type] = component;
}

function PlaceholderPage({ type }: { type: string }) {
  return (
    <div className="flex items-center justify-center h-full text-text-muted">
      <div className="text-center">
        <p className="text-lg font-medium capitalize">{type}</p>
        <p className="text-sm mt-1">This page is under construction.</p>
      </div>
    </div>
  );
}

export default function Layout() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const { tabs, activeTabId } = useTabs();

  const handleMenuToggle = useCallback(() => {
    setMobileOpen((prev) => !prev);
  }, []);

  const handleSidebarCollapse = useCallback(() => {
    setSidebarCollapsed((prev) => !prev);
  }, []);

  const handleMobileClose = useCallback(() => {
    setMobileOpen(false);
  }, []);

  // Find the active tab and its component
  const activeTab = tabs.find((t) => t.id === activeTabId);
  const ActiveComponent = activeTab ? TAB_COMPONENTS[activeTab.type] : undefined;

  return (
    <div className="min-h-screen bg-surface-alt">
      <Header onMenuToggle={handleMenuToggle} />

      <Sidebar
        collapsed={sidebarCollapsed}
        onToggleCollapse={handleSidebarCollapse}
        mobileOpen={mobileOpen}
        onMobileClose={handleMobileClose}
      />

      {/* Main content area */}
      <div
        className={`
          pt-14 transition-all duration-200
          ${sidebarCollapsed ? 'lg:pl-14' : 'lg:pl-56'}
        `}
      >
        <TabBar />

        <main className="p-4 min-h-[calc(100vh-3.5rem-2.5rem)]">
          {ActiveComponent ? (
            <ActiveComponent />
          ) : activeTab ? (
            <PlaceholderPage type={activeTab.type} />
          ) : (
            <div className="flex items-center justify-center h-[60vh] text-text-muted">
              <p>Select an item from the sidebar to get started.</p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
