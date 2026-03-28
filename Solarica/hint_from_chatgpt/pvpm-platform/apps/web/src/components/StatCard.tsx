import { ReactNode } from "react";

export function StatCard({ title, value, hint }: { title: string; value: ReactNode; hint?: string }) {
  return (
    <div className="card">
      <div className="label">{title}</div>
      <div className="value">{value}</div>
      {hint ? <div className="hint">{hint}</div> : null}
    </div>
  );
}
