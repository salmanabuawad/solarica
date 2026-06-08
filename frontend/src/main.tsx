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
  registerSW({
    immediate: true,
    onRegisteredSW(_swUrl, registration) {
      // Poll for a new service worker so an already-open phone/tablet picks up
      // a new deploy WITHOUT a manual refresh. nginx serves sw.js no-cache, so
      // update() re-fetches it; when a new SW is found, autoUpdate's
      // skipWaiting activates it → controllerchange (below) → auto reload.
      if (!registration) return;
      const check = () => { registration.update().catch(() => { /* offline / transient */ }); };
      setInterval(check, 60_000);
      // Also check when the app regains focus / becomes visible (iOS Safari
      // backgrounds tabs and fires visibilitychange more reliably than focus) /
      // comes back online — so a phone returning to the app updates promptly.
      window.addEventListener("focus", check);
      window.addEventListener("online", check);
      document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") check(); });
    },
    onOfflineReady() { /* shell cached */ },
  });

  if ("serviceWorker" in navigator) {
    // Only auto-reload on an UPDATE (a controller already existed), not on the
    // first SW taking control of a fresh tab — that would double-load on the
    // very first visit.
    const hadController = !!navigator.serviceWorker.controller;
    let didReload = false;
    navigator.serviceWorker.addEventListener("controllerchange", () => {
      if (didReload || !hadController) return;
      didReload = true;
      window.location.reload();
    });
  }
}

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode><ErrorBoundary><App /></ErrorBoundary></React.StrictMode>
);
