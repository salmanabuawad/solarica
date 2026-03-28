interface StatCardProps {
  title: string;
  value: string | number;
  hint?: string;
  accent?: boolean;
}

export function StatCard({ title, value, hint, accent }: StatCardProps) {
  return (
    <div className="stat-box">
      <div className="stat-label">{title}</div>
      <div className="stat-value" style={accent ? { color: "rgb(var(--theme-action-accent))" } : undefined}>
        {value}
      </div>
      {hint && <div style={{ fontSize: "var(--theme-font-size-xs)", color: "rgb(var(--theme-text-muted))", marginTop: 2 }}>{hint}</div>}
    </div>
  );
}
