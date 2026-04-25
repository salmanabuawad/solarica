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
  dccbs = [],
  inverters = [],
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
  pierStatusDisplay = "icon",
}: SiteMapProps) {
  const { t } = useTranslation();
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MLMap | null>(null);
  const blockMarkersRef = useRef<maplibregl.Marker[]>([]);
  const rowLabelMarkersRef = useRef<maplibregl.Marker[]>([]);
  const pierLabelMarkersRef = useRef<maplibregl.Marker[]>([]);
  const trackerLabelMarkersRef = useRef<maplibregl.Marker[]>([]);
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
  const trackerLabelDataRef = useRef<Record<string, { lng: number; lat: number }>>({});

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
    // Build a line per tracker.  We try three sources in order of
    // reliability:
    //   1. All piers on the tracker — draw the line that actually hits
    //      every pier (most accurate and, on Ashalim, always available).
    //   2. The tracker's bbox — span along whichever axis is longer.
    //   3. Skip (no usable geometry).
    //
    // The pier-based path is preferred because the Ashalim bbox values
    // coming out of the vector parser were observed to sometimes be
    // degenerate (zero width on single-pier trackers), which produced
    // point-length "lines" that MapLibre renders as invisible.
    const byTracker: Record<string, any[]> = {};
    for (const p of piers) {
      if (!p.tracker_code) continue;
      (byTracker[p.tracker_code] ??= []).push(p);
    }
    const features: any[] = [];
    let bboxUsed = 0;
    let pierUsed = 0;
    let skipped = 0;
    // Without a real imageWidth the coord transform is meaningless — skip
    // and recompute once the parent's imageWidth prop settles.
    if (!imageWidth || imageWidth <= 0) {
      return { type: "FeatureCollection" as const, features };
    }
    for (const t of trackers) {
      let a: [number, number] | null = null;
      let b: [number, number] | null = null;

      // Preferred: first-pier → last-pier along the tracker axis.
      const tPiers = byTracker[t.tracker_code];
      if (tPiers && tPiers.length >= 2) {
        const sorted = [...tPiers].sort((p, q) =>
          String(p.pier_code || "").localeCompare(String(q.pier_code || ""), undefined, { numeric: true }),
        );
        a = rotatedToLngLat(sorted[0].x, sorted[0].y, imageWidth);
        b = rotatedToLngLat(sorted[sorted.length - 1].x, sorted[sorted.length - 1].y, imageWidth);
        pierUsed++;
      } else {
        // Fallback: span the bbox along whichever side is longer.
        const box = t.bbox as { x: number; y: number; w: number; h: number } | undefined;
        if (
          box &&
          typeof box.x === "number" && typeof box.y === "number" &&
          typeof box.w === "number" && typeof box.h === "number" &&
          (box.w > 0 || box.h > 0)
        ) {
          if (box.w >= box.h) {
            const midY = box.y + box.h / 2;
            a = rotatedToLngLat(box.x,         midY, imageWidth);
            b = rotatedToLngLat(box.x + box.w, midY, imageWidth);
          } else {
            const midX = box.x + box.w / 2;
            a = rotatedToLngLat(midX, box.y,          imageWidth);
            b = rotatedToLngLat(midX, box.y + box.h,  imageWidth);
          }
          bboxUsed++;
        } else {
          skipped++;
        }
      }
      if (!a || !b) continue;
      features.push({
        type: "Feature" as const,
        geometry: { type: "LineString" as const, coordinates: [a, b] },
        properties: {
          tracker_code: t.tracker_code,
          row: String(t.row || ""),
        },
      });
    }
    // One-off diagnostic so it's obvious from the devtools console if
    // the tracker dataset never produced drawable features (the root
    // cause of the "Trackers checkbox does nothing" complaint).  Also
    // logs a sample so bad coordinates are easy to spot.
    try {
      const sample = features[0];
      console.debug(
        `[SiteMap] trackersGeoJSON: ${features.length} lines ` +
        `(pier=${pierUsed}, bbox=${bboxUsed}, skipped=${skipped}) ` +
        `from ${trackers.length} trackers, ${piers.length} piers, imageWidth=${imageWidth}`,
        sample ? sample.geometry.coordinates : "(no features)",
      );
    } catch { /* noop */ }
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

  // Tracker labels: compute one position per tracker_code, anchored at
  // the centre of the tracker bbox so the label sits over its row.
  // Only rendered when the user is zoomed in enough (see
  // refreshTrackerLabels below) — otherwise 1 533 labels would clobber
  // the map.
  const trackerLabelData = useMemo(() => {
    const out: Record<string, { lng: number; lat: number }> = {};
    if (!imageWidth || imageWidth <= 0) return out;
    for (const t of trackers) {
      if (!t?.tracker_code) continue;
      const box = t.bbox as { x: number; y: number; w: number; h: number } | undefined;
      let cx: number, cy: number;
      if (box && typeof box.x === "number" && typeof box.w === "number") {
        cx = box.x + box.w / 2;
        cy = box.y + box.h / 2;
      } else if (typeof t.center_x === "number" && typeof t.center_y === "number") {
        cx = t.center_x; cy = t.center_y;
      } else {
        continue;
      }
      const [lng, lat] = rotatedToLngLat(cx, cy, imageWidth);
      out[t.tracker_code] = { lng, lat };
    }
    return out;
  }, [trackers, imageWidth]);

  // DCCB + Inverter sources — both come from the electrical parser as
  // `{type, name, x, y}` in PDF-point coordinates, so the same 90° CCW
  // rotation the piers use puts them on the right spot on the map.
  const dccbGeoJSON = useMemo(() => {
    if (!imageWidth || imageWidth <= 0) {
      return { type: "FeatureCollection" as const, features: [] };
    }
    const features = (dccbs || [])
      .filter((d: any) => typeof d?.x === "number" && typeof d?.y === "number")
      .map((d: any) => ({
        type: "Feature" as const,
        geometry: {
          type: "Point" as const,
          coordinates: rotatedToLngLat(d.x, d.y, imageWidth),
        },
        properties: { name: d.name || "", type: "dccb" },
      }));
    return { type: "FeatureCollection" as const, features };
  }, [dccbs, imageWidth]);

  const inverterGeoJSON = useMemo(() => {
    if (!imageWidth || imageWidth <= 0) {
      return { type: "FeatureCollection" as const, features: [] };
    }
    const features = (inverters || [])
      .filter((d: any) => typeof d?.x === "number" && typeof d?.y === "number")
      .map((d: any) => ({
        type: "Feature" as const,
        geometry: {
          type: "Point" as const,
          coordinates: rotatedToLngLat(d.x, d.y, imageWidth),
        },
        properties: { name: d.name || "", type: "inverter" },
      }));
    return { type: "FeatureCollection" as const, features };
  }, [inverters, imageWidth]);

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
      map.addSource("dccb", { type: "geojson", data: dccbGeoJSON });
      map.addSource("inverters", { type: "geojson", data: inverterGeoJSON });

      // --- Block fill + outline -----------------------------------------
      //
      // Default-hidden (visibility: "none") so the Blocks checkbox drives
      // everything. Previously these added with implicit `visible` and
      // the first-run visibility effect could silently bail on the
      // `isStyleLoaded()` race, leaving the blocks briefly shown even
      // when the checkbox was off.
      map.addLayer({
        id: "blocks-fill",
        type: "fill",
        source: "blocks",
        layout: { visibility: "none" },
        paint: {
          "fill-color": "#3b82f6",
          "fill-opacity": 0.04,
        },
      });
      map.addLayer({
        id: "blocks-outline",
        type: "line",
        source: "blocks",
        layout: { visibility: "none" },
        paint: {
          "line-color": "#3b82f6",
          "line-width": 1.2,
        },
      });
      map.addLayer({
        id: "blocks-selected",
        type: "line",
        source: "blocks",
        layout: { visibility: "none" },
        filter: ["==", ["get", "block_code"], ""],
        paint: {
          "line-color": "#f97316",
          "line-width": 2.5,
        },
      });

      // --- Tracker lines -------------------------------------------------
      //
      // Drawn as a two-layer stack so the line reads on *any* base-map
      // colour and even when it crosses the 24 k pier dots:
      //   • `trackers-casing`  — wide white halo underneath
      //   • `trackers-line`    — emerald core on top
      // Both widths scale with zoom so the lines are legible from fully
      // zoomed-out (site overview) to fully zoomed-in (single row).
      map.addLayer({
        id: "trackers-casing",
        type: "line",
        source: "trackers",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": "#ffffff",
          "line-opacity": 0.8,
          "line-width": [
            "interpolate", ["linear"], ["zoom"],
            0, 1.5,
            6, 2,
            10, 2.5,
            14, 3.5,
            18, 5,
          ],
        },
      });
      map.addLayer({
        id: "trackers-line",
        type: "line",
        source: "trackers",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": "#16a34a",
          "line-opacity": 1,
          "line-width": [
            "interpolate", ["linear"], ["zoom"],
            0, 0.6,
            6, 1,
            10, 1.4,
            14, 2,
            18, 3,
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

      // --- Pier circles + selection ------------------------------------
      //
      // Pier dot colour follows the user preference `pierStatusDisplay`:
      //   • "icon"  → dot is always the pier_type colour, status comes
      //               from the icon symbol layer (default)
      //   • "color" → dot fill = status colour for non-New piers, no
      //               icon overlay
      //   • "both"  → status-coloured dot AND status icon
      // Both expressions are added at construction time; the visibility
      // effect below toggles the icon symbol layer based on the pref.
      const wantStatusColor = pierStatusDisplay !== "icon";
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
          "circle-color": wantStatusColor
            ? ["case", ["!=", ["get", "status"], "New"], ["get", "status_color"], ["get", "color"]]
            : ["get", "color"],
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": wantStatusColor
            ? ["case", ["!=", ["get", "status"], "New"], 1.5, 0]
            : 0,
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

      // --- Electrical devices -------------------------------------------
      //
      // DCCB  = small red dots with a white stroke (~ one per combiner).
      // Inverter = slightly larger blue dots with a white stroke (one
      //            per inverter station). Both start hidden; the user
      //            toggles them via the side-panel checkboxes.
      map.addLayer({
        id: "dccb-layer",
        type: "circle",
        source: "dccb",
        layout: { visibility: "none" },
        paint: {
          "circle-radius": [
            "interpolate", ["linear"], ["zoom"],
            0, 2.5, 8, 4, 14, 6, 18, 9,
          ],
          "circle-color": "#dc2626",
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": 1.5,
        },
      });
      map.addLayer({
        id: "inverters-layer",
        type: "circle",
        source: "inverters",
        layout: { visibility: "none" },
        paint: {
          "circle-radius": [
            "interpolate", ["linear"], ["zoom"],
            0, 3.5, 8, 6, 14, 9, 18, 13,
          ],
          "circle-color": "#2563eb",
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": 2,
        },
      });

      // Generous internal padding so the site layout doesn't kiss the map's
      // edges — especially on narrow mobile viewports where 40 px was too tight.
      if (bounds) map.fitBounds(bounds, { padding: 56, duration: 0 });

      // Promote tracker lines above the 24 k-pier layer so they're
      // actually readable.  With piers rendered on top the tracker line
      // was getting obscured.  Casing first (below) → core (on top).
      try {
        map.moveLayer("trackers-casing");
        map.moveLayer("trackers-line");
        map.moveLayer("trackers-selected");
      } catch { /* layers might not exist mid-swap; ignore */ }

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

      // Pier number labels + viewport change: recompute on any
      // movement end. The initial refresh is owned by dedicated
      // useEffects (`refreshPierLabels` / `refreshRowLabels` /
      // `refreshBlockLabels`), so we don't fire them again here —
      // doing so caused a double-render flicker on first paint.
      const refresh = () => {
        refreshPierLabels();
        refreshRowLabels();
        refreshTrackerLabels();
      };
      map.on("moveend", refresh);
      map.on("zoomend", refresh);
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
  // display:none→block cycle. Also re-fit the camera to the current bounds
  // whenever the container's pixel size changes substantially — otherwise
  // the first fitBounds (which fires before the lazy parent has finished
  // laying out) leaves the trackers as a tiny dot in the middle of the map.
  const boundsRef = useRef<maplibregl.LngLatBounds | null>(null);
  useEffect(() => { boundsRef.current = bounds; }, [bounds]);
  useEffect(() => {
    const el = containerRef.current;
    const map = mapRef.current;
    if (!el || !map) return;
    // First-time auto-fit only.  Once we successfully fit the map to
    // its bounds against a real, non-zero canvas, we stop auto-fitting
    // on resize — otherwise window-resizes and side-panel toggles
    // would fight against any zoom/pan the user has done since.
    let firstFitDone = false;
    const ro = new ResizeObserver(() => {
      const w = el.clientWidth;
      const h = el.clientHeight;
      if (w <= 0 || h <= 0) return;
      map.resize();
      if (!firstFitDone) {
        const b = boundsRef.current;
        if (b) {
          map.fitBounds(b, { padding: 56, duration: 0 });
          firstFitDone = true;
        }
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
    if (!map) return;
    const apply = () => {
      const src = map.getSource("piers") as GeoJSONSource | undefined;
      if (!src) { setTimeout(apply, 50); return; }
      src.setData(piersGeoJSON as any);
      // Note: pier-label markers are NOT rebuilt here.  They only
      // show `pier_code` (which doesn't change when pierStatuses
      // updates), so destroying + recreating them on every status
      // edit was a major source of visible flicker.  A dedicated
      // effect below refreshes them only when the pier *set* or the
      // label-threshold prefs actually change.
    };
    apply();
  }, [piersGeoJSON]);

  // Pier labels only depend on the pier set + threshold prefs, not on
  // statuses. Splitting this out kills the blink that used to fire on
  // every status update.
  useEffect(() => {
    refreshPierLabels();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [piers.length, imageWidth, pierLabelThreshold, pierDetailThreshold]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const apply = () => {
      const src = map.getSource("blocks") as GeoJSONSource | undefined;
      if (!src) { setTimeout(apply, 50); return; }
      src.setData(blocksGeoJSON as any);
      // refreshBlockLabels is owned by its dedicated effect below —
      // calling it here too caused the labels to blink on every
      // blocks-data tick.
    };
    apply();
  }, [blocksGeoJSON]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const apply = () => {
      const src = map.getSource("trackers") as GeoJSONSource | undefined;
      if (!src) {
        // Source hasn't been created yet (map hasn't fired load).  Retry
        // on the next paint — cheap and avoids losing data on the race.
        setTimeout(apply, 50);
        return;
      }
      src.setData(trackersGeoJSON as any);
      // Re-promote tracker lines above the 24 k pier layer every time
      // the data changes — otherwise a late-arriving pier source pushes
      // piers back on top and the lines silently disappear underneath.
      // Also *force* visibility to match the user's checkbox state: the
      // visibility effect can silently bail on first run if the style
      // isn't loaded yet, leaving the layer in whatever state the
      // addLayer call set it to. Doing it here guarantees the layer
      // follows the Trackers checkbox even across race-conditions.
      const trackersOn = layerVisible(layersRef.current, "trackers", true);
      try {
        if (map.getLayer("trackers-casing")) {
          map.moveLayer("trackers-casing");
          map.setLayoutProperty("trackers-casing", "visibility", trackersOn ? "visible" : "none");
        }
        if (map.getLayer("trackers-line")) {
          map.moveLayer("trackers-line");
          map.setLayoutProperty("trackers-line", "visibility", trackersOn ? "visible" : "none");
        }
        if (map.getLayer("trackers-selected")) {
          map.moveLayer("trackers-selected");
          map.setLayoutProperty("trackers-selected", "visibility", trackersOn ? "visible" : "none");
        }
      } catch { /* noop */ }
      // Row labels live on their own effect (deps: rowLabelsOn +
      // rowLabelData) so they don't re-render every time the tracker
      // line data ticks — used to be a major flicker source.
    };
    apply();
  }, [trackersGeoJSON]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const apply = () => {
      (map.getSource("dccb") as GeoJSONSource | undefined)?.setData(dccbGeoJSON as any);
      (map.getSource("inverters") as GeoJSONSource | undefined)?.setData(inverterGeoJSON as any);
    };
    if (map.isStyleLoaded()) apply();
    else map.once("load", apply);
  }, [dccbGeoJSON, inverterGeoJSON]);

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
    if (!map) return;
    const apply = () => {
      const show = (id: string, visible: boolean) => {
        if (map.getLayer(id)) {
          map.setLayoutProperty(id, "visibility", visible ? "visible" : "none");
        } else {
          // Layer not created yet (style still loading) — retry briefly.
          setTimeout(() => apply(), 50);
        }
      };
      const piersOn = layerVisible(layers, "piers");
      const blocksOn = layerVisible(layers, "blocks");
      const blockLabelsOn = layerVisible(layers, "blockLabels");
      const trackersOn = layerVisible(layers, "trackers");
      const rowLabelsOn = layerVisible(layers, "row_labels");
      // Icon overlay only renders when the user wants the icon variant
      // (default) or both. When set to "color" the dot's fill colour
      // alone communicates status — no icon.
      const wantIcon = pierStatusDisplay !== "color";
      show("piers-layer", piersOn);
      show("piers-selected", piersOn);
      show("pier-status-icons", piersOn && wantIcon);
      // Live-update the pier dot's colour expression when the user
      // flips the "Show status as" preference. Without this the
      // expression stays whatever was set inside on("load") and the
      // dropdown change has no visible effect on the map.
      if (map.getLayer("piers-layer")) {
        const wantStatusColor = pierStatusDisplay !== "icon";
        map.setPaintProperty("piers-layer", "circle-color",
          wantStatusColor
            ? ["case", ["!=", ["get", "status"], "New"], ["get", "status_color"], ["get", "color"]]
            : ["get", "color"],
        );
        map.setPaintProperty("piers-layer", "circle-stroke-width",
          wantStatusColor
            ? ["case", ["!=", ["get", "status"], "New"], 1.5, 0]
            : 0,
        );
      }
      show("blocks-fill", blocksOn);
      show("blocks-outline", blocksOn);
      show("blocks-selected", blocksOn);
      show("trackers-casing", trackersOn);
      show("trackers-line", trackersOn);
      show("trackers-selected", trackersOn);
      show("dccb-layer", layerVisible(layers, "dccb", false));
      show("inverters-layer", layerVisible(layers, "inverters", false));
      // Block labels: cheap toggle on existing markers (display:
      // none/""), no destroy-and-rebuild.  A separate effect below
      // owns the actual marker creation when the checkbox flips on
      // for the first time. This stops the visible flicker that used
      // to fire whenever ANY layer checkbox changed.
      for (const m of blockMarkersRef.current) {
        m.getElement().style.display = blockLabelsOn ? "" : "none";
      }
    };
    apply();
    // Row-label rendering lives in its OWN effect below so that toggling
    // Blocks / Block labels / Trackers doesn't destroy and rebuild the row
    // markers each time (previously this loop ran on every layer change
    // and visually wiped the row labels mid-toggle).
  }, [layers, pierLabelThreshold, pierDetailThreshold, pierStatusDisplay]);

  // ---- Row labels — dedicated effect ------------------------------------
  //
  // Only re-runs when Row-numbers visibility changes or when the underlying
  // pier data changes. Prevents Blocks / Block-labels toggles from
  // destroying and rebuilding the row-number markers.
  const rowLabelsOn = layerVisible(layers, "row_labels");
  useEffect(() => {
    refreshRowLabels();
  }, [rowLabelsOn, rowLabelData]);

  // ---- Tracker labels — dedicated effect --------------------------------
  //
  // Tracker codes (T0001…T1533) appear as small chips when the Trackers
  // checkbox is on AND the user is zoomed in enough to read them
  // (1 533 labels at site overview would be unreadable). The actual
  // rendering happens in refreshTrackerLabels which checks the zoom
  // level and the viewport — this effect just resets the label set
  // when the toggle or data changes.
  const trackersOnForLabels = layerVisible(layers, "trackers");
  useEffect(() => {
    refreshTrackerLabels();
  }, [trackersOnForLabels, trackerLabelData]);

  // ---- Block labels — dedicated effect ----------------------------------
  //
  // Block-label HTML markers are expensive to recreate (DOM + style +
  // map.addMarker per block). Rebuild only when the block set changes
  // or the BlockLabels checkbox actually flips. The visibility effect
  // above just toggles `display` on already-built markers, which is
  // cheap and doesn't blink.
  const blockLabelsOn = layerVisible(layers, "blockLabels");
  useEffect(() => {
    refreshBlockLabels();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [blockLabelsOn, blocks, imageWidth]);

  // ---- HTML marker helpers ----------------------------------------------

  function clearMarkers() {
    for (const m of pierLabelMarkersRef.current) m.remove();
    pierLabelMarkersRef.current = [];
    for (const m of rowLabelMarkersRef.current) m.remove();
    rowLabelMarkersRef.current = [];
    for (const m of trackerLabelMarkersRef.current) m.remove();
    trackerLabelMarkersRef.current = [];
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
  useEffect(() => { trackerLabelDataRef.current = trackerLabelData; }, [trackerLabelData]);

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

  // Tracker labels — small "T0001" pills centred on each tracker. With
  // 1 533 trackers we only render labels above a zoom threshold (the
  // map text would be unreadable below it) and clip to the viewport so
  // the marker count stays bounded as the user pans around.
  function refreshTrackerLabels() {
    const map = mapRef.current;
    if (!map) return;
    for (const m of trackerLabelMarkersRef.current) m.remove();
    trackerLabelMarkersRef.current = [];
    if (!layerVisible(layersRef.current, "trackers")) return;

    const bounds = map.getBounds();
    const zoom = map.getZoom();
    // Cap the number of labels rendered based on zoom level so the
    // user always sees *some* labels (not gated entirely by a zoom
    // threshold) but the count stays bounded:
    //   < zoom 11  → 0 labels (entire site overview, would be clutter)
    //   11..13     → up to 80 labels (sample across the viewport)
    //   13..15     → up to 250
    //   >= 15      → up to 600 (essentially everything in view)
    const cap = zoom < 11 ? 0
              : zoom < 13 ? 80
              : zoom < 15 ? 250
              : 600;
    if (cap === 0) return;

    // When the cap < total visible trackers, sample every Nth tracker
    // so the chips spread across the viewport instead of clustering
    // in whatever order Object.entries returns first.
    const allEntries = Object.entries(trackerLabelDataRef.current);
    const visible: [string, { lng: number; lat: number }][] = [];
    for (const e of allEntries) if (bounds.contains([e[1].lng, e[1].lat])) visible.push(e);
    const stride = visible.length > cap ? Math.ceil(visible.length / cap) : 1;

    let placed = 0;
    for (let i = 0; i < visible.length; i += stride) {
      const [code, pos] = visible[i];
      const el = document.createElement("div");
      el.textContent = code;
      el.style.cssText =
        "font: 700 10px Arial, sans-serif; color: #15803d; cursor: pointer; " +
        "background: rgba(255,255,255,0.92); border: 1px solid #86efac; " +
        "border-radius: 999px; padding: 0 6px; white-space: nowrap; " +
        "box-shadow: 0 1px 2px rgba(0,0,0,0.06); user-select: none;";
      el.addEventListener("mouseenter", () => { el.style.background = "#dcfce7"; });
      el.addEventListener("mouseleave", () => { el.style.background = "rgba(255,255,255,0.92)"; });
      el.addEventListener("click", (ev) => {
        ev.stopPropagation();
        onTrackerClick({ tracker_code: code });
      });
      const marker = new maplibregl.Marker({ element: el, anchor: "center" })
        .setLngLat([pos.lng, pos.lat])
        .addTo(map);
      trackerLabelMarkersRef.current.push(marker);
      placed++;
      if (placed >= cap) break;
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

    // `piers-layer` may not be in the style yet if the map fired a
    // zoom/move event before its on("load") handler ran (seen on slow
    // first-paint — MapLibre throws a synchronous error if any layer in
    // the filter list is missing).  Skip until it exists.
    if (!map.getLayer("piers-layer")) return;

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
  // A fixed square sits parked in the map's bottom-left corner (right
  // next to the side panel) at all times; the user drags it over an
  // area of interest and presses ✓ to zoom+select. No toolbar button
  // needed. +/- buttons on the square resize it in 20 px steps
  // (60 px min → 90 % of shorter side max).
  useEffect(() => {
    const map = mapRef.current;
    const container = containerRef.current;
    if (!map || !container) return;

    // The map container can still be reporting 0×0 right after lazy
    // loading. Pick a sensible default and let the ResizeObserver below
    // upgrade everything once the real container size is known.
    const minSide = 60;
    let side = 110;          // initial size used until container measures
    let maxSide = 600;       // recalculated once container has size
    const margin = 10;

    const box = document.createElement("div");
    // Anchor with `bottom`+`left` so the square is always parked at the
    // bottom-left even if the container hasn't laid out yet (useEffect
    // can fire before the lazy-Suspense parent has its real height).
    // The drag handler swaps `bottom` → `top` on first interaction.
    box.style.cssText =
      `position: absolute; left: ${margin}px; bottom: ${margin}px; ` +
      `width: ${side}px; height: ${side}px; ` +
      // Soft-dashed outline + a subtle tinted fill so the drag area is
      // discoverable without screaming for attention, and a crisp drop
      // shadow so it visibly sits above the map.
      `border: 1.5px dashed #334155; background: rgba(248,250,252,0.35); ` +
      `border-radius: 8px; cursor: grab; z-index: 20; touch-action: none; ` +
      `box-shadow: 0 2px 8px rgba(15,23,42,0.08);`;

    // Once the container actually has size, scale `side` to ~14 % of
    // the shorter edge and clamp to the new max. Box stays anchored
    // bottom-left via CSS `bottom` until the user interacts with it.
    const ro = new ResizeObserver(() => {
      const c = container.getBoundingClientRect();
      if (!c.width || !c.height) return;
      maxSide = Math.round(Math.min(c.width, c.height) * 0.9);
      const target = Math.round(Math.min(c.width, c.height) * 0.14);
      const next = Math.max(minSide, Math.min(maxSide, target));
      if (next !== side) {
        side = next;
        box.style.width = `${side}px`;
        box.style.height = `${side}px`;
      }
    });
    ro.observe(container);

    // Convert from CSS `bottom` to absolute `top` lazily, the first
    // time the user grabs the box. Without this, every mouse move
    // would have to recompute against `bottom`, and resizing wouldn't
    // keep the box pinned to the bottom-left until the user moves it.
    function pinToTop() {
      if (box.style.top) return;
      const c = container.getBoundingClientRect();
      const offsetTop = c.height - side - margin;
      box.style.top = `${Math.max(margin, offsetTop)}px`;
      box.style.bottom = "";
    }

    // Small pill-style toolbar parked at the top of the square with
    // icon-only buttons: ✓ apply, + grow, − shrink. Each button is a
    // rounded ghost that fills on hover, so the trio reads as a real
    // control set instead of three loose characters.
    const ctrl = document.createElement("div");
    ctrl.style.cssText =
      "position: absolute; top: -14px; left: 50%; transform: translateX(-50%); " +
      "display: flex; gap: 4px; padding: 3px; z-index: 3; " +
      "background: #ffffff; border: 1px solid #e2e8f0; border-radius: 999px; " +
      "box-shadow: 0 2px 10px rgba(15,23,42,0.12);";
    const ICON_CHECK =
      '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 12 10 18 20 6"/></svg>';
    const ICON_PLUS =
      '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>';
    const ICON_MINUS =
      '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"><line x1="5" y1="12" x2="19" y2="12"/></svg>';

    const mkBtn = (
      icon: string,
      title: string,
      variant: "primary" | "ghost",
      onClick: () => void,
    ) => {
      const b = document.createElement("button");
      b.type = "button";
      b.innerHTML = icon;
      b.title = title;
      b.setAttribute("aria-label", title);
      const isPrimary = variant === "primary";
      const baseBg   = isPrimary ? "#16a34a" : "transparent";
      const baseFg   = isPrimary ? "#ffffff" : "#0f172a";
      const hoverBg  = isPrimary ? "#15803d" : "#f1f5f9";
      b.style.cssText =
        `display: inline-flex; align-items: center; justify-content: center; ` +
        `width: 22px; height: 22px; padding: 0; border: none; ` +
        `background: ${baseBg}; color: ${baseFg}; border-radius: 999px; ` +
        `cursor: pointer; touch-action: manipulation; ` +
        `transition: background-color 120ms ease;`;
      b.addEventListener("mouseenter", () => { b.style.background = hoverBg; });
      b.addEventListener("mouseleave", () => { b.style.background = baseBg; });
      b.addEventListener("click", (ev) => { ev.stopPropagation(); onClick(); });
      b.addEventListener("pointerdown", (ev) => { ev.stopPropagation(); });
      return b;
    };
    ctrl.appendChild(mkBtn(ICON_CHECK, t("details.zoomHere", "Zoom & select this area"), "primary", () => applyZoom()));
    ctrl.appendChild(mkBtn(ICON_PLUS,  t("details.grow",     "Grow"),   "ghost", () => resize(+20)));
    ctrl.appendChild(mkBtn(ICON_MINUS, t("details.shrink",   "Shrink"), "ghost", () => resize(-20)));
    box.appendChild(ctrl);
    container.appendChild(box);

    // Resize no-op that used to manage the hint; kept as a stub so
    // resize() can call it without a conditional.
    function updateHintVisibility() { /* no-op */ }

    function resize(delta: number) {
      // First +/- click pins the box to top/left coords so we can
      // recompute its centre from `style.left/top`.
      pinToTop();
      const c = container.getBoundingClientRect();
      const newSide = Math.max(minSide, Math.min(maxSide, side + delta));
      const prevCX = parseFloat(box.style.left) + side / 2;
      const prevCY = parseFloat(box.style.top || "0") + side / 2;
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
      // Convert from CSS bottom→top so the move handler can use top.
      pinToTop();
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
      pinToTop();   // ensure style.top is populated for the math below
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

      // Report pier codes inside the square so the grid selection stays
      // in sync. Guard against the layer-not-ready race: MapLibre throws
      // synchronously when any layer in the filter list is missing.
      const features = map.getLayer("piers-layer")
        ? map.queryRenderedFeatures(
            [[x0 + dx, y0 + dy], [x1 + dx, y1 + dy]],
            { layers: ["piers-layer"] },
          )
        : [];
      const codes = new Set<string>();
      for (const f of features) {
        const c0 = (f.properties as any)?.pier_code;
        if (c0) codes.add(c0);
      }
      const picked = piersRef.current.filter((p: any) => codes.has(p.pier_code));
      onAreaSelect?.(picked);

      map.fitBounds(b, { padding: 32, duration: 450 });
      // Re-park in the (new) bottom-LEFT corner so the box stays reachable
      // after a zoom-in that shrinks the viewport in canvas pixels. Also
      // clamp `side` to the new container — otherwise the box overflows
      // a narrow viewport after an aggressive zoom-in and looks chopped
      // off.
      requestAnimationFrame(() => {
        const cc = container.getBoundingClientRect();
        const fit = Math.max(minSide, Math.min(side, Math.round(Math.min(cc.width, cc.height) * 0.5)));
        if (fit !== side) {
          side = fit;
          box.style.width = `${side}px`;
          box.style.height = `${side}px`;
          updateHintVisibility();
        }
        // Re-park to the bottom-left using CSS `bottom` (not `top`) so
        // the position survives any subsequent container resize.
        box.style.left = `${margin}px`;
        box.style.top = "";
        box.style.bottom = `${margin}px`;
      });
    }

    box.addEventListener("pointerdown", onDown);
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    return () => {
      ro.disconnect();
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
