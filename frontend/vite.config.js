import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      // TEMPORARY: ship a self-destroying service worker. Older builds cached a
      // heavy bundle that froze the main thread, so those clients could never
      // run the auto-update reload and stayed stuck on stale JS. A
      // self-destroying SW unregisters itself and wipes its caches from the SW
      // thread (which isn't frozen), forcing every client back to fresh network
      // loads. Re-enable the normal offline PWA once all clients are recovered.
      selfDestroying: true,
      // autoUpdate: a new service worker installs silently and activates on
      // the next navigation. Combined with the skipWaiting / reload logic
      // in main.tsx, visible tabs reload automatically when a new build
      // ships — no stale UIs staying behind yesterday's JS.
      registerType: "autoUpdate",
      // Inject a light manifest so browsers treat this as an installable
      // PWA; nothing else in the app depends on the manifest, it is only
      // here so that Chrome / Safari will happily cache the shell.
      manifest: {
        name: "Solarica",
        short_name: "Solarica",
        description: "Solarica pier inspection — works offline in the field.",
        theme_color: "#0f172a",
        background_color: "#f8fafc",
        display: "standalone",
        start_url: "/",
        icons: [],
      },
      workbox: {
        // Cache the JS/CSS/HTML shell so the app opens without a network.
        // Maximum file size bumped so the MapLibre chunk is not skipped.
        maximumFileSizeToCacheInBytes: 4 * 1024 * 1024,
        globPatterns: ["**/*.{js,css,html,svg,png,woff,woff2}"],
        navigateFallback: "/index.html",
        // Never cache API responses — our IndexedDB layer handles that.
        navigateFallbackDenylist: [/^\/api\//],
        // Activate a new SW immediately and claim open clients so the page
        // reload in main.tsx fires on the next visit (instead of waiting
        // for every tab to close, which on mobile basically never happens).
        skipWaiting: true,
        clientsClaim: true,
        cleanupOutdatedCaches: true,
        runtimeCaching: [
          {
            // Serve /api/* requests straight from the network. The
            // IndexedDB layer in src/api.ts is the source of truth for
            // offline data; we explicitly do not want Workbox to shadow it.
            urlPattern: /\/api\//,
            handler: "NetworkOnly",
          },
        ],
      },
    }),
  ],
  server: {
    proxy: {
      "/api": "http://localhost:8000",
      "/projects": "http://localhost:8000",
    },
  },
});
