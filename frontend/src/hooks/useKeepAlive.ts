import { useEffect, useRef } from "react";
import { getAuthToken, getDataVersion, logout } from "../api";

const KEEPALIVE_INTERVAL_MS = 60 * 1000; // poll once per minute

/**
 * Keep-alive + change detection. Every minute (and whenever the tab regains
 * focus) it asks the server for the current data version of the active project:
 *  - if the version changed, calls onDataChanged() so the UI can refresh;
 *  - if the request 401s (expired/invalid token), forces the login screen.
 * Skips while the tab is hidden or the device is offline. The poll is NOT user
 * activity, so it never resets the idle-logout timer (see useIdleLogout).
 */
export function useKeepAlive(projectId: string | null, onDataChanged: () => void) {
  const lastVersion = useRef<string | null>(null);
  const onChange = useRef(onDataChanged);
  onChange.current = onDataChanged;

  useEffect(() => {
    if (!projectId) return;
    lastVersion.current = null; // new project → re-baseline
    let cancelled = false;

    const tick = async () => {
      if (cancelled) return;
      if (typeof document !== "undefined" && document.visibilityState !== "visible") return;
      if (typeof navigator !== "undefined" && navigator.onLine === false) return;
      try {
        const v = await getDataVersion(projectId);
        if (cancelled) return;
        if (lastVersion.current !== null && v !== lastVersion.current) onChange.current();
        lastVersion.current = v;
      } catch {
        // getDataVersion() goes through j(), which purges auth on a 401. If the
        // token is gone, the session expired — force the login screen.
        if (!getAuthToken()) logout();
        // otherwise transient/offline: ignore and try again next tick
      }
    };

    tick(); // seed the baseline immediately
    const id = window.setInterval(tick, KEEPALIVE_INTERVAL_MS);
    const onVisible = () => { if (document.visibilityState === "visible") tick(); };
    document.addEventListener("visibilitychange", onVisible);

    return () => {
      cancelled = true;
      window.clearInterval(id);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [projectId]);
}
