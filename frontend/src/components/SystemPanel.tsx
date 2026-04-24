import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  getProject,
  getPlantInfo,
  updatePlantInfo,
  createProject,
  listProjectFiles,
  uploadProjectFile,
  clearProjectFiles,
  parseProject,
} from "../api";
import { useResponsive } from "../hooks/useResponsive";
import { useOnlineStatus } from "../hooks/useOnlineStatus";
import { BusyOverlay, ConfirmModal } from "./Modals";

interface Props {
  projectId: string;
  onProjectChanged?: (projectId: string) => void;
  /** Render only a specific section: "files" (upload/parse) or "info" (metadata/validation). */
  section?: "files" | "info";
  /** Project summary — passed from App.tsx so we don't re-fetch. */
  project?: any;
  /** Plant info — passed from App.tsx so we don't re-fetch. */
  plantInfo?: any;
  /** Called after plant info is updated so App can refresh its own state. */
  onPlantInfoChanged?: (info: any) => void;
}

export default function SystemPanel({ projectId, onProjectChanged, section, project: projectProp, plantInfo: plantInfoProp, onPlantInfoChanged }: Props) {
  const { t } = useTranslation();
  const { isMobile, isTablet } = useResponsive();
  const compact = isMobile || isTablet;
  const { online } = useOnlineStatus();
  const [error, setError] = useState("");
  // Use props from App when available; fall back to local state for backward compat.
  const [localProject, setLocalProject] = useState<any>(null);
  const [localPlantInfo, setLocalPlantInfo] = useState<any>(null);
  const project = projectProp ?? localProject;
  const plantInfo = plantInfoProp ?? localPlantInfo;
  const [editingPlant, setEditingPlant] = useState(false);
  const [plantDraft, setPlantDraft] = useState<any>({});
  const [files, setFiles] = useState<any[]>([]);
  const [parsing, setParsing] = useState(false);
  const [parseMsg, setParseMsg] = useState("");
  const [showNewProject, setShowNewProject] = useState(false);
  const [newProjectId, setNewProjectId] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [confirmState, setConfirmState] = useState<
    | null
    | { title: string; message: string; confirmLabel: string; danger?: boolean; action: () => void }
  >(null);

  // Only fetch files (lightweight); project + plantInfo come from props.
  async function refreshFiles() {
    if (!projectId) return;
    try {
      const fl = await listProjectFiles(projectId).catch(() => []);
      setFiles(fl);
    } catch (e: any) {
      setError(String(e.message || e));
    }
  }

  // Legacy: fetch everything only when props aren't provided.
  async function refreshAll() {
    if (!projectId) return;
    try {
      const [proj, pi, fl] = await Promise.all([
        projectProp ? Promise.resolve(null) : getProject(projectId).catch(() => null),
        plantInfoProp ? Promise.resolve(null) : getPlantInfo(projectId).catch(() => ({})),
        listProjectFiles(projectId).catch(() => []),
      ]);
      if (!projectProp) setLocalProject(proj);
      if (!plantInfoProp) setLocalPlantInfo(pi);
      setFiles(fl);
    } catch (e: any) {
      setError(String(e.message || e));
    }
  }

  useEffect(() => {
    setError("");
    setParseMsg("");
    setLocalProject(null);
    setLocalPlantInfo(null);
    setFiles([]);
    setEditingPlant(false);
    if (projectId) {
      if (projectProp && plantInfoProp) {
        refreshFiles();
      } else {
        refreshAll();
      }
    }
  }, [projectId]);

  async function handleCreateProject() {
    const id = newProjectId.trim();
    if (!id) return;
    try {
      await createProject({ project_id: id });
      setShowNewProject(false);
      setNewProjectId("");
      onProjectChanged?.(id);
    } catch (e: any) {
      setError(String(e.message || e));
    }
  }

  async function handleFileUpload(kind: string, file: File) {
    if (!projectId || !file) return;
    try {
      setBusy(`Uploading ${file.name}…`);
      await uploadProjectFile(projectId, kind, file);
      setBusy(`Refreshing file list…`);
      const fl = await listProjectFiles(projectId);
      setFiles(fl);
      setParseMsg(`Uploaded ${file.name}`);
      setTimeout(() => setParseMsg(""), 2000);
    } catch (e: any) {
      setError(String(e.message || e));
    } finally {
      setBusy(null);
    }
  }

  function handleClearFiles() {
    if (!projectId) return;
    setConfirmState({
      title: "Delete uploaded files?",
      message: "Delete all uploaded files for this project?\n(Parsed data will not be affected until you re-parse.)",
      confirmLabel: "Delete",
      danger: true,
      action: async () => {
        setConfirmState(null);
        try {
          setBusy("Clearing files…");
          await clearProjectFiles(projectId);
          setFiles([]);
        } catch (e: any) {
          setError(String(e.message || e));
        } finally {
          setBusy(null);
        }
      },
    });
  }

  function handleParse() {
    if (!projectId) return;
    setConfirmState({
      title: "Parse project?",
      message: "Parse will clear all existing project data and rebuild from uploaded files. Continue?",
      confirmLabel: "Parse",
      danger: true,
      action: async () => {
        setConfirmState(null);
        try {
          setParsing(true);
          setBusy("Parsing… this may take a minute or two");
          const result = await parseProject(projectId);
          setParseMsg(`Parsed: ${result.block_count} blocks, ${result.tracker_count} trackers, ${result.pier_count} piers`);
          await refreshAll();
          onProjectChanged?.(projectId);
        } catch (e: any) {
          setError(String(e.message || e));
          setParseMsg("");
        } finally {
          setParsing(false);
          setBusy(null);
        }
      },
    });
  }

  async function handlePlantSave() {
    if (!projectId) return;
    try {
      const toSave = { ...plantDraft };
      if (toSave.tolerance_ratio != null && toSave.tolerance_ratio !== "") {
        const n = parseFloat(toSave.tolerance_ratio);
        toSave.tolerance_ratio = isNaN(n) ? 0.05 : n;
      }
      const updated = await updatePlantInfo(projectId, toSave);
      setLocalPlantInfo(updated);
      onPlantInfoChanged?.(updated);
      setEditingPlant(false);
    } catch (e: any) {
      setError(String(e.message || e));
    }
  }

  return (
    <div style={{ display: "grid", gap: 14 }}>
      {/* Offline warning banner */}
      {!online && (
        <div
          style={{
            border: "1px solid #fecaca",
            background: "#fef2f2",
            color: "#991b1b",
            padding: "8px 12px",
            borderRadius: 10,
            fontSize: 12,
            fontWeight: 600,
          }}
        >
          You are offline. Uploading files, parsing, and creating projects are disabled.
          Pier status changes will keep working and sync automatically once you are back online.
        </div>
      )}

      {/* New Project + Files — shown when section is "files" or unset */}
      {(section === "files" || !section) && (<>
      {/* New Project + Files */}
      <div style={{ border: "1px solid #e2e8f0", borderRadius: 16, padding: compact ? 12 : 16, background: "#fff" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10, flexWrap: "wrap" }}>
          <div style={{ fontWeight: 800, fontSize: 16 }}>{t("sp.projectFiles")}</div>
          <button
            onClick={() => setShowNewProject(true)}
            disabled={!online}
            title={online ? "" : "Creating a project requires an internet connection"}
            style={{
              fontSize: 12,
              padding: "6px 12px",
              borderRadius: 6,
              border: "1px solid #d1d5db",
              background: online ? "#fff" : "#f1f5f9",
              cursor: online ? "pointer" : "not-allowed",
              opacity: online ? 1 : 0.6,
            }}
          >
            {t("sp.newProject")}
          </button>
        </div>
        {showNewProject && (
          <div style={{ display: "flex", gap: 6, marginBottom: 10, flexWrap: "wrap" }}>
            <input
              value={newProjectId}
              onChange={(e) => setNewProjectId(e.target.value)}
              placeholder={t("project.enterId")}
              style={{ flex: 1, minWidth: 180, padding: "6px 10px", borderRadius: 6, border: "1px solid #d1d5db", fontSize: 13 }}
            />
            <button onClick={handleCreateProject} style={{ fontSize: 12, padding: "6px 14px", borderRadius: 6, border: "none", background: "#0f172a", color: "#fff", cursor: "pointer" }}>{t("app.create")}</button>
            <button onClick={() => { setShowNewProject(false); setNewProjectId(""); }} style={{ fontSize: 12, padding: "6px 14px", borderRadius: 6, border: "1px solid #d1d5db", background: "#fff", cursor: "pointer" }}>{t("app.cancel")}</button>
          </div>
        )}
        {projectId ? (
          <>
            <div style={{ display: "grid", gridTemplateColumns: compact ? "1fr" : "1fr 1fr", gap: 10, marginBottom: 10 }}>
              <FileUploadField label="Construction PDF" kind="construction_pdf" files={files} onUpload={handleFileUpload} disabled={!online} />
              <FileUploadField label="Ramming PDF" kind="ramming_pdf" files={files} onUpload={handleFileUpload} disabled={!online} />
              <FileUploadField label="Block Mapping (image)" kind="block_mapping" files={files} onUpload={handleFileUpload} disabled={!online} />
            </div>
            <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
              <button
                onClick={handleParse}
                disabled={parsing || files.length < 2 || !online}
                title={online ? "" : "Parsing requires an internet connection"}
                style={{
                  fontSize: 13, padding: "8px 16px", borderRadius: 6, border: "none",
                  background: parsing || files.length < 2 || !online ? "#cbd5e1" : "#0f172a",
                  color: "#fff", fontWeight: 600,
                  cursor: parsing || files.length < 2 || !online ? "not-allowed" : "pointer",
                }}
              >
                {parsing ? t("sp.parsing") : t("sp.parse")}
              </button>
              {files.length > 0 && (
                <button
                  onClick={handleClearFiles}
                  disabled={!online}
                  title={online ? "" : "Clearing files requires an internet connection"}
                  style={{
                    fontSize: 12,
                    padding: "6px 10px",
                    borderRadius: 6,
                    border: "1px solid #d1d5db",
                    background: online ? "#fff" : "#f1f5f9",
                    cursor: online ? "pointer" : "not-allowed",
                    opacity: online ? 1 : 0.6,
                  }}
                >
                  {t("sp.clearFiles")}
                </button>
              )}
              {parseMsg && <span style={{ fontSize: 12, color: "#475569" }}>{parseMsg}</span>}
            </div>
          </>
        ) : (
          <div style={{ fontSize: 12, color: "#64748b" }}>{t("sp.selectOrCreate")}</div>
        )}
      </div>

      </>)}

      {/* Project Metadata Card — shown when section is "info" or unset */}
      {(section === "info" || !section) && (<>
      {/* Project Metadata Card */}
      {project && (
        <div style={{ border: "1px solid #e2e8f0", borderRadius: 16, padding: compact ? 12 : 16, background: "#f8fafc" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12, flexWrap: "wrap" }}>
            <div style={{ fontWeight: 800, fontSize: 16 }}>{t("sp.projectInfo")}</div>
            <span style={{ fontSize: 12, color: "#64748b", background: "#e2e8f0", padding: "2px 8px", borderRadius: 6 }}>{projectId}</span>
          </div>
          <SectionTitle>{t("sp.site")}</SectionTitle>
          <MetaGrid compact={compact}>
            <MetaField label={t("field.project")} value={projectId} />
            <MetaField label={t("field.projectNum")} value={plantInfo?.project_number} />
            <MetaField label={t("field.siteId")} value={plantInfo?.site_id} />
            <MetaField label={t("field.latLong")} value={plantInfo?.lat_long} />
            <MetaField label={t("field.windLoad")} value={plantInfo?.wind_load} />
            <MetaField label={t("field.snowLoad")} value={plantInfo?.snow_load} />
            <MetaField label={t("field.issueDate")} value={plantInfo?.issue_date} />
            <MetaField label={t("field.nextracker")} value={plantInfo?.nextracker_model} />
          </MetaGrid>

          <SectionTitle>{t("sp.structure")}</SectionTitle>
          <MetaGrid compact={compact}>
            <MetaField label={t("field.piers")} value={project.pier_count?.toLocaleString()} />
            <MetaField label={t("field.trackers")} value={project.tracker_count?.toLocaleString()} />
            <MetaField label={t("field.blocks")} value={project.block_count} />
            <MetaField label={t("field.rows")} value={project.row_count} />
          </MetaGrid>

          <SectionTitle>{t("sp.electrical")}</SectionTitle>
          <MetaGrid compact={compact}>
            <MetaField label={t("field.totalOutput")} value={plantInfo?.total_output_mw} />
            <MetaField label={t("field.inverters")} value={plantInfo?.inverters} />
            <MetaField label={t("field.dccb")} value={plantInfo?.dccb?.toLocaleString?.() ?? plantInfo?.dccb} />
            <MetaField label={t("field.stringGroups")} value={plantInfo?.string_groups} />
            <MetaField label={t("field.totalStrings")} value={plantInfo?.total_strings?.toLocaleString?.() ?? plantInfo?.total_strings} />
            <MetaField label={t("field.totalModules")} value={plantInfo?.total_modules?.toLocaleString?.() ?? plantInfo?.total_modules} />
            <MetaField label={t("field.modulesPerString")} value={plantInfo?.modules_per_string} />
            <MetaField label={t("field.devices")} value={plantInfo?.devices} />
          </MetaGrid>

          <SectionTitle>{t("sp.module")}</SectionTitle>
          <MetaGrid compact={compact}>
            <MetaField label={t("field.modulePower")} value={plantInfo?.module_capacity_w} />
            <MetaField label={t("field.length")} value={plantInfo?.module_length_m} />
            <MetaField label={t("field.width")} value={plantInfo?.module_width_m} />
            <MetaField label={t("field.pitch")} value={plantInfo?.pitch_m} />
          </MetaGrid>
          <SectionTitle>{t("sp.validation")}</SectionTitle>
          <MetaGrid compact={compact}>
            <ValidationField
              label={t("field.trackers")}
              actual={project.tracker_count}
              expected={plantInfo?.expected_trackers}
              tolerance={plantInfo?.tolerance_ratio ?? 0.05}
            />
            <ValidationField
              label={t("field.piers")}
              actual={project.pier_count}
              expected={plantInfo?.expected_piers}
              tolerance={plantInfo?.tolerance_ratio ?? 0.05}
            />
            <ValidationField
              label={t("field.totalModules")}
              actual={plantInfo?.total_modules}
              expected={plantInfo?.expected_modules_from_bom}
              tolerance={plantInfo?.tolerance_ratio ?? 0.05}
            />
            <MetaField label={t("field.tolerance")} value={`±${Math.round((plantInfo?.tolerance_ratio ?? 0.05) * 100)}%`} />
          </MetaGrid>

          {plantInfo?.notes && <div style={{ marginTop: 8, fontSize: 12, color: "#475569" }}>{plantInfo.notes}</div>}
          <div style={{ marginTop: 10 }}>
            {!editingPlant ? (
              <button onClick={() => { setPlantDraft({ ...plantInfo }); setEditingPlant(true); }} style={{ fontSize: 12, padding: "4px 10px", borderRadius: 6, border: "1px solid #d1d5db", background: "#fff", cursor: "pointer" }}>
                {t("sp.editPlantInfo")}
              </button>
            ) : (
              <div style={{ display: "grid", gridTemplateColumns: compact ? "1fr" : "1fr 1fr 1fr", gap: 8 }}>
                <PlantInput label="Total Output (MW)" field="total_output_mw" draft={plantDraft} setDraft={setPlantDraft} />
                <PlantInput label="Total Strings" field="total_strings" draft={plantDraft} setDraft={setPlantDraft} />
                <PlantInput label="Total Modules" field="total_modules" draft={plantDraft} setDraft={setPlantDraft} />
                <PlantInput label="Inverters" field="inverters" draft={plantDraft} setDraft={setPlantDraft} />
                <PlantInput label="DCCB" field="dccb" draft={plantDraft} setDraft={setPlantDraft} />
                <PlantInput label="Devices" field="devices" draft={plantDraft} setDraft={setPlantDraft} />
                <PlantInput label="Tolerance (0-1)" field="tolerance_ratio" draft={plantDraft} setDraft={setPlantDraft} />
                <div style={{ gridColumn: compact ? undefined : "1 / -1" }}>
                  <PlantInput label="Notes" field="notes" draft={plantDraft} setDraft={setPlantDraft} />
                </div>
                <div style={{ display: "flex", gap: 6 }}>
                  <button onClick={handlePlantSave} style={{ fontSize: 12, padding: "6px 14px", borderRadius: 6, border: "none", background: "#0f172a", color: "#fff", cursor: "pointer" }}>{t("app.save")}</button>
                  <button onClick={() => setEditingPlant(false)} style={{ fontSize: 12, padding: "6px 14px", borderRadius: 6, border: "1px solid #d1d5db", background: "#fff", cursor: "pointer" }}>{t("app.cancel")}</button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
      </>)}

      {error && <div style={{ color: "#b00020" }}>{error}</div>}

      {busy && <BusyOverlay message={busy} />}
      {confirmState && (
        <ConfirmModal
          title={confirmState.title}
          message={confirmState.message}
          confirmLabel={confirmState.confirmLabel}
          danger={confirmState.danger}
          onConfirm={confirmState.action}
          onCancel={() => setConfirmState(null)}
        />
      )}
    </div>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ fontSize: 11, fontWeight: 700, color: "#475569", textTransform: "uppercase", letterSpacing: 0.5, marginTop: 14, marginBottom: 6, borderBottom: "1px solid #e2e8f0", paddingBottom: 3 }}>
      {children}
    </div>
  );
}

function MetaGrid({ children, compact }: { children: React.ReactNode; compact: boolean }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: compact ? "1fr 1fr" : "repeat(4, 1fr)", gap: compact ? "8px 12px" : "8px 20px", fontSize: 13 }}>
      {children}
    </div>
  );
}

