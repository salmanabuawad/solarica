import { createContext, useCallback, useContext, useState } from 'react';
import type { ReactNode } from 'react';
import type { Tab } from '../lib/types';

// ── Constants ───────────────────────────────────────────────────

const MAX_TABS = 10;

const DEFAULT_TAB: Tab = {
  id: 'dashboard',
  type: 'dashboard',
  label: 'Dashboard',
  icon: 'home',
};

// ── Types ───────────────────────────────────────────────────────

interface TabContextValue {
  tabs: Tab[];
  activeTabId: string;
  openTab: (tab: Tab) => void;
  closeTab: (tabId: string) => void;
  setActiveTab: (tabId: string) => void;
}

// ── Context ─────────────────────────────────────────────────────

const TabContext = createContext<TabContextValue | undefined>(undefined);

// ── Provider ────────────────────────────────────────────────────

export function TabProvider({ children }: { children: ReactNode }) {
  const [tabs, setTabs] = useState<Tab[]>([DEFAULT_TAB]);
  const [activeTabId, setActiveTabId] = useState<string>(DEFAULT_TAB.id);

  const openTab = useCallback((tab: Tab) => {
    setTabs((prev) => {
      // If tab already exists, just activate it
      const existing = prev.find((t) => t.id === tab.id);
      if (existing) {
        setActiveTabId(tab.id);
        return prev;
      }

      // Enforce max tabs
      if (prev.length >= MAX_TABS) {
        return prev;
      }

      setActiveTabId(tab.id);
      return [...prev, tab];
    });
  }, []);

  const closeTab = useCallback(
    (tabId: string) => {
      // Never close the dashboard tab
      if (tabId === 'dashboard') return;

      setTabs((prev) => {
        const idx = prev.findIndex((t) => t.id === tabId);
        if (idx === -1) return prev;

        const next = prev.filter((t) => t.id !== tabId);

        // If closing the active tab, activate an adjacent one
        if (activeTabId === tabId) {
          const newActive =
            next[Math.min(idx, next.length - 1)]?.id ?? 'dashboard';
          setActiveTabId(newActive);
        }

        return next;
      });
    },
    [activeTabId],
  );

  const setActiveTab = useCallback(
    (tabId: string) => {
      setTabs((prev) => {
        if (prev.some((t) => t.id === tabId)) {
          setActiveTabId(tabId);
        }
        return prev;
      });
    },
    [],
  );

  const value: TabContextValue = {
    tabs,
    activeTabId,
    openTab,
    closeTab,
    setActiveTab,
  };

  return <TabContext.Provider value={value}>{children}</TabContext.Provider>;
}

// ── Hook ────────────────────────────────────────────────────────

export function useTabs(): TabContextValue {
  const ctx = useContext(TabContext);
  if (ctx === undefined) {
    throw new Error('useTabs must be used within a TabProvider');
  }
  return ctx;
}
