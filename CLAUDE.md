# Solarica Parsing Engine

Solar pier inspection platform. Backend parses construction/ramming PDFs to extract blocks, trackers, and piers. Frontend shows them in Grid + Map views with status tracking. Designed for offline field use.

## Architecture

- **Backend**: Python/FastAPI, PostgreSQL, runs on `root@185.229.226.37` as `solarica-backend.service` (uvicorn, 1 worker, port 8010)
- **Frontend**: React + TypeScript + Vite, deployed to `/opt/solarica/frontend/dist` on the same server, served by nginx at `https://solarica.wavelync.com/`
- **Map**: MapLibre GL JS (WebGL) — single lazy-loaded chunk, GeoJSON circle layers for 25k+ piers
- **Grid**: ag-grid-community with checkbox multi-selection
- **Offline**: IndexedDB cache (`idb` package) + service worker (`vite-plugin-pwa`), optimistic writes with mutation queue

## Key files

### Backend (`backend/`)
- `app/main.py` — FastAPI routes (CRUD projects, blocks, trackers, piers, pier-statuses, plant-info, files, parse)
- `app/parser.py` — PDF parsing pipeline. Key function: `extract_trackers_from_pdf_vector()` uses **Hungarian bipartite matching** (scipy `linear_sum_assignment`) per label round (P1..P19) for exact pier assignment. Produces exact BOM-matching pier counts.
- `app/pier_scan.py` — Low-level PDF vector extraction via PyMuPDF. `extract_vector_labeled_piers()` reads colored symbols + P1..P19 text labels.
- `app/system_artifacts.py` — Anchor/block label parsing, spatial indexing utilities
- `app/electrical_metadata.py` — Extracts electrical specs from construction PDF
- `app/db_store.py` — PostgreSQL persistence layer
- `requirements.txt` — includes `scipy>=1.13.0` (for Hungarian matching)

### Frontend (`frontend/src/`)
- `App.tsx` — Main app shell. Mode switcher (System/Grid/Map), shared selection state, bulk status toolbar, viewport filter toggle, sync queue panel mount
- `api.ts` — Offline-aware API layer. Network-first with IDB fallback for GETs. Optimistic writes with mutation queue for pier status updates. In-flight bundle deduplication per project id. Throws `OfflineError` for server-only operations when offline.
- `offlineStore.ts` — IndexedDB schema (3 stores: projects, meta, mutations). Bundle save/load, mutation queue with coalescing.
- `hooks/useOnlineStatus.ts` — React hook tracking `navigator.onLine` + pending mutation count. Auto-syncs on reconnect.
- `userPrefs.ts` — localStorage wrapper for pierLabelThreshold, pierDetailThreshold
- `components/SiteMapMapLibre.tsx` — MapLibre GL map. Renders piers (circle layer), blocks (fill+line), trackers (line), block labels (HTML markers), pier code labels (HTML markers when zoomed), detail cards (when <=4 visible). Box-select with fitBounds. Bulk selection highlight layer.
- `components/SimpleGrid.tsx` — ag-grid wrapper with checkbox multi-select, external selection sync
- `components/SystemPanel.tsx` — Project files upload, parse trigger, plant info editor. Disabled when offline.
- `components/SyncQueuePanel.tsx` — Modal listing pending mutations with per-row Retry/Ignore and batch Retry All/Clear All
- `components/Modals.tsx` — BusyOverlay (blocking spinner), ConfirmModal, PromptModal
- `components/PierModal.tsx` — Individual pier detail popup
- `vite.config.js` — Vite + React + vite-plugin-pwa (Workbox service worker, precaches app shell)

## Deploy

### Frontend only
```powershell
$env:DEPLOY_SKIP_CONFIRM="1"; .\deploy-to-server.ps1
```

### Backend only
```powershell
$env:DEPLOY_SKIP_CONFIRM="1"; .\deploy-backend-to-server.ps1
```

### Both
```powershell
$env:DEPLOY_SKIP_CONFIRM="1"; .\deploy-all-to-server.ps1
```

Target: `root@185.229.226.37`, frontend at `/opt/solarica/frontend/dist`, backend at `/opt/solarica/backend/`

## Server notes

- **1 uvicorn worker** (was 2, reduced to prevent OOM during parse — server has 3.9 GB RAM)
- Service: `systemctl restart solarica-backend`
- Nginx serves frontend as static files + proxies `/api/*` to `127.0.0.1:8010`
- scipy is pre-installed in `/opt/solarica/venv/`

## Parser algorithm (extract_trackers_from_pdf_vector)

Per-round Hungarian bipartite matching:
1. Round 1: anchors (ROW:/TRK: text) → P1 labels via Hungarian
2. Round 2: P1 → nearest P2 via Hungarian, establishing axis direction per tracker
3. Rounds 3..19: active trackers ↔ unused P(k) labels via Hungarian. Cost = Euclidean drift from predicted + 2x perpendicular penalty. Along-axis bounds [0.4x, 1.7x step], perpendicular max 3pt (half the 7pt inter-tracker spacing). Tracker drops out when no feasible P(k) remains.
4. Step/direction re-estimated after each hop for curving rows.

Result on proect2: exactly 24130 piers matching BOM, exact distribution {5:43, 6:37, 9:53, 11:30, 13:112, 15:36, 17:1164, 19:58}.

## Known gaps / next tasks

- **Row numbers on piers**: DONE. `row_num` is now propagated from tracker anchor to every pier. Grid and map both show row numbers.
- **Block mapping file (3rd upload)**: UPLOAD WORKING. `block_mapping` kind added to `FILE_KINDS` in `backend/app/main.py`. User uploaded `block_names.jpeg` for ashalim3 — it's an image showing 18 execution blocks (numbered 1–18) overlaid on 13 design blocks (B1–B13) with colored boundary lines. The mapping is spatial, not tabular: execution blocks cut across design block boundaries. Implementation approach: use the image as a spatial reference — either (a) manually define the execution block polygons from the image coordinates and assign trackers by point-in-polygon, or (b) use CV to detect the colored boundary lines and OCR to read the numbers, then build polygons automatically. The image is at `uploads/block_mapping_c23d41ab_block_names.jpeg` on the server. Supported formats: Excel/CSV, PDF, PNG/JPG, DXF, DWG.
- **Full device inventory**: User wants a comprehensive device register (inverters, combiner boxes, DCCBs) with physical location, cyber exposure, and electrical safety fields. Needs new DB table, API endpoints, and import flow.
- **Tabs**: Current layout is tabs: Project Info (metadata), Details (Grid/Map), Devices (BOM/pier specs), Config (upload/parse). App.tsx owns project+plantInfo state, passes to SystemPanel as props.

## Offline mode

- App shell cached by service worker (vite-plugin-pwa, Workbox)
- Project data cached in IndexedDB on first online load
- Pier status writes are optimistic + queued in IDB mutation store
- Mutations coalesce (same pier updated twice → only latest kept)
- Auto-sync fires on `window.online` event
- SyncQueuePanel lets user inspect/retry/ignore stuck mutations
- Server-only ops (create project, upload, parse) throw OfflineError when offline
