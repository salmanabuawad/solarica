import React from "react";

/**
 * Catches render/runtime errors in its subtree and shows a small fallback with
 * a reload button instead of letting the whole React tree unmount (which would
 * blank the screen). Use at the app root and around risky subtrees (the map).
 */
export default class ErrorBoundary extends React.Component<
  { children: React.ReactNode; fallback?: React.ReactNode; label?: string },
  { hasError: boolean }
> {
  constructor(props: any) {
    super(props);
    this.state = { hasError: false };
  }
  static getDerivedStateFromError() {
    return { hasError: true };
  }
  componentDidCatch(error: any, info: any) {
    // eslint-disable-next-line no-console
    console.error("[ErrorBoundary]", this.props.label || "", error, info);
  }
  render() {
    if (this.state.hasError) {
      if (this.props.fallback !== undefined) return this.props.fallback;
      return (
        <div style={{ padding: 16, color: "#b91c1c", fontSize: 13, display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <span>Something went wrong loading this view.</span>
          <button
            onClick={() => { try { window.location.reload(); } catch { /* ignore */ } }}
            style={{ padding: "6px 12px", borderRadius: 8, border: "1px solid #cbd5e1", background: "#fff", cursor: "pointer", fontWeight: 600 }}
          >Reload</button>
        </div>
      );
    }
    return this.props.children;
  }
}
