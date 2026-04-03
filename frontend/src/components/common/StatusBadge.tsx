// ── Types ───────────────────────────────────────────────────────

interface StatusBadgeProps {
  status: string;
  size?: 'sm' | 'md';
  className?: string;
}

// ── Color mapping ───────────────────────────────────────────────

const STATUS_COLORS: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-700 border-gray-300',
  open: 'bg-info-light text-info border-info',
  in_progress: 'bg-warning-light text-warning border-warning',
  pending_approval: 'bg-orange-100 text-orange-700 border-orange-400',
  approved: 'bg-success-light text-success border-success',
  rejected: 'bg-danger-light text-danger border-danger',
  completed: 'bg-success-light text-success border-success',
  closed: 'bg-gray-100 text-gray-500 border-gray-300',
  flagged: 'bg-danger-light text-danger border-danger',
  // Extra statuses used across the app
  pass: 'bg-success-light text-success border-success',
  fail: 'bg-danger-light text-danger border-danger',
  warning: 'bg-warning-light text-warning border-warning',
  critical: 'bg-danger-light text-danger border-danger',
  high: 'bg-warning-light text-warning border-warning',
  medium: 'bg-yellow-100 text-yellow-700 border-yellow-400',
  low: 'bg-gray-100 text-gray-600 border-gray-300',
  info: 'bg-info-light text-info border-info',
};

const DEFAULT_COLOR = 'bg-gray-100 text-gray-600 border-gray-300';

// ── Helpers ─────────────────────────────────────────────────────

function formatStatus(status: string): string {
  return status
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

// ── Component ───────────────────────────────────────────────────

export default function StatusBadge({ status, size = 'md', className = '' }: StatusBadgeProps) {
  const colorClasses = STATUS_COLORS[status.toLowerCase()] ?? DEFAULT_COLOR;
  const sizeClasses = size === 'sm' ? 'px-1.5 py-0.5 text-xs' : 'px-2 py-0.5 text-sm';

  return (
    <span
      className={`
        inline-flex items-center rounded-full border font-medium
        ${colorClasses}
        ${sizeClasses}
        ${className}
      `}
    >
      {formatStatus(status)}
    </span>
  );
}
