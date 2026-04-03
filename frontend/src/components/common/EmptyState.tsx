import type { LucideIcon } from 'lucide-react';
import type { ReactNode } from 'react';

// ── Types ───────────────────────────────────────────────────────

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description?: string;
  action?: ReactNode;
  /** Legacy prop support: renders a button with this label */
  actionLabel?: string;
  onAction?: () => void;
}

// ── Component ───────────────────────────────────────────────────

export default function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  actionLabel,
  onAction,
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
      <div className="w-16 h-16 rounded-full bg-surface-alt flex items-center justify-center mb-4">
        <Icon size={32} className="text-text-muted" />
      </div>

      <h3 className="text-lg font-semibold text-text-primary mb-1">
        {title}
      </h3>

      {description && (
        <p className="text-sm text-text-secondary max-w-md mb-6">
          {description}
        </p>
      )}

      {/* Render custom action node, or a default button from actionLabel/onAction */}
      {action ? (
        <div>{action}</div>
      ) : actionLabel && onAction ? (
        <button
          onClick={onAction}
          className="px-4 py-2 bg-primary text-white text-sm font-medium rounded-lg hover:bg-primary-hover transition-colors"
        >
          {actionLabel}
        </button>
      ) : null}
    </div>
  );
}
