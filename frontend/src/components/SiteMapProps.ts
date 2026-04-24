export interface SiteMapProps {
  imageWidth: number;
  imageHeight: number;
  blocks: any[];
  trackers: any[];
  piers: any[];
  /** DCCB devices extracted by the security module (`{type, name, x, y}`). */
  dccbs?: any[];
  /** Inverter devices extracted by the security module (`{type, name, x, y}`). */
  inverters?: any[];
  pierStatuses?: Record<string, string>;
  selectedBlock: any;
  selectedTracker: any;
  selectedPier: any;
  layers: { key: string; visible: boolean }[];
  onBlockClick: (b: any) => void;
  onTrackerClick: (t: any) => void;
  onPierClick: (p: any) => void;
  /** Called when the user finishes a box/touch area selection. */
  onAreaSelect?: (piers: any[]) => void;
  /** Shared bulk selection — pier codes currently selected in either view. */
  bulkSelectedPierCodes?: Set<string>;
  /** Pier-code labels show only when the number of visible piers is ≤ this. */
  pierLabelThreshold?: number;
  /** Full detail cards show only when the number of visible piers is ≤ this. */
  pierDetailThreshold?: number;
}

/** Fill colours for the five pier types. */
export const PIER_COLORS: Record<string, string> = {
  HAP: "#ff0000",
  HMP: "#ff0000",
  SAP: "#00ffff",
  SAPE: "#0000ff",
  SAPEND: "#ff8c00",
  SMP: "#00ff00",
  UNKNOWN: "#64748b",
};

/** Status ring colors, matching PierModal and SimpleGrid. */
export const STATUS_COLORS: Record<string, string> = {
  "New": "",                      // no ring
  "In Progress": "#eab308",       // yellow
  "Implemented": "#10b981",       // light green
  "Approved": "#16a34a",          // green
  "Rejected": "#ef4444",          // red
  "Fixed": "#2563eb",             // blue
};

/**
 * Rotate the PDF-space point 90° counter-clockwise so the rendered map reads
 * the same way as the construction drawings.
 *   raw (x, y)  →  rotated (y, imageWidth - x)
 */
export function rotate90CCW(x: number, y: number, imageWidth: number): [number, number] {
  return [y, imageWidth - x];
}

export function layerVisible(
  layers: { key: string; visible: boolean }[],
  key: string,
  fallback = true,
): boolean {
  return layers.find((l) => l.key === key)?.visible ?? fallback;
}
