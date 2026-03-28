import { useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";

interface UploadFormProps {
  onImported?: () => void;
  siteId?: number;
}

export function UploadForm({ onImported, siteId }: UploadFormProps) {
  const { t } = useTranslation();
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<"idle" | "uploading" | "ok" | "error">("idle");
  const [message, setMessage] = useState("");

  const handleUpload = async () => {
    if (!file) return;
    setStatus("uploading");
    setMessage("");
    try {
      const res = await api.uploadFile(file, siteId);
      setStatus(res.success ? "ok" : "error");
      setMessage(res.message);
      if (res.success) {
        setFile(null);
        onImported?.();
      }
    } catch (e) {
      setStatus("error");
      setMessage(String(e));
    }
  };

  return (
    <div className="upload-form">
      <p className="hint" style={{ margin: "0 0 10px", fontSize: "var(--theme-font-size-xs)", color: "rgb(var(--theme-text-muted))" }}>
        {t("upload.hint")}
      </p>
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <input
          type="file"
          accept=".xls,.xlsx,.csv,.txt"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          style={{ fontSize: "var(--theme-font-size-xs)" }}
        />
        <button
          onClick={handleUpload}
          disabled={!file || status === "uploading"}
          style={{ padding: "6px 16px", borderRadius: 6, background: "rgb(var(--theme-action-accent))", color: "#fff", border: "none", cursor: "pointer", fontWeight: 600, fontSize: "var(--theme-font-size-xs)", opacity: (!file || status === "uploading") ? 0.6 : 1 }}
        >
          {status === "uploading" ? t("upload.uploading") : t("upload.upload")}
        </button>
      </div>
      {message && (
        <p style={{ margin: "8px 0 0", fontSize: "var(--theme-font-size-xs)", color: status === "ok" ? "#16a34a" : "#ef4444" }}>{message}</p>
      )}
    </div>
  );
}
