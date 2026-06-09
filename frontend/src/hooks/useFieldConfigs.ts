import { useEffect, useState } from "react";
import { FieldConfig, listFieldConfigs } from "../api";

/** Per-grid column preferences, keyed by field_name. */
export type FieldConfigMap = Record<string, FieldConfig>;

/**
 * Fetch the field configuration for a single grid and expose a lookup map
 * keyed by field_name.  Returns `null` while loading so grids can render
 * their fallback column defs instead of flashing an unconfigured layout.
 */
export function useFieldConfigs(gridName: string | null | undefined): FieldConfigMap | null {
  const [map, setMap] = useState<FieldConfigMap | null>(null);

  useEffect(() => {
    if (!gridName) { setMap({}); return; }
    let cancelled = false;
    listFieldConfigs(gridName)
      .then((rows) => {
        if (cancelled) return;
        const m: FieldConfigMap = {};
        for (const r of rows) m[r.field_name] = r;
        setMap(m);
      })
      .catch(() => {
        if (cancelled) return;
        // Non-fatal — grids fall back to their hardcoded defaults.
        setMap({});
      });
    return () => { cancelled = true; };
  }, [gridName]);

  return map;
}

/**
 * Apply a FieldConfigMap to a flat array of ag-grid column defs.
 *  - Drops columns whose config says visible = false.
 *  - Rewrites headerName if a display_name was set.
 *  - Applies pin_side → pinned ("left" | "right" | null).
 *  - Applies width.
 *  - Sorts by column_order (columns with no explicit order keep their
 *    relative position at the end).
 *
 * Accepts ColGroupDef trees (with `children`) and applies per-leaf.
 */
export function applyFieldConfigs(
  cols: any[],
  configs: FieldConfigMap | null,
  widthMultiplier: number = 1,
  rtl: boolean = false,
): any[] {
  // In RTL the visual "start" is the right edge, so a left-pinned column should
  // pin right (and vice-versa). enableRtl reverses the centre columns; this
  // flips the pinned ones to match.
  const flipPin = (p: any) => rtl ? (p === "left" ? "right" : p === "right" ? "left" : p) : p;
  if (!configs || Object.keys(configs).length === 0) {
    return rtl ? cols.map((c) => (c.pinned ? { ...c, pinned: flipPin(c.pinned) } : c)) : cols;
  }

  const transform = (col: any): any | null => {
    if (col.children) {
      const kids = col.children.map(transform).filter(Boolean);
      if (kids.length === 0) return null;
      return { ...col, children: kids };
    }
    const cfg = configs[col.field];
    if (!cfg) return col.pinned ? { ...col, pinned: flipPin(col.pinned) } : col;
    if (cfg.visible === false) return null;
    const merged: any = { ...col };
    // NB: we intentionally do NOT override headerName with cfg.display_name.
    // display_name is a single (English) string, so applying it would defeat
    // i18n — the column defs already pass translated headerName via t().
    if (cfg.pin_side) merged.pinned = flipPin(cfg.pin_side);
    else if (cfg.pin_side === null && col.pinned) merged.pinned = undefined;
    else if (col.pinned) merged.pinned = flipPin(col.pinned);
    if (cfg.width != null) {
      // Scale the configured width by the multiplier (used on mobile
      // to render columns at e.g. 70 % of the desktop width). Floored
      // at 30 px so a small multiplier can't collapse a column.
      const scaled = Math.max(30, Math.round(cfg.width * widthMultiplier));
      merged.width = scaled;
      merged.minWidth = Math.min(col.minWidth ?? 60, scaled);
    }
    // ag-grid rejects custom top-level props; stash our order in `context`.
    merged.context = { ...(col.context || {}), fc_order: cfg.column_order ?? Number.POSITIVE_INFINITY };
    return merged;
  };

  const processed = cols.map(transform).filter(Boolean);

  // Sort leaves & group children by fc_order. Groups sort by the min
  // fc_order of their children so you can reorder whole bands too.
  const minOrder = (node: any): number => {
    if (node.children) {
      const v = node.children.map(minOrder);
      return Math.min(...v);
    }
    return (node.context?.fc_order) ?? Number.POSITIVE_INFINITY;
  };
  const sortTree = (node: any): any => {
    if (!node.children) return node;
    const kids = node.children.slice().sort((a: any, b: any) => minOrder(a) - minOrder(b)).map(sortTree);
    return { ...node, children: kids };
  };
  return processed.slice().sort((a: any, b: any) => minOrder(a) - minOrder(b)).map(sortTree);
}
