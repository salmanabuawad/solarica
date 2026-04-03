import { createContext, useContext, useState, useCallback, useEffect, useRef } from 'react';
import type { ReactNode } from 'react';
import { CheckCircle, XCircle, AlertTriangle, Info, X } from 'lucide-react';

// ── Types ───────────────────────────────────────────────────────

export type ToastType = 'success' | 'error' | 'warning' | 'info';

export interface ToastItem {
  id: string;
  type: ToastType;
  message: string;
  duration: number; // ms, 0 = persistent
}

interface ToastContextValue {
  toast: (type: ToastType, message: string, duration?: number) => void;
  dismiss: (id: string) => void;
}

// ── Constants ───────────────────────────────────────────────────

const DEFAULT_DURATIONS: Record<ToastType, number> = {
  success: 3000,
  info: 5000,
  warning: 5000,
  error: 0, // persistent until dismissed
};

const TOAST_STYLES: Record<ToastType, { bg: string; icon: React.ElementType; iconColor: string }> = {
  success: { bg: 'bg-success-light border-success', icon: CheckCircle, iconColor: 'text-success' },
  error: { bg: 'bg-danger-light border-danger', icon: XCircle, iconColor: 'text-danger' },
  warning: { bg: 'bg-warning-light border-warning', icon: AlertTriangle, iconColor: 'text-warning' },
  info: { bg: 'bg-info-light border-info', icon: Info, iconColor: 'text-info' },
};

// ── Context ─────────────────────────────────────────────────────

const ToastContext = createContext<ToastContextValue | undefined>(undefined);

// ── Single toast entry ──────────────────────────────────────────

function ToastEntry({ item, onDismiss }: { item: ToastItem; onDismiss: (id: string) => void }) {
  const style = TOAST_STYLES[item.type];
  const Icon = style.icon;
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => {
    if (item.duration > 0) {
      timerRef.current = setTimeout(() => onDismiss(item.id), item.duration);
    }
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [item.id, item.duration, onDismiss]);

  return (
    <div
      className={`
        flex items-start gap-3 px-4 py-3 rounded-lg border-l-4 shadow-lg
        ${style.bg} text-text-primary
        min-w-[280px] max-w-[420px]
      `}
      role="alert"
    >
      <Icon size={20} className={`shrink-0 mt-0.5 ${style.iconColor}`} />
      <p className="flex-1 text-sm">{item.message}</p>
      <button
        onClick={() => onDismiss(item.id)}
        className="shrink-0 p-0.5 rounded opacity-60 hover:opacity-100 transition-opacity"
        aria-label="Dismiss"
      >
        <X size={14} />
      </button>
    </div>
  );
}

// ── Provider ────────────────────────────────────────────────────

let toastCounter = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const toast = useCallback((type: ToastType, message: string, duration?: number) => {
    const id = `toast-${++toastCounter}`;
    const dur = duration ?? DEFAULT_DURATIONS[type];
    setToasts((prev) => [...prev, { id, type, message, duration: dur }]);
  }, []);

  return (
    <ToastContext.Provider value={{ toast, dismiss }}>
      {children}

      {/* Toast container - fixed bottom (start side) */}
      {toasts.length > 0 && (
        <div className="toast-container fixed bottom-4 z-[9999] flex flex-col gap-2 ltr:right-4 rtl:left-4" style={{ insetInlineEnd: '1rem' }}>
          {toasts.map((item) => (
            <ToastEntry key={item.id} item={item} onDismiss={dismiss} />
          ))}
        </div>
      )}
    </ToastContext.Provider>
  );
}

// ── Hook ────────────────────────────────────────────────────────

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (ctx === undefined) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return ctx;
}
