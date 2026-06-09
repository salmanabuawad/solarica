import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useResponsive } from "../hooks/useResponsive";

/**
 * String images modal — mirrors the buildingsmanager asset-files UX:
 * a thumbnail grid, upload, full-screen gallery viewer with prev/next, and
 * per-image delete. Read-only users (canEdit=false) only view.
 */
export default function StringImagesModal({
  code,
  images,
  canEdit,
  onUpload,
  onDelete,
  onClose,
}: {
  code: string;
  images: string[];
  canEdit: boolean;
  onUpload: (file: File) => void;
  onDelete: (url: string) => void;
  onClose: () => void;
}) {
  const { t, i18n } = useTranslation();
  const rtl = i18n.language === "he" || i18n.language === "ar";
  const { isMobile, isTablet } = useResponsive();
  const compact = isMobile || isTablet;
  const fileRef = useRef<HTMLInputElement>(null);
  const cameraRef = useRef<HTMLInputElement>(null);
  const [viewIdx, setViewIdx] = useState<number | null>(null);
  const [confirmUrl, setConfirmUrl] = useState<string | null>(null);

  const pick = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    files.forEach((f) => onUpload(f));
    // Reset whichever input fired (camera or gallery) so re-selecting the
    // same file fires change again.
    e.target.value = "";
  };

  const step = (d: number) => {
    if (viewIdx == null || images.length === 0) return;
    setViewIdx((viewIdx + d + images.length) % images.length);
  };

  return (
    <div
      onClick={onClose}
      style={{ position: "fixed", inset: 0, background: "rgba(15,23,42,0.7)", zIndex: 200, display: "flex", alignItems: "center", justifyContent: "center", padding: 20 }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        dir={rtl ? "rtl" : "ltr"}
        style={{ background: "#fff", borderRadius: 12, padding: 16, width: "min(900px, 94vw)", maxHeight: "88vh", overflow: "auto", boxShadow: "0 10px 40px rgba(0,0,0,0.4)" }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginBottom: 12 }}>
          <div style={{ fontWeight: 800, fontSize: 15 }}>{t("strings.col.images")} · {code} <span style={{ color: "#64748b", fontWeight: 600 }}>({images.length})</span></div>
          <div style={{ display: "flex", gap: 8 }}>
            {canEdit && (
              <>
                {/* Phone/tablet: capture straight from the rear camera. */}
                {compact && (
                  <>
                    <input ref={cameraRef} type="file" accept="image/*" capture="environment" style={{ display: "none" }} onChange={pick} />
                    <button onClick={() => cameraRef.current?.click()} style={btn("#2563eb", "#fff")}>📷 {t("strings.img.camera", "Camera")}</button>
                  </>
                )}
                {/* Gallery / file picker (also offers the camera on mobile). */}
                <input ref={fileRef} type="file" accept="image/*,video/*" multiple style={{ display: "none" }} onChange={pick} />
                <button onClick={() => fileRef.current?.click()} style={btn("#0f172a", "#fff")}>＋ {t("strings.img.upload", "Upload")}</button>
              </>
            )}
            <button onClick={onClose} style={btn("#fff", "#334155", "#cbd5e1")}>✕</button>
          </div>
        </div>

        {images.length === 0 ? (
          <div style={{ color: "#94a3b8", textAlign: "center", padding: "48px 0" }}>{t("strings.img.none", "No images")}</div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))", gap: 10 }}>
            {images.map((src, i) => (
              <div key={i} style={{ position: "relative", border: "1px solid #e2e8f0", borderRadius: 8, overflow: "hidden", background: "#f8fafc" }}>
                <button
                  onClick={() => setViewIdx(i)}
                  style={{ display: "block", width: "100%", height: 130, border: 0, padding: 0, cursor: "pointer", background: "#f1f5f9" }}
                  title={t("strings.img.view", "View")}
                >
                  <img src={src} alt={`${code} ${i + 1}`} style={{ width: "100%", height: "100%", objectFit: "cover" }} loading="lazy" />
                </button>
                {canEdit && (
                  <button
                    onClick={() => setConfirmUrl(src)}
                    title={t("strings.img.delete", "Delete")}
                    style={{ position: "absolute", top: 4, [rtl ? "left" : "right"]: 4, width: 26, height: 26, borderRadius: 6, border: "none", background: "rgba(220,38,38,0.92)", color: "#fff", cursor: "pointer", fontSize: 13, lineHeight: 1 } as React.CSSProperties}
                  >🗑</button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Full-screen gallery viewer */}
      {viewIdx != null && images[viewIdx] && (
        <div
          onClick={(e) => { e.stopPropagation(); setViewIdx(null); }}
          style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.85)", zIndex: 210, display: "flex", alignItems: "center", justifyContent: "center" }}
        >
          <button onClick={(e) => { e.stopPropagation(); step(-1); }} style={navBtn(rtl ? "right" : "left")}>‹</button>
          <img src={images[viewIdx]} alt="" onClick={(e) => e.stopPropagation()} style={{ maxWidth: "88vw", maxHeight: "86vh", objectFit: "contain", borderRadius: 8 }} />
          <button onClick={(e) => { e.stopPropagation(); step(1); }} style={navBtn(rtl ? "left" : "right")}>›</button>
          <div style={{ position: "fixed", top: 16, [rtl ? "left" : "right"]: 20, color: "#fff", fontWeight: 700 } as React.CSSProperties}>{viewIdx + 1} / {images.length}</div>
          <button onClick={(e) => { e.stopPropagation(); setViewIdx(null); }} style={{ position: "fixed", top: 14, [rtl ? "right" : "left"]: 20, background: "rgba(255,255,255,0.15)", color: "#fff", border: "none", borderRadius: 8, padding: "6px 12px", cursor: "pointer", fontWeight: 700 } as React.CSSProperties}>✕</button>
        </div>
      )}

      {/* Delete confirm */}
      {confirmUrl && (
        <div onClick={(e) => { e.stopPropagation(); setConfirmUrl(null); }} style={{ position: "fixed", inset: 0, background: "rgba(15,23,42,0.6)", zIndex: 220, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <div onClick={(e) => e.stopPropagation()} dir={rtl ? "rtl" : "ltr"} style={{ background: "#fff", borderRadius: 10, padding: 20, width: "min(380px, 90vw)" }}>
            <div style={{ fontWeight: 700, marginBottom: 14 }}>{t("strings.img.confirmDelete", "Delete this image?")}</div>
            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <button onClick={() => setConfirmUrl(null)} style={btn("#fff", "#334155", "#cbd5e1")}>{t("app.cancel", "Cancel")}</button>
              <button onClick={() => { onDelete(confirmUrl); if (viewIdx != null) setViewIdx(null); setConfirmUrl(null); }} style={btn("#dc2626", "#fff")}>{t("strings.img.delete", "Delete")}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function btn(bg: string, color: string, border?: string): React.CSSProperties {
  return { background: bg, color, border: `1px solid ${border || bg}`, borderRadius: 8, padding: "6px 12px", cursor: "pointer", fontWeight: 600, fontSize: 13 };
}
function navBtn(side: "left" | "right"): React.CSSProperties {
  return { position: "fixed", [side]: 12, top: "50%", transform: "translateY(-50%)", width: 48, height: 48, borderRadius: "50%", border: "none", background: "rgba(255,255,255,0.18)", color: "#fff", fontSize: 30, cursor: "pointer", zIndex: 211 } as React.CSSProperties;
}
