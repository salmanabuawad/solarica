import { createContext, useCallback, useContext, useState } from 'react';
import type { ReactNode } from 'react';

// ── Types ────────────────────────────────────────────────────────

interface HelpContextValue {
  isOpen: boolean;
  topic: string | null;
  openHelp: (topic?: string) => void;
  closeHelp: () => void;
}

// ── Context ──────────────────────────────────────────────────────

const HelpContext = createContext<HelpContextValue | undefined>(undefined);

// ── Provider ─────────────────────────────────────────────────────

export function HelpProvider({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  const [topic, setTopic] = useState<string | null>(null);

  const openHelp = useCallback((t?: string) => {
    setTopic(t ?? null);
    setIsOpen(true);
  }, []);

  const closeHelp = useCallback(() => {
    setIsOpen(false);
    setTopic(null);
  }, []);

  return (
    <HelpContext.Provider value={{ isOpen, topic, openHelp, closeHelp }}>
      {children}
    </HelpContext.Provider>
  );
}

// ── Hook ─────────────────────────────────────────────────────────

export function useHelp() {
  const ctx = useContext(HelpContext);
  if (ctx === undefined) throw new Error('useHelp must be used within a HelpProvider');
  return ctx;
}