function MetaField({ label, value }: { label: string; value: any }) {
  return (
    <div>
      <div style={{ fontSize: 11, color: "#64748b", marginBottom: 2 }}>{label}</div>
      <div style={{ fontWeight: 600, fontSize: 14 }}>{value ?? "-"}</div>
    </div>
  );
}

function ValidationField({ label, actual, expected, tolerance }: { label: string; actual: any; expected: any; tolerance: number }) {
  const hasBoth = typeof actual === "number" && typeof expected === "number" && expected > 0;
  let status: "pass" | "fail" | "unknown" = "unknown";
  let diffPct = 0;
  if (hasBoth) {
    diffPct = (actual - expected) / expected;
    status = Math.abs(diffPct) <= tolerance ? "pass" : "fail";
  }
  const color = status === "pass" ? "#16a34a" : status === "fail" ? "#dc2626" : "#94a3b8";
  const icon = status === "pass" ? "✓" : status === "fail" ? "⚠" : "—";
  return (
    <div>
      <div style={{ fontSize: 11, color: "#64748b", marginBottom: 2 }}>{label}</div>
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <span style={{ fontWeight: 700, fontSize: 14, color }}>{icon}</span>
        <span style={{ fontWeight: 600, fontSize: 13 }}>
          {actual?.toLocaleString?.() ?? actual ?? "-"}
          {hasBoth && <span style={{ color: "#64748b", fontWeight: 400 }}> / {expected.toLocaleString()}</span>}
        </span>
      </div>
      {hasBoth && (
        <div style={{ fontSize: 10, color, marginTop: 1 }}>
          {diffPct >= 0 ? "+" : ""}{(diffPct * 100).toFixed(1)}%
        </div>
      )}
    </div>
  );
}

