import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import maplibregl, {
  GeoJSONSource,
  Map as MLMap,
  MapMouseEvent,
} from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import {
  PIER_COLORS,
  STATUS_COLORS,
  SiteMapProps,
  layerVisible,
  rotate90CCW,
} from "./SiteMapProps";

/**
 * MapLibre GL renderer. The site is treated as a small geographic rectangle
 * around (0, 0) so MapLibre's vector renderer can draw every pier in a
 * single GL draw call.
 *
 * Features parity with the legacy canvas SiteMap:
 *   - Blocks (polygon line + optional selection fill)
 *   - Block labels (HTML markers at centroids)
 *   - Trackers (line from first to last pier)
 *   - Piers (circle layer, colored by type)
 *   - Status rings (circle stroke for non-"New" piers)
 *   - Selected pier highlight
 *   - Layer toggles
 *   - Click to select pier / tracker / block
 *   - Pier-code labels when visible count ≤ `pierLabelThreshold`
 *   - Box area selection via an overlay rectangle (mouse + touch)
 */

// PDF points → pseudo lon/lat. Small scale keeps us well inside Mercator.
const DEG_PER_PT = 0.001;
const pt2lng = (pt: number) => pt * DEG_PER_PT;
const pt2lat = (pt: number) => -pt * DEG_PER_PT; // flip y so +y is down

function rotatedToLngLat(
  x: number,
  y: number,
  imageWidth: number,
): [number, number] {
  const [rx, ry] = rotate90CCW(x, y, imageWidth);
  return [pt2lng(rx), pt2lat(ry)];
}

