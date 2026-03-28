/**
 * PdfRegionPicker
 *
 * Renders the first page of a PDF file in a canvas and lets the user draw
 * one or more selection rectangles.  Regions are returned as normalised
 * {x, y, w, h} values in the range [0, 1] relative to the top-left corner
 * of the page — the same convention used by the browser canvas and expected
 * by the backend's coordinate-conversion logic.
 */

import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

export interface PdfRegion {
  x: number; // left edge   (0 = page left,  1 = page right)
  y: number; // top edge    (0 = page top,   1 = page bottom)
  w: number; // width       (fraction of page width)
  h: number; // height      (fraction of page height)
}

interface Props {
  file: File;
  regions: PdfRegion[];
  onChange: (regions: PdfRegion[]) => void;
}

const MAX_CANVAS_WIDTH = 860;

export function PdfRegionPicker({ file, regions, onChange }: Props) {
  const { t } = useTranslation();
  const pdfCanvasRef = useRef<HTMLCanvasElement>(null);
  const overlayCanvasRef = useRef<HTMLCanvasElement>(null);
  const [loading, setLoading] = useState(true);
  const [renderError, setRenderError] = useState<string | null>(null);

  // Drag state kept in a ref to avoid stale closure issues in mouse handlers
  const dragStartRef = useRef<{ x: number; y: number } | null>(null);
  const [liveRect, setLiveRect] = useState<PdfRegion | null>(null);

  // ── Render first page ───────────────────────────────────────────────────
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setRenderError(null);

    async function render() {
      try {
        // Dynamic import so the ~2 MB bundle is only loaded when needed
        const pdfjsLib = await import("pdfjs-dist");
        pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
          "pdfjs-dist/build/pdf.worker.min.mjs",
          import.meta.url,
        ).href;

        const arrayBuffer = await file.arrayBuffer();
        const doc = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
        const page = await doc.getPage(1);
        if (cancelled) return;

        const viewport0 = page.getViewport({ scale: 1 });
        const scale = Math.min(MAX_CANVAS_WIDTH / viewport0.width, 2.5);
        const viewport = page.getViewport({ scale });

        const pdf = pdfCanvasRef.current;
        const overlay = overlayCanvasRef.current;
        if (!pdf || !overlay) return;

        pdf.width = Math.round(viewport.width);
        pdf.height = Math.round(viewport.height);
        overlay.width = pdf.width;
        overlay.height = pdf.height;

        await page.render({
          canvasContext: pdf.getContext("2d")!,
          viewport,
          canvas: pdf,
        } as Parameters<typeof page.render>[0]).promise;

        if (!cancelled) setLoading(false);
      } catch (e) {
        if (!cancelled) {
          setRenderError(e instanceof Error ? e.message : "Failed to render PDF");
          setLoading(false);
        }
      }
    }

    render();
    return () => {
      cancelled = true;
    };
  }, [file]);

  // ── Redraw overlay whenever regions or liveRect changes ─────────────────
  useEffect(() => {
    const overlay = overlayCanvasRef.current;
    if (!overlay || loading) return;
    const ctx = overlay.getContext("2d");
    if (!ctx) return;

    const W = overlay.width;
    const H = overlay.height;
    ctx.clearRect(0, 0, W, H);

    // Committed regions — blue
    regions.forEach((r, i) => {
      const x = r.x * W, y = r.y * H, w = r.w * W, h = r.h * H;
      ctx.fillStyle = "rgba(37, 99, 235, 0.13)";
      ctx.fillRect(x, y, w, h);
      ctx.strokeStyle = "#2563eb";
      ctx.lineWidth = 2;
      ctx.setLineDash([]);
      ctx.strokeRect(x, y, w, h);
      ctx.fillStyle = "#fff";
      ctx.font = `bold ${Math.max(11, Math.round(W / 70))}px sans-serif`;
      ctx.fillText(String(i + 1), x + 6, y + 16);
    });

    // Live drag rect — amber dashed
    if (liveRect) {
      const x = liveRect.x * W, y = liveRect.y * H, w = liveRect.w * W, h = liveRect.h * H;
      ctx.fillStyle = "rgba(245, 158, 11, 0.12)";
      ctx.fillRect(x, y, w, h);
      ctx.strokeStyle = "#f59e0b";
      ctx.lineWidth = 2;
      ctx.setLineDash([6, 3]);
      ctx.strokeRect(x, y, w, h);
      ctx.setLineDash([]);
    }
  }, [regions, liveRect, loading]);

  // ── Mouse helpers ────────────────────────────────────────────────────────
  function normPos(e: React.MouseEvent<HTMLCanvasElement>) {
    const rect = e.currentTarget.getBoundingClientRect();
    return {
      x: Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width)),
      y: Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height)),
    };
  }

  function handleMouseDown(e: React.MouseEvent<HTMLCanvasElement>) {
    e.preventDefault();
    dragStartRef.current = normPos(e);
  }

  function handleMouseMove(e: React.MouseEvent<HTMLCanvasElement>) {
    if (!dragStartRef.current) return;
    const { x: sx, y: sy } = dragStartRef.current;
    const p = normPos(e);
    setLiveRect({
      x: Math.min(sx, p.x),
      y: Math.min(sy, p.y),
      w: Math.abs(p.x - sx),
      h: Math.abs(p.y - sy),
    });
  }

  function commitDrag(e: React.MouseEvent<HTMLCanvasElement>) {
    if (!dragStartRef.current) return;
    const { x: sx, y: sy } = dragStartRef.current;
    const p = normPos(e);
    const w = Math.abs(p.x - sx);
    const h = Math.abs(p.y - sy);
    dragStartRef.current = null;
    setLiveRect(null);
    if (w > 0.01 && h > 0.01) {
      onChange([
        ...regions,
        { x: Math.min(sx, p.x), y: Math.min(sy, p.y), w, h },
      ]);
    }
  }

  // ── Render ───────────────────────────────────────────────────────────────
  return (
    <div className="pdf-region-picker">
      {loading && <div className="pdf-rp-loading">{t("common.loading")}</div>}
      {renderError && <div className="pdf-rp-error">{renderError}</div>}

      <div
        className="pdf-canvas-wrapper"
        style={{ display: loading || renderError ? "none" : undefined }}
      >
        <canvas ref={pdfCanvasRef} className="pdf-render-canvas" />
        <canvas
          ref={overlayCanvasRef}
          className="pdf-overlay-canvas"
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={commitDrag}
          onMouseLeave={commitDrag}
        />
      </div>

      {!loading && !renderError && regions.length === 0 && (
        <p className="pdf-rp-hint">{t("sitePanel.regionPickerHint")}</p>
      )}

      {regions.length > 0 && (
        <div className="pdf-regions-list">
          {regions.map((_, i) => (
            <span key={i} className="pdf-region-tag">
              {t("sitePanel.regionLabel", { n: i + 1 })}
              <button
                type="button"
                className="pdf-region-remove"
                onClick={() => onChange(regions.filter((__, j) => j !== i))}
                title="Remove"
              >
                ×
              </button>
            </span>
          ))}
          <button
            type="button"
            className="pdf-clear-btn"
            onClick={() => onChange([])}
          >
            {t("sitePanel.clearRegions")}
          </button>
        </div>
      )}
    </div>
  );
}
