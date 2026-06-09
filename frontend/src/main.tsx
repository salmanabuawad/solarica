import React from "react";
import ReactDOM from "react-dom/client";
import { ModuleRegistry, AllCommunityModule } from "ag-grid-community";
import { registerSW } from "virtual:pwa-register";
import App from "./App";
import ErrorBoundary from "./components/ErrorBoundary";
import "./i18n/i18n";
import "./index.css";

ModuleRegistry.registerModules([AllCommunityModule]);

// Service-worker update + offline support
// ----------------------------------------
// vite-plugin-pwa is configured as `registerType: "autoUpdate"` — a new
// SW installs in the background and sends `skipWaiting()` automatically.
// Once the new SW takes control, `controllerchange` fires; we use that as
// the cue to reload so open tabs don't keep running the old JS bundle.
// The same SW also Workbox-precaches the app shell (JS/CSS/HTML/icons),
// so the app boots fully offline after a single online visit.
if (typeof window !== "undefined") {
  let refreshing = false;
  const reload = () => { if (!refreshing) { refreshing = true; window.location.reload(); } };

  registerSW({
    immediate: true,
    onRegisteredSW(_swUrl, registration) {
      // Poll for a new service worker so an already-open phone/tablet picks up
      // a new deploy WITHOUT a manual refresh. nginx serves sw.js no-cache, so
      // update() re-fetches it; when a new SW is found, autoUpdate's
      // skipWaiting activates it → controllerchange (below) → auto reload.
      if (!registration) return;
      const check = () => { registration.update().catch(() => { /* offline / transient */ }); };
      check();
      setInterval(check, 30_000);
      // Also check on focus / visibility / online / pageshow. `pageshow` is the
      // important one for iOS: standalone PWAs are restored from the bfcache
      // and `pageshow` (persisted) fires when they do, while background timers
      // are frozen. Without this, an iOS home-screen app can sit on old code.
      window.addEventListener("focus", check);
      window.addEventListener("online", check);
      window.addEventListener("pageshow", check);
      document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") check(); });
    },
    onOfflineReady() { /* shell cached */ },
  });

  if ("serviceWorker" in navigator) {
    // Auto-reload when a NEW sw takes control — but not on the first SW install
    // of a fresh tab (that would double-load on the very first visit).
    const hadController = !!navigator.serviceWorker.controller;
    navigator.serviceWorker.addEventListener("controllerchange", () => { if (hadController) reload(); });

    // ---- Build watchdog -------------------------------------------------
    // The SW-update path above is not reliable on every phone (iOS especially
    // is slow to swap a controlling SW). So we independently compare the JS
    // bundle this tab booted with against the one the server is serving right
    // now, and force the refresh ourselves. nginx serves index.html no-store
    // and we add a cache-busting query so the SW precache can't shadow it.
    //   • 1st time a newer build is seen  → update the SW, then reload.
    //   • if a reload still served the old shell → unregister the SW + clear
    //     caches and reload, so the next load comes straight from the network.
    // Both steps are sessionStorage-guarded per build hash → never loops.
    const bootSrc = Array.from(document.querySelectorAll("script[src]"))
      .map((s) => s.getAttribute("src") || "")
      .find((s) => /assets\/index-[\w-]+\.js/.test(s)) || "";
    const booted = (bootSrc.match(/index-([\w-]+)\.js/) || [])[1] || "";
    if (booted) {
      const SOFT = "solarica_build_soft", HARD = "solarica_build_hard";
      const poll = async () => {
        if (refreshing || document.visibilityState !== "visible" || !navigator.onLine) return;
        let live = "";
        try {
          const html = await fetch("/index.html?ts=" + Date.now(), { cache: "no-store" }).then((r) => r.text());
          live = (html.match(/index-([\w-]+)\.js/) || [])[1] || "";
        } catch { return; /* offline / transient */ }
        if (!live || live === booted) return;
        if (sessionStorage.getItem(HARD) === live) return; // escalation already spent → don't loop
        if (sessionStorage.getItem(SOFT) === live) {
          // A gentle reload already happened but we still booted the old shell
          // → the SW is serving stale precache. Nuke it and reload from network.
          sessionStorage.setItem(HARD, live);
          try {
            const regs = await navigator.serviceWorker.getRegistrations();
            await Promise.all(regs.map((r) => r.unregister()));
            if (window.caches) { const keys = await caches.keys(); await Promise.all(keys.map((k) => caches.delete(k))); }
          } catch { /* ignore */ }
          reload();
          return;
        }
        // First sighting of a newer build → refresh the SW, then reload.
        sessionStorage.setItem(SOFT, live);
        try {
          const reg = await navigator.serviceWorker.getRegistration();
          if (reg) { await reg.update(); if (reg.waiting) reg.waiting.postMessage({ type: "SKIP_WAITING" }); }
        } catch { /* ignore */ }
        setTimeout(reload, 1200);
      };
      setInterval(poll, 30_000);
      window.addEventListener("focus", poll);
      window.addEventListener("online", poll);
      window.addEventListener("pageshow", poll);
      document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") poll(); });
      setTimeout(poll, 4000);
    }
  }
}

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode><ErrorBoundary><App /></ErrorBoundary></React.StrictMode>
);