function FileUploadField({ label, kind, files, onUpload, disabled }: { label: string; kind: string; files: any[]; onUpload: (kind: string, file: File) => void; disabled?: boolean }) {
  const existing = files.filter((f) => f.kind === kind);
  return (
    <div style={{ border: "1px dashed #cbd5e1", borderRadius: 8, padding: 10, background: disabled ? "#f1f5f9" : "#f8fafc", opacity: disabled ? 0.6 : 1 }}>
      <div style={{ fontSize: 11, color: "#64748b", marginBottom: 4, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>{label}</div>
      {existing.length > 0 && (
        <div style={{ fontSize: 12, color: "#334155", marginBottom: 6 }}>
          {existing.map((f) => (
            <div key={f.id}>✓ {f.original_name || f.filename} ({(f.size_bytes / (1024 * 1024)).toFixed(1)} MB)</div>
          ))}
        </div>
      )}
      <input
        type="file"
        accept=".pdf,.png,.jpg,.jpeg"
        disabled={disabled}
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) {
            onUpload(kind, f);
            e.target.value = "";
          }
        }}
        style={{ fontSize: 12 }}
      />
    </div>
  );
}

function PlantInput({ label, field, draft, setDraft }: { label: string; field: string; draft: any; setDraft: (d: any) => void }) {
  return (
    <div>
      <div style={{ fontSize: 11, color: "#64748b", marginBottom: 2 }}>{label}</div>
      <input
        value={draft[field] ?? ""}
        onChange={(e) => setDraft({ ...draft, [field]: e.target.value || null })}
        style={{ width: "100%", padding: "6px 8px", borderRadius: 6, border: "1px solid #d1d5db", fontSize: 13, boxSizing: "border-box" }}
      />
    </div>
  );
}