export default function SiteMapMapLibre({
  imageWidth,
  blocks,
  trackers,
  piers,
  pierStatuses,
  selectedBlock,
  selectedTracker,
  selectedPier,
  layers,
  onBlockClick,
  onTrackerClick,
  onPierClick,
  onAreaSelect,
  bulkSelectedPierCodes,
  pierLabelThreshold = 25,
  pierDetailThreshold = 4,
}: SiteMapProps) {
  const { t } = useTranslation();
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MLMap | null>(null);
  const blockMarkersRef = useRef<maplibregl.Marker[]>([]);
  const rowLabelMarkersRef = useRef<maplibregl.Marker[]>([]);
  const pierLabelMarkersRef = useRef<maplibregl.Marker[]>([]);
  // Ref raised while the corner zoom-square is actively being dragged,
  // so the map click handlers can skip pier / tracker / block clicks
  // under the pointer during a drag.
  const isBoxDraggingRef = useRef(false);

  // Refs mirroring reactive state, so map-level event handlers (registered
  // once at load) always see the *current* props without needing the
  // enclosing effect to re-subscribe.  Without these the handlers captured
  // the first-render closure: zooming fired refreshRowLabels against the
  // stale `layers` / `rowLabelData` snapshot → labels appeared to vanish
  // despite the checkbox being selected.
  const layersRef = useRef(layers);
  useEffect(() => { layersRef.current = layers; }, [layers]);
  const piersRef = useRef(piers);
  useEffect(() => { piersRef.current = piers; }, [piers]);
  const rowLabelDataRef = useRef<Record<string, { lng: number; lat: number }>>({});

  // ---- GeoJSON sources (memoized by dataset) ------------------------------

  const piersGeoJSON = useMemo(() => {
    const features = piers.map((p: any) => {
      const [lng, lat] = rotatedToLngLat(p.x, p.y, imageWidth);
      const status = pierStatuses?.[p.pier_code] || "New";
      return {
        type: "Feature" as const,
        geometry: { type: "Point" as const, coordinates: [lng, lat] },
        properties: {
          pier_code: p.pier_code,
          pier_type: p.pier_type || "UNKNOWN",
          color: PIER_COLORS[p.pier_type] || PIER_COLORS.UNKNOWN,
          status,
          status_color: STATUS_COLORS[status] || "",
          block_code: p.block_code || "",
          tracker_code: p.tracker_code || "",
          row_num: p.row_num ?? "",
          slope_band: p.slope_band || "",
          structure_code: p.structure_code || "",
        },
      };
    });
    return { type: "FeatureCollection" as const, features };
  }, [piers, pierStatuses, imageWidth]);

  const blocksGeoJSON = useMemo(() => {
    const features = blocks.flatMap((b: any) => {
      const poly = b.polygon;
      if (!poly || poly.length < 3) return [];
      const ring = poly.map((pt: any) =>
        rotatedToLngLat(pt.x, pt.y, imageWidth),
      );
      ring.push(ring[0]);
      return [
        {
          type: "Feature" as const,
          geometry: { type: "Polygon" as const, coordinates: [ring] },
          properties: { block_code: b.block_code, label: b.label },
        },
      ];
    });
    return { type: "FeatureCollection" as const, features };
  }, [blocks, imageWidth]);

  const trackersGeoJSON = useMemo(() => {
    // Group piers by tracker_code, then draw a line from first to last pier.
    const byTracker: Record<string, any[]> = {};
    for (const p of piers) {
      if (!p.tracker_code) continue;
      (byTracker[p.tracker_code] ??= []).push(p);
    }
    const features = trackers
      .map((t: any) => {
        const tPiers = byTracker[t.tracker_code];
        if (!tPiers || tPiers.length < 2) return null;
        const sorted = [...tPiers].sort((a, b) =>
          String(a.pier_code || "").localeCompare(String(b.pier_code || "")),
        );
        const first = sorted[0];
        const last = sorted[sorted.length - 1];
        return {
          type: "Feature" as const,
          geometry: {
            type: "LineString" as const,
            coordinates: [
              rotatedToLngLat(first.x, first.y, imageWidth),
              rotatedToLngLat(last.x, last.y, imageWidth),
            ],
          },
          properties: {
            tracker_code: t.tracker_code,
            row: String(t.row || ""),
          },
        };
      })
      .filter(Boolean) as any[];
    return { type: "FeatureCollection" as const, features };
  }, [trackers, piers, imageWidth]);

  // Row labels: compute the topmost pier position per row number so we can
  // place a label above each row on the map.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const rowLabelData = useMemo(() => {
    const rowEdges: Record<string, { lng: number; lat: number }> = {};
    for (const p of piers) {
      const row = String(p.row_num || "");
      if (!row) continue;
      const [rx, ry] = rotate90CCW(p.x, p.y, imageWidth);
      const lng = pt2lng(rx);
      const lat = pt2lat(ry);
      const existing = rowEdges[row];
      // "Topmost" = largest lat (least negative) in the rotated space.
      if (!existing || lat > existing.lat) {
        rowEdges[row] = { lng, lat };
      }
    }
    return rowEdges;
  }, [piers, imageWidth]);

  const bounds = useMemo(() => {
    if (!piers.length) return null;
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (const p of piers) {
      const [rx, ry] = rotate90CCW(p.x, p.y, imageWidth);
      if (rx < minX) minX = rx;
      if (rx > maxX) maxX = rx;
      if (ry < minY) minY = ry;
      if (ry > maxY) maxY = ry;
    }
    return new maplibregl.LngLatBounds(
      [pt2lng(minX), pt2lat(maxY)],
      [pt2lng(maxX), pt2lat(minY)],
    );
  }, [piers, imageWidth]);

  // ---- Map lifecycle ------------------------------------------------------

  useEffect(() => {
    if (!containerRef.current) return;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: {
        version: 8,
        sources: {},
        layers: [
          {
            id: "bg",
            type: "background",
            paint: { "background-color": "#f8fafc" },
          },
        ],
      },
      center: [0, 0],
      zoom: 2,
      minZoom: -2,
      maxZoom: 22,
      dragRotate: false,
      pitchWithRotate: false,
      touchPitch: false,
    });
    mapRef.current = map;
    map.addControl(
      new maplibregl.NavigationControl({ showCompass: false }),
      "top-right",
    );

    map.on("load", () => {
      // --- Sources -------------------------------------------------------
      map.addSource("blocks", { type: "geojson", data: blocksGeoJSON });
      map.addSource("trackers", { type: "geojson", data: trackersGeoJSON });
      map.addSource("piers", { type: "geojson", data: piersGeoJSON });

      // --- Block fill + outline -----------------------------------------
      map.addLayer({
        id: "blocks-fill",
        type: "fill",
        source: "blocks",
        paint: {
          "fill-color": "#3b82f6",
          "fill-opacity": 0.04,
        },
      });
      map.addLayer({
        id: "blocks-outline",
        type: "line",
        source: "blocks",
        paint: {
          "line-color": "#3b82f6",
          "line-width": 1.2,
        },
      });
      map.addLayer({
        id: "blocks-selected",
        type: "line",
        source: "blocks",
        filter: ["==", ["get", "block_code"], ""],
        paint: {
          "line-color": "#f97316",
          "line-width": 2.5,
        },
      });

      // --- Tracker lines -------------------------------------------------
      //
      // Solid emerald line that actually *reads* against the pier dots.
      // Width scales with zoom so it doesn't look chunky at far zoom-out
      // nor disappear at close zoom-in.
      map.addLayer({
        id: "trackers-line",
        type: "line",
        source: "trackers",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": "#16a34a",
          "line-opacity": 0.85,
          "line-width": [
            "interpolate", ["linear"], ["zoom"],
            0, 1.2,
            4, 1.8,
            8, 2.6,
            12, 3.5,
            18, 5,
          ],
        },
      });
      map.addLayer({
        id: "trackers-selected",
        type: "line",
        source: "trackers",
        filter: ["==", ["get", "tracker_code"], ""],
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": "#f97316",
          "line-width": 4,
        },
      });

      // --- Pier circles + status rings + selection ---------------------
      //
      // A pier's fill reflects its current *status* when it's not "New"
      // (matches the grid's status-pill colours so the map and table tell
      // the same story at a glance). "New" piers fall back to their
      // pier_type colour. A white ring around status-ful piers keeps them
      // legible regardless of what colour's behind them.
      map.addLayer({
        id: "piers-layer",
        type: "circle",
        source: "piers",
        paint: {
          "circle-radius": [
            "interpolate", ["linear"], ["zoom"],
            0, 1.5,
            6, 2.5,
            10, 4,
            14, 6,
            18, 10,
          ],
          "circle-color": [
            "case",
            ["!=", ["get", "status"], "New"], ["get", "status_color"],
            ["get", "color"],
          ],
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": [
            "case",
            ["!=", ["get", "status"], "New"], 1.5,
            0,
          ],
        },
      });
      // Extra status-coloured halo so piers pop off the map even at low zoom.
      map.addLayer({
        id: "pier-status-rings",
        type: "circle",
        source: "piers",
        filter: ["!=", ["get", "status"], "New"],
        paint: {
          "circle-radius": [
            "interpolate", ["linear"], ["zoom"],
            0, 3,
            6, 4.5,
            10, 7,
            14, 10,
            18, 15,
          ],
          "circle-color": "rgba(0,0,0,0)",
          "circle-stroke-color": ["get", "status_color"],
          "circle-stroke-width": 2,
          "circle-stroke-opacity": 0.55,
        },
      });

      // --- Status icons (symbol layer) ----------------------------------
      //
      // Each non-"New" pier gets a small icon matching its status: clock,
      // wrench, check, X, or shield.  Icons are white-filled circles with
      // a coloured stroke + glyph so they're legible on any base-layer.
      // Loaded as data-URI SVGs into the map's image store; cheap (< 1 KB
      // each) and renders with the usual collision-aware symbol layer.
      const SIZE = 24;
      const statusIcons: Array<{ id: string; svg: string }> = [
        {
          id: "status-in-progress",
          svg: `<svg xmlns="http://www.w3.org/2000/svg" width="${SIZE}" height="${SIZE}" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10.5" fill="#fff" stroke="#eab308" stroke-width="2"/><path d="M12 7v5l3 2" fill="none" stroke="#a16207" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
        },
        {
          id: "status-implemented",
          svg: `<svg xmlns="http://www.w3.org/2000/svg" width="${SIZE}" height="${SIZE}" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10.5" fill="#fff" stroke="#10b981" stroke-width="2"/><path d="M7 12l3.2 3.2L17 8" fill="none" stroke="#047857" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
        },
        {
          id: "status-approved",
          svg: `<svg xmlns="http://www.w3.org/2000/svg" width="${SIZE}" height="${SIZE}" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10.5" fill="#16a34a" stroke="#166534" stroke-width="1.5"/><path d="M7 12l3.2 3.2L17 8" fill="none" stroke="#fff" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
        },
        {
          id: "status-rejected",
          svg: `<svg xmlns="http://www.w3.org/2000/svg" width="${SIZE}" height="${SIZE}" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10.5" fill="#fff" stroke="#ef4444" stroke-width="2"/><path d="M8 8l8 8M16 8l-8 8" fill="none" stroke="#b91c1c" stroke-width="2.4" stroke-linecap="round"/></svg>`,
        },
        {
          id: "status-fixed",
          svg: `<svg xmlns="http://www.w3.org/2000/svg" width="${SIZE}" height="${SIZE}" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10.5" fill="#fff" stroke="#2563eb" stroke-width="2"/><path d="M12 5l6 2.2v4.4c0 3.5-2.5 6.4-6 7.4-3.5-1-6-3.9-6-7.4V7.2z" fill="#dbeafe"/><path d="M9 12l2.2 2.2L15 10" fill="none" stroke="#1e40af" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
        },
      ];
      for (const it of statusIcons) {
        const img = new Image(SIZE, SIZE);
        img.onload = () => { if (!map.hasImage(it.id)) map.addImage(it.id, img); };
        img.src = "data:image/svg+xml;utf8," + encodeURIComponent(it.svg);
      }

      map.addLayer({
        id: "pier-status-icons",
        type: "symbol",
        source: "piers",
        filter: ["!=", ["get", "status"], "New"],
        layout: {
          "icon-image": [
            "case",
            ["==", ["get", "status"], "In Progress"], "status-in-progress",
            ["==", ["get", "status"], "Implemented"], "status-implemented",
            ["==", ["get", "status"], "Approved"],    "status-approved",
            ["==", ["get", "status"], "Rejected"],    "status-rejected",
            ["==", ["get", "status"], "Fixed"],       "status-fixed",
            "status-approved",
          ],
          "icon-size": [
            "interpolate", ["linear"], ["zoom"],
            0,  0.20,
            8,  0.35,
            12, 0.55,
            15, 0.80,
            18, 1.10,
          ],
          "icon-allow-overlap": false,
          "icon-ignore-placement": false,
          "symbol-sort-key": 1,  // stable draw order
        },
      });
      // Bulk-selection highlight — any pier whose code is in the shared
      // selection set. Drawn as a filled ring larger than the base circle.
      map.addLayer({
        id: "piers-bulk-selected",
        type: "circle",
        source: "piers",
        filter: ["in", ["get", "pier_code"], ["literal", []]],
        paint: {
          "circle-radius": [
            "interpolate", ["linear"], ["zoom"],
            0, 3,
            6, 5,
            10, 7,
            14, 10,
            18, 14,
          ],
          "circle-color": "rgba(59, 130, 246, 0.25)",
          "circle-stroke-color": "#2563eb",
          "circle-stroke-width": 2,
        },
      });
      map.addLayer({
        id: "piers-selected",
        type: "circle",
        source: "piers",
        filter: ["==", ["get", "pier_code"], ""],
        paint: {
          "circle-radius": 10,
          "circle-color": "#ef4444",
          "circle-stroke-width": 2,
          "circle-stroke-color": "#fff",
        },
      });

      // Generous internal padding so the site layout doesn't kiss the map's
      // edges — especially on narrow mobile viewports where 40 px was too tight.
      if (bounds) map.fitBounds(bounds, { padding: 56, duration: 0 });

      // --- Interaction handlers -----------------------------------------
      map.on("click", "piers-layer", (e: MapMouseEvent & { features?: any[] }) => {
        if (isBoxDraggingRef.current) return; // box-select owns clicks
        const f = e.features?.[0];
        if (!f) return;
        const code = f.properties?.pier_code;
        const match = piers.find((p: any) => p.pier_code === code);
        if (match) onPierClick(match);
      });
      map.on("click", "trackers-line", (e: MapMouseEvent & { features?: any[] }) => {
        if (isBoxDraggingRef.current) return;
        const f = e.features?.[0];
        if (!f) return;
        const code = f.properties?.tracker_code;
        const match = trackers.find((t: any) => t.tracker_code === code);
        if (match) onTrackerClick(match);
      });
      map.on("click", "blocks-fill", (e: MapMouseEvent & { features?: any[] }) => {
        if (isBoxDraggingRef.current) return;
        const f = e.features?.[0];
        if (!f) return;
        const code = f.properties?.block_code;
        const match = blocks.find((b: any) => b.block_code === code);
        if (match) onBlockClick(match);
      });
      map.on("mouseenter", "piers-layer", () => {
        if (!isBoxDraggingRef.current) map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", "piers-layer", () => {
        if (!isBoxDraggingRef.current) map.getCanvas().style.cursor = "";
      });

      // Pier number labels + viewport change: recompute on any movement end.
      const refresh = () => {
        refreshPierLabels();
        refreshRowLabels();
      };
      map.on("moveend", refresh);
      map.on("zoomend", refresh);
      refresh();
      refreshBlockLabels();
      refreshRowLabels();
    });

    return () => {
      clearMarkers();
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Resize the GL canvas when the container transitions from hidden to visible
  // (e.g. accordion toggling). Without this the canvas stays at 0x0 after a
  // display:none→block cycle.
  useEffect(() => {
    const el = containerRef.current;
    const map = mapRef.current;
    if (!el || !map) return;
    const ro = new ResizeObserver(() => {
      if (el.clientWidth > 0 && el.clientHeight > 0) {
        map.resize();
      }
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // The zoom square is always visible in the top-right; there is no
  // "box select mode" any more. dragPan stays enabled — the square's
  // own pointer events stop propagation, so panning the map past the
  // square still works exactly as before.

  // ---- Source updates when data changes ----------------------------------

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    (map.getSource("piers") as GeoJSONSource | undefined)?.setData(piersGeoJSON as any);
    refreshPierLabels();
  }, [piersGeoJSON]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    (map.getSource("blocks") as GeoJSONSource | undefined)?.setData(blocksGeoJSON as any);
    refreshBlockLabels();
  }, [blocksGeoJSON]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    (map.getSource("trackers") as GeoJSONSource | undefined)?.setData(trackersGeoJSON as any);
    refreshRowLabels();
  }, [trackersGeoJSON]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !bounds) return;
    // Fit only when the pier set itself changes (cheap heuristic: first load
    // or project swap).
    map.fitBounds(bounds, { padding: 40, duration: 300 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [piers.length, imageWidth]);

  // ---- Selection filters -------------------------------------------------

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    map.setFilter("piers-selected", [
      "==", ["get", "pier_code"], selectedPier?.pier_code || "",
    ]);
  }, [selectedPier]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    map.setFilter("trackers-selected", [
      "==", ["get", "tracker_code"], selectedTracker?.tracker_code || "",
    ]);
  }, [selectedTracker]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    map.setFilter("blocks-selected", [
      "==", ["get", "block_code"], selectedBlock?.block_code || "",
    ]);
  }, [selectedBlock]);

  // Bulk-selection filter — this can be a very large list so we pass it as
  // a literal expression directly into MapLibre.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    const codes = bulkSelectedPierCodes
      ? Array.from(bulkSelectedPierCodes)
      : [];
    if (map.getLayer("piers-bulk-selected")) {
      map.setFilter("piers-bulk-selected", [
        "in",
        ["get", "pier_code"],
        ["literal", codes],
      ]);
    }
  }, [bulkSelectedPierCodes]);

  // ---- Layer visibility --------------------------------------------------

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    const show = (id: string, visible: boolean) => {
      if (map.getLayer(id)) {
        map.setLayoutProperty(id, "visibility", visible ? "visible" : "none");
      }
    };
    const piersOn = layerVisible(layers, "piers");
    const blocksOn = layerVisible(layers, "blocks");
    const blockLabelsOn = layerVisible(layers, "blockLabels");
    const trackersOn = layerVisible(layers, "trackers");
    const rowLabelsOn = layerVisible(layers, "row_labels");
    show("piers-layer", piersOn);
    show("piers-selected", piersOn);
    show("pier-status-rings", piersOn);
    show("pier-status-icons", piersOn);
    show("blocks-fill", blocksOn);
    show("blocks-outline", blocksOn);
    show("blocks-selected", blocksOn);
    show("trackers-line", trackersOn);
    show("trackers-selected", trackersOn);
    // Block labels are HTML markers and can't use MapLibre layout visibility.
    for (const m of blockMarkersRef.current) {
      m.getElement().style.display = blockLabelsOn ? "" : "none";
    }
    refreshPierLabels();
    // Row-label rendering lives in its OWN effect below so that toggling
    // Blocks / Block labels / Trackers doesn't destroy and rebuild the row
    // markers each time (previously this loop ran on every layer change
    // and visually wiped the row labels mid-toggle).
  }, [layers, pierLabelThreshold, pierDetailThreshold]);

  // ---- Row labels — dedicated effect ------------------------------------
  //
  // Only re-runs when Row-numbers visibility changes or when the underlying
  // pier data changes. Prevents Blocks / Block-labels toggles from
  // destroying and rebuilding the row-number markers.
  const rowLabelsOn = layerVisible(layers, "row_labels");
  useEffect(() => {
    refreshRowLabels();
  }, [rowLabelsOn, rowLabelData]);

  // ---- HTML marker helpers ----------------------------------------------

  function clearMarkers() {
    for (const m of pierLabelMarkersRef.current) m.remove();
    pierLabelMarkersRef.current = [];
    for (const m of rowLabelMarkersRef.current) m.remove();
    rowLabelMarkersRef.current = [];
    for (const m of blockMarkersRef.current) m.remove();
    blockMarkersRef.current = [];
  }

  function refreshBlockLabels() {
    const map = mapRef.current;
    if (!map) return;
    for (const m of blockMarkersRef.current) m.remove();
    blockMarkersRef.current = [];
    if (!layerVisible(layers, "blockLabels")) return;
    for (const b of blocks) {
      if (!b.centroid) continue;
      const el = document.createElement("div");
      el.textContent = b.block_code;
      el.style.cssText =
        "font: 700 12px Arial, sans-serif; color: #1e3a5f; pointer-events: none; " +
        "text-shadow: 0 0 3px #fff, 0 0 3px #fff, 0 0 3px #fff; white-space: nowrap;";
      const [lng, lat] = rotatedToLngLat(b.centroid.x, b.centroid.y, imageWidth);
      const marker = new maplibregl.Marker({ element: el })
        .setLngLat([lng, lat])
        .addTo(map);
      blockMarkersRef.current.push(marker);
    }
  }

  // Keep the data ref in sync so the zoom/move handlers always see fresh data.
  useEffect(() => { rowLabelDataRef.current = rowLabelData; }, [rowLabelData]);

  function refreshRowLabels() {
    const map = mapRef.current;
    if (!map) return;
    for (const m of rowLabelMarkersRef.current) m.remove();
    rowLabelMarkersRef.current = [];
    // Read layers + row positions through refs so zoom/move events
    // (registered once at map-load time) always see the latest state.
    if (!layerVisible(layersRef.current, "row_labels")) return;

    const bounds = map.getBounds();
    for (const [row, pos] of Object.entries(rowLabelDataRef.current)) {
      if (!bounds.contains([pos.lng, pos.lat])) continue;
      // Strip S prefix so short-tracker rows read the same as regular ones.
      const display = row.replace(/^S/i, "");
      const el = document.createElement("div");
      el.textContent = `R-${display}`;
      // Clickable pill so row numbers behave like piers/trackers: hover
      // feedback, pointer cursor, click filters the grid + highlights on map.
      el.style.cssText =
        "font: 700 11px Arial, sans-serif; color: #0f172a; cursor: pointer; " +
        "background: rgba(255,255,255,0.88); border: 1px solid #cbd5e1; " +
        "border-radius: 999px; padding: 1px 7px; white-space: nowrap; " +
        "box-shadow: 0 1px 2px rgba(0,0,0,0.08); user-select: none;";
      el.addEventListener("mouseenter", () => { el.style.background = "#dbeafe"; el.style.borderColor = "#93c5fd"; });
      el.addEventListener("mouseleave", () => { el.style.background = "rgba(255,255,255,0.88)"; el.style.borderColor = "#cbd5e1"; });
      el.addEventListener("click", (ev) => {
        ev.stopPropagation();
        // Re-use the tracker-click flow — the App treats it as a row
        // filter by setting gridFilterBy to "row" and gridFilterValue
        // to the row id. Passing a synthetic object with the row info
        // so the caller can distinguish.
        onTrackerClick({ __row: true, row: row, tracker_code: "", row_num: row });
      });
      const marker = new maplibregl.Marker({ element: el, anchor: "bottom" })
        .setLngLat([pos.lng, pos.lat + 0.003])
        .addTo(map);
      rowLabelMarkersRef.current.push(marker);
    }
  }

  function refreshPierLabels() {
    const map = mapRef.current;
    if (!map) return;
    // Remove existing labels.
    for (const m of pierLabelMarkersRef.current) m.remove();
    pierLabelMarkersRef.current = [];
    // Read through layersRef so the handler reflects the latest toggle state
    // even when triggered by map-level zoom / move events.
    if (!layerVisible(layersRef.current, "piers")) return;

    // Query only the features currently rendered in the viewport.
    const visible = map.queryRenderedFeatures(undefined, {
      layers: ["piers-layer"],
    });
    // Deduplicate by pier_code (MapLibre can return duplicates across tiles).
    const seen = new Set<string>();
    const unique: typeof visible = [];
    for (const f of visible) {
      const code = (f.properties as any)?.pier_code;
      if (!code || seen.has(code)) continue;
      seen.add(code);
      unique.push(f);
    }
    if (unique.length > pierLabelThreshold) return;

    // Pick the detail level: full card vs thin code-only label. The full
    // card only kicks in when the user is zoomed right onto a handful of
    // piers (default ≤ 4) so it does not flood the screen.
    const showDetails = unique.length <= pierDetailThreshold;

    for (const f of unique) {
      const props = f.properties as any;
      const geom = f.geometry as any;
      if (!geom || geom.type !== "Point") continue;
      const [lng, lat] = geom.coordinates as [number, number];
      const el = document.createElement("div");

      if (showDetails) {
        // Rich detail card — one row per meaningful field.
        const statusColor = STATUS_COLORS[props.status] || "#94a3b8";
        const rows: string[] = [];
        const add = (label: string, value: any) => {
          if (value == null || value === "") return;
          rows.push(
            `<div style="display:flex;gap:6px;"><span style="color:#64748b;min-width:52px;">${label}</span><span style="color:#0f172a;font-weight:600;">${String(value)}</span></div>`,
          );
        };
        add("Type", props.pier_type);
        add("Tracker", props.tracker_code);
        add("Block", props.block_code);
        add("Row", props.row_num);
        add("Structure", props.structure_code);
        add("Slope", props.slope_band);
        el.innerHTML = `
          <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;">
            <span style="width:8px;height:8px;border-radius:50%;background:${props.color};display:inline-block;box-shadow:0 0 0 1px #cbd5e1;"></span>
            <span style="font:700 12px Arial,sans-serif;color:#0f172a;">${props.pier_code}</span>
            <span style="font:600 10px Arial,sans-serif;color:${statusColor};text-transform:uppercase;letter-spacing:.3px;">${props.status}</span>
          </div>
          <div style="font:500 11px Arial,sans-serif;display:grid;gap:1px;">
            ${rows.join("")}
          </div>`;
        el.style.cssText =
          "background: rgba(255,255,255,0.97); padding: 6px 8px; border-radius: 8px; " +
          "box-shadow: 0 2px 8px rgba(15,23,42,0.18); border: 1px solid #e2e8f0; " +
          "pointer-events: none; transform: translate(12px, -50%); " +
          "white-space: nowrap; min-width: 140px;";
      } else {
        // Thin code-only label.
        el.textContent = String(props.pier_code || "");
        el.style.cssText =
          "font: 600 10px Arial, sans-serif; color: #0f172a; pointer-events: none; " +
          "background: rgba(255,255,255,0.85); padding: 1px 4px; border-radius: 4px; " +
          "transform: translate(10px, -6px); white-space: nowrap;";
      }

      const marker = new maplibregl.Marker({
        element: el,
        anchor: showDetails ? "left" : "top-left",
      })
        .setLngLat([lng, lat])
        .addTo(map);
      pierLabelMarkersRef.current.push(marker);
    }
  }

  // ---- Always-visible zoom selector --------------------------------------
  //
  // A fixed square sits parked in the map's top-right corner at all
  // times; the user drags it over an area of interest and releases to
  // zoom+select. No toolbar button needed. +/- buttons on the square
  // resize it in 20 px steps (60 px min → 90 % of shorter side max).
  useEffect(() => {
    const map = mapRef.current;
    const container = containerRef.current;
    if (!map || !container) return;

    const crect = container.getBoundingClientRect();
    const minSide = 60;
    const maxSide = Math.round(Math.min(crect.width, crect.height) * 0.9);
    let side = Math.round(Math.min(crect.width, crect.height) * 0.18);
    // Park in the top-right corner by default.
    const margin = 12;
    const initialLeft = Math.max(0, crect.width - side - margin);
    const initialTop = margin;

    const box = document.createElement("div");
    box.style.cssText =
      `position: absolute; left: ${initialLeft}px; top: ${initialTop}px; ` +
      `width: ${side}px; height: ${side}px; ` +
      `border: 2px solid #2563eb; background: rgba(37,99,235,0.12); ` +
      `box-shadow: 0 6px 20px rgba(0,0,0,0.22); border-radius: 8px; ` +
      `cursor: grab; z-index: 20; touch-action: none; ` +
      `display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 4px;`;

    // Compact +/- resize controls anchored inside the top-right corner
    // of the box so the user never has to chase a separate toolbar.
    const ctrl = document.createElement("div");
    ctrl.style.cssText =
      "position: absolute; top: 4px; right: 4px; display: flex; gap: 4px; z-index: 2;";
    const mkBtn = (label: string, onClick: () => void) => {
      const b = document.createElement("button");
      b.type = "button";
      b.textContent = label;
      b.style.cssText =
        "width: 26px; height: 26px; border-radius: 6px; border: 1px solid #bfdbfe; " +
        "background: rgba(255,255,255,0.95); color: #1e3a8a; font: 700 14px Arial; " +
        "cursor: pointer; line-height: 1; padding: 0; touch-action: manipulation;";
      b.addEventListener("click", (ev) => { ev.stopPropagation(); onClick(); });
      b.addEventListener("pointerdown", (ev) => { ev.stopPropagation(); });  // don't start drag
      return b;
    };
    const plusBtn = mkBtn("+", () => resize(+20));
    const minusBtn = mkBtn("−", () => resize(-20));
    // Apply button — confirms the area (zoom + select). Previously this
    // happened implicitly on pointer-up; users wanted an explicit action
    // so they can drop the box and then deliberately choose "go".
    const applyBtn = mkBtn("✓", () => applyZoom());
    applyBtn.title = t("details.zoomHere", "Zoom & select this area");
    applyBtn.style.background = "#16a34a";
    applyBtn.style.color = "#ffffff";
    applyBtn.style.borderColor = "#15803d";
    ctrl.appendChild(minusBtn);
    ctrl.appendChild(plusBtn);
    ctrl.appendChild(applyBtn);
    box.appendChild(ctrl);

    const hint = document.createElement("div");
    hint.textContent = t("details.dragThenApply", "Drag, then press ✓");
    // Hint truncates + hides entirely when the box is narrow, otherwise
    // it overflowed the box on small sizes and looked "corrupted".
    hint.style.cssText =
      "font: 600 10px Arial, sans-serif; color: #1e3a8a; " +
      "background: rgba(255,255,255,0.9); padding: 2px 8px; border-radius: 999px; " +
      "pointer-events: none; white-space: nowrap; " +
      "max-width: calc(100% - 16px); overflow: hidden; text-overflow: ellipsis; " +
      "box-sizing: border-box;";
    box.appendChild(hint);
    container.appendChild(box);

    function updateHintVisibility() {
      // Keep the hint out of sight if the box is too narrow for it to
      // ever fit comfortably; the + / − / ✓ buttons are self-explanatory.
      hint.style.display = side < 130 ? "none" : "";
    }
    updateHintVisibility();

    function resize(delta: number) {
      const c = container.getBoundingClientRect();
      const newSide = Math.max(minSide, Math.min(maxSide, side + delta));
      const prevCX = parseFloat(box.style.left) + side / 2;
      const prevCY = parseFloat(box.style.top) + side / 2;
      side = newSide;
      box.style.width = `${side}px`;
      box.style.height = `${side}px`;
      box.style.left = `${Math.max(0, Math.min(c.width - side, Math.round(prevCX - side / 2)))}px`;
      box.style.top  = `${Math.max(0, Math.min(c.height - side, Math.round(prevCY - side / 2)))}px`;
      updateHintVisibility();
    }

    let dragging = false;
    let offset = { x: 0, y: 0 };

    function onDown(ev: PointerEvent) {
      ev.preventDefault();
      ev.stopPropagation();
      dragging = true;
      isBoxDraggingRef.current = true;
      box.style.cursor = "grabbing";
      const rect = box.getBoundingClientRect();
      offset = { x: ev.clientX - rect.left, y: ev.clientY - rect.top };
      box.setPointerCapture(ev.pointerId);
    }
    function onMove(ev: PointerEvent) {
      if (!dragging) return;
      ev.preventDefault();
      const c = container.getBoundingClientRect();
      const x = Math.max(0, Math.min(c.width - side, ev.clientX - c.left - offset.x));
      const y = Math.max(0, Math.min(c.height - side, ev.clientY - c.top - offset.y));
      box.style.left = `${x}px`;
      box.style.top = `${y}px`;
    }
    function onUp(ev: PointerEvent) {
      if (!dragging) return;
      dragging = false;
      // Defer clearing the drag flag to the next tick — the same pointer-up
      // may still bubble into a MapLibre click handler, and we don't want
      // that click to be treated as a pier click.
      setTimeout(() => { isBoxDraggingRef.current = false; }, 0);
      box.style.cursor = "grab";
      try { box.releasePointerCapture(ev.pointerId); } catch { /* noop */ }
      // Note: no zoom on drag-end any more — the user must press ✓.
    }

    function applyZoom() {
      // Compute world bounds under the box and zoom-fit them.
      const c = container.getBoundingClientRect();
      const x0 = parseFloat(box.style.left);
      const y0 = parseFloat(box.style.top);
      const x1 = x0 + side;
      const y1 = y0 + side;

      const canvas = map.getCanvas();
      const cr = canvas.getBoundingClientRect();
      const dx = c.left - cr.left;
      const dy = c.top - cr.top;
      const A = map.unproject([x0 + dx, y0 + dy]);
      const B = map.unproject([x1 + dx, y0 + dy]);
      const C = map.unproject([x0 + dx, y1 + dy]);
      const D = map.unproject([x1 + dx, y1 + dy]);
      const b = new maplibregl.LngLatBounds(A, B); b.extend(C); b.extend(D);

      // Report pier codes inside the square so the grid selection stays in sync.
      const features = map.queryRenderedFeatures(
        [[x0 + dx, y0 + dy], [x1 + dx, y1 + dy]],
        { layers: ["piers-layer"] },
      );
      const codes = new Set<string>();
      for (const f of features) {
        const c0 = (f.properties as any)?.pier_code;
        if (c0) codes.add(c0);
      }
      const picked = piersRef.current.filter((p: any) => codes.has(p.pier_code));
      onAreaSelect?.(picked);

      map.fitBounds(b, { padding: 32, duration: 450 });
      // Re-park in the (new) top-right corner so the box stays reachable
      // after a zoom-in that shrinks the viewport in canvas pixels.
      // Also clamp `side` to the new container — otherwise the box
      // overflows a narrow viewport after an aggressive zoom-in and
      // looks chopped off.
      requestAnimationFrame(() => {
        const cc = container.getBoundingClientRect();
        const fit = Math.max(minSide, Math.min(side, Math.round(Math.min(cc.width, cc.height) * 0.5)));
        if (fit !== side) {
          side = fit;
          box.style.width = `${side}px`;
          box.style.height = `${side}px`;
          updateHintVisibility();
        }
        box.style.left = `${Math.max(0, cc.width - side - margin)}px`;
        box.style.top = `${margin}px`;
      });
    }

    box.addEventListener("pointerdown", onDown);
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    return () => {
      box.removeEventListener("pointerdown", onDown);
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      if (box.parentNode) box.parentNode.removeChild(box);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div
      ref={containerRef}
      style={{
        position: "relative",
        width: "100%",
        height: "100%",
        minHeight: 300,
      }}
    >
    </div>
  );
}
