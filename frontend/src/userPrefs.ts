/**
 * Tiny wrapper around localStorage for per-user preferences. Every getter
 * is safe to call during SSR / before the DOM is ready (returns the default
 * if window is undefined).
 */

const KEYS = {
  pierLabelThreshold: "solarica.pierLabelThreshold",
  pierDetailThreshold: "solarica.pierDetailThreshold",
} as const;

const DEFAULTS = {
  pierLabelThreshold: 25,
  pierDetailThreshold: 4,
};

function readNumber(key: string, fallback: number): number {
  if (typeof window === "undefined") return fallback;
  const raw = window.localStorage.getItem(key);
  if (raw == null) return fallback;
  const n = Number(raw);
  return Number.isFinite(n) ? n : fallback;
}

function writeNumber(key: string, value: number) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(key, String(value));
  } catch {
    // ignore quota errors
  }
}

export const userPrefs = {
  getPierLabelThreshold: () => readNumber(KEYS.pierLabelThreshold, DEFAULTS.pierLabelThreshold),
  setPierLabelThreshold: (v: number) => writeNumber(KEYS.pierLabelThreshold, v),
  getPierDetailThreshold: () => readNumber(KEYS.pierDetailThreshold, DEFAULTS.pierDetailThreshold),
  setPierDetailThreshold: (v: number) => writeNumber(KEYS.pierDetailThreshold, v),
};
