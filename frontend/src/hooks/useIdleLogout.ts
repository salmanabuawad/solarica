import { useEffect } from "react";
import { logout, touchSession, hasSessionActivity, isSessionIdleExpired } from "../api";

// Activity that counts as "the user is still here". Passive listeners so they
// never block scrolling/typing. mousemove/scroll fire a lot, so writes are
// throttled in the handler.
const ACTIVITY_EVENTS = ["mousedown", "mousemove", "keydown", "touchstart", "scroll", "wheel", "click"];
const CHECK_INTERVAL_MS = 30 * 1000; // re-check idle every 30s
const WRITE_THROTTLE_MS = 5 * 1000;  // at most one localStorage write per 5s

/**
 * Auto sign-out after a period of inactivity (see IDLE_TIMEOUT_MS in api.ts).
 * Tracks activity as a shared localStorage timestamp so multiple tabs count as
 * one session, and also signs out when the app is reopened after a long idle.
 * Pass `enabled` = whether a user is currently signed in.
 */
export function useIdleLogout(enabled: boolean) {
  useEffect(() => {
    if (!enabled) return;

    // On mount: if the stored activity is already stale, sign out now (covers
    // reopening the app after being idle). If there's no baseline yet (e.g. an
    // older session from before this feature shipped), start the clock now.
    if (isSessionIdleExpired()) { logout(); return; }
    if (!hasSessionActivity()) touchSession();

    let lastWrite = Date.now();
    const onActivity = () => {
      const now = Date.now();
      if (now - lastWrite < WRITE_THROTTLE_MS) return;
      lastWrite = now;
      touchSession();
    };

    const check = () => { if (isSessionIdleExpired()) logout(); };
    const onVisible = () => { if (document.visibilityState === "visible") check(); };

    ACTIVITY_EVENTS.forEach((e) => window.addEventListener(e, onActivity, { passive: true }));
    document.addEventListener("visibilitychange", onVisible);
    const intervalId = window.setInterval(check, CHECK_INTERVAL_MS);

    return () => {
      ACTIVITY_EVENTS.forEach((e) => window.removeEventListener(e, onActivity));
      document.removeEventListener("visibilitychange", onVisible);
      window.clearInterval(intervalId);
    };
  }, [enabled]);
}
