import { useState, useRef, useEffect } from 'react';
import {
  Upload, FileSearch, AlertTriangle, CheckCircle2, XCircle,
  ChevronDown, ChevronRight, Info, Zap, MapPin, Layers, BarChart2,
  FileText, FolderOpen, Trash2, X, Cpu, Activity,
} from 'lucide-react';
import * as api from '../../lib/api';
import type { StringScanResult } from '../../lib/api';

interface Props {
  projectId: number;
  /** Pre-uploaded project files (from project_files route) */
  projectFiles?: { id: string; original_name: string; file_type: string; is_active?: boolean }[];
}

export default function ProjectStrings({ projectId, projectFiles = [] }: Props) {
  const [result, setResult] = useState<StringScanResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedFileIds, setSelectedFileIds] = useState<string[]>([]);
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set());
  const [showUploadModal, setShowUploadModal] = useState(false);

  // Only active files appear in the scan selector; inactive ones are excluded
  const pdfFiles = projectFiles.filter(f => f.file_type === 'PDF' && f.is_active !== false);

  function toggleSection(key: string) {
    setExpandedSections(prev => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  }

  function toggleFileId(id: string) {
    setSelectedFileIds(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id],
    );
  }

  async function runScan(uploadedFiles?: FileList) {
    if (!selectedFileIds.length && !uploadedFiles?.length) {
      setError('Select at least one PDF file to scan.');
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await api.scanProjectStrings(
        projectId,
        selectedFileIds.length ? selectedFileIds : undefined,
        uploadedFiles || undefined,
      );
      setResult(res);
      // auto-expand all sections
      setExpandedSections(new Set(Object.keys(res.strings)));
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Scan failed.');
    } finally {
      setLoading(false);
    }
  }

  function handleUploadScan(files: FileList) {
    setShowUploadModal(false);
    runScan(files);
  }

  /* ── helpers ── */
  const hasGaps = result && Object.keys(result.gaps).length > 0;
  const hasDuplicates = result && result.duplicates.length > 0;
  const hasAnomalies = result && Object.keys(result.anomalies).length > 0;

  return (
    <>
    {showUploadModal && (
      <UploadScanModal
        onClose={() => setShowUploadModal(false)}
        onScan={handleUploadScan}
      />
    )}
    {/* Busy overlay */}
    {loading && <ScanBusyOverlay />}
    <div className="space-y-5">
      {/* ── File selection panel ── */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
          <FileSearch className="h-4 w-4 text-blue-600" />
          String Extraction — Select Design Files
        </h3>

        {pdfFiles.length > 0 && (
          <div className="mb-4">
            <p className="text-xs text-gray-500 mb-2">Project PDFs (already uploaded):</p>
            <div className="flex flex-wrap gap-2">
              {pdfFiles.map(f => (
                <button
                  key={f.id}
                  onClick={() => toggleFileId(f.id)}
                  className={`px-3 py-1.5 rounded-lg border text-xs font-medium transition-colors ${
                    selectedFileIds.includes(f.id)
                      ? 'bg-blue-600 text-white border-blue-600'
                      : 'bg-gray-50 text-gray-700 border-gray-200 hover:border-blue-400'
                  }`}
                >
                  {f.original_name}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="flex items-center gap-3 flex-wrap">
          {selectedFileIds.length > 0 && (
            <button
              onClick={() => runScan()}
              disabled={loading}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
            >
              {loading ? (
                <span className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
              ) : (
                <Zap className="h-4 w-4" />
              )}
              Scan Selected ({selectedFileIds.length})
            </button>
          )}

          {pdfFiles.length === 0 && (
            <button
              onClick={() => setShowUploadModal(true)}
              disabled={loading}
              className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-200 disabled:opacity-50 flex items-center gap-2 border border-gray-200"
            >
              <Upload className="h-4 w-4" />
              Upload &amp; Scan PDF
            </button>
          )}
        </div>

        {error && (
          <div className="mt-3 flex items-start gap-2 text-red-600 text-sm bg-red-50 rounded-lg p-3">
            <XCircle className="h-4 w-4 shrink-0 mt-0.5" />
            {error}
          </div>
        )}
      </div>

      {/* ── Results ── */}
      {result && (
        <>
          {/* Site metadata */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h3 className="font-semibold text-gray-800 mb-4 flex items-center gap-2">
              <Info className="h-4 w-4 text-blue-600" />
              Site Details
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              {[
                { label: 'Site Code',    value: result.site_code },
                { label: 'Site Name',    value: result.site_name },
                { label: 'Layout',       value: result.layout_name },
                { label: 'Country',      value: result.country },
                { label: 'Region',       value: result.region },
                { label: 'Capacity',     value: result.plant_capacity_mw != null ? `${result.plant_capacity_mw} MW` : null },
                { label: 'Module Type',  value: result.module_type },
                { label: 'Module Count', value: result.module_count?.toLocaleString() ?? null },
              ].map(({ label, value }) => (
                <div key={label}>
                  <p className="text-xs text-gray-500">{label}</p>
                  <p className="font-medium text-gray-900">{value ?? '—'}</p>
                </div>
              ))}
              {(result.latitude != null && result.longitude != null) && (
                <div className="col-span-2 flex items-center gap-1 text-gray-600 text-xs">
                  <MapPin className="h-3 w-3" />
                  {result.latitude}N, {result.longitude}E
                </div>
              )}
            </div>
          </div>

          {/* Summary bar */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatCard label="Total Strings" value={result.valid_count + result.invalid_count} color="blue" icon={<Layers className="h-5 w-5" />} />
            <StatCard label="Valid" value={result.valid_count} color="green" icon={<CheckCircle2 className="h-5 w-5" />} />
            <StatCard label="Invalid / Dupes" value={result.invalid_count} color={result.invalid_count > 0 ? 'red' : 'gray'} icon={<XCircle className="h-5 w-5" />} />
            <StatCard label="Gap Groups" value={Object.keys(result.gaps).length} color={hasGaps ? 'yellow' : 'gray'} icon={<BarChart2 className="h-5 w-5" />} />
          </div>

          {/* Status banner */}
          <div className={`rounded-xl border p-4 flex items-center gap-3 ${
            result.has_errors
              ? 'bg-red-50 border-red-200 text-red-700'
              : hasGaps
              ? 'bg-yellow-50 border-yellow-200 text-yellow-700'
              : 'bg-green-50 border-green-200 text-green-700'
          }`}>
            {result.has_errors ? <XCircle className="h-5 w-5 shrink-0" /> :
             hasGaps ? <AlertTriangle className="h-5 w-5 shrink-0" /> :
             <CheckCircle2 className="h-5 w-5 shrink-0" />}
            <span className="font-medium text-sm">
              {result.has_errors
                ? `${result.invalid_count} invalid or duplicate string(s) found — review before import.`
                : hasGaps
                ? `All strings valid, but ${Object.keys(result.gaps).length} gap group(s) detected.`
                : 'All strings valid with no gaps detected.'}
            </span>
          </div>

          {/* Gaps */}
          {hasGaps && (
            <Section title={`Sequence Gaps (${Object.keys(result.gaps).length} groups)`} color="yellow" icon={<AlertTriangle className="h-4 w-4" />}>
              <div className="space-y-2">
                {Object.entries(result.gaps).map(([group, missing]) => (
                  <div key={group} className="flex items-start gap-3 text-sm">
                    <span className="font-mono font-medium text-yellow-700 w-24 shrink-0">{group}</span>
                    <span className="text-gray-600">Missing: <span className="font-mono text-xs">{missing.join(', ')}</span></span>
                  </div>
                ))}
              </div>
            </Section>
          )}

          {/* Duplicates */}
          {hasDuplicates && (
            <Section title={`Duplicate Strings (${result.duplicates.length})`} color="red" icon={<XCircle className="h-4 w-4" />}>
              <div className="flex flex-wrap gap-2">
                {result.duplicates.map(code => (
                  <span key={code} className="px-2 py-1 bg-red-50 text-red-700 rounded font-mono text-xs border border-red-200">{code}</span>
                ))}
              </div>
            </Section>
          )}

          {/* Anomalies */}
          {hasAnomalies && (
            <Section title={`Anomalies / Malformed Codes (${Object.keys(result.anomalies).length} groups)`} color="orange" icon={<AlertTriangle className="h-4 w-4" />}>
              <div className="space-y-2">
                {Object.entries(result.anomalies).map(([key, vals]) => (
                  <div key={key} className="flex items-start gap-3 text-sm">
                    <span className="font-mono font-medium text-orange-700 w-28 shrink-0">{key}</span>
                    <span className="font-mono text-xs text-gray-600">{vals.join(', ')}</span>
                  </div>
                ))}
              </div>
            </Section>
          )}

          {/* Inverters panel */}
          {result.inverters && result.inverters.length > 0 && (
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold text-gray-800 flex items-center gap-2">
                  <Cpu className="h-4 w-4 text-indigo-600" />
                  Inverters Detected
                </h3>
                <div className="flex items-center gap-3 text-xs text-gray-500">
                  <span className="font-semibold text-gray-700">{result.inverters.length}</span> inverters
                  {result.total_strings_doc && (
                    <span className="text-gray-500">· doc total: {result.total_strings_doc} strings</span>
                  )}
                  {result.dc_string_buckets_found && result.dc_string_buckets_found.length > 0 && (
                    <span className="text-blue-600 font-medium">
                      DC buckets: {result.dc_string_buckets_found.join(' / ')}s
                    </span>
                  )}
                </div>
              </div>

              {/* Group by section (first number of inverter key) */}
              {(() => {
                const bySection: Record<string, typeof result.inverters> = {};
                for (const inv of result.inverters) {
                  const sec = inv.raw_name.split('.')[0];
                  if (!bySection[sec]) bySection[sec] = [];
                  bySection[sec].push(inv);
                }
                const missingByInv = result.missing_strings_by_inverter ?? {};
                return Object.entries(bySection).map(([sec, invs]) => (
                  <div key={sec} className="mb-5 last:mb-0">
                    <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                      Section {sec} — {invs.length} inverters
                    </p>
                    <div className="grid grid-cols-4 sm:grid-cols-6 md:grid-cols-8 lg:grid-cols-10 gap-2">
                      {invs.map(inv => {
                        const isInferred = inv.pattern === 'inferred' || inv.pattern === 'gap_fill';
                        // Prefer inverter_summary string count over legacy strings_count
                        const summary = result.inverter_summary?.[inv.raw_name];
                        const strCount = summary?.string_count ?? inv.strings_count ?? 0;
                        const missingNos = missingByInv[inv.raw_name];
                        const hasMissing = missingNos && missingNos.length > 0;
                        const minNo = summary?.min_string_no;
                        const maxNo = summary?.max_string_no;
                        const rangeLabel = minNo != null && maxNo != null ? `#${minNo}–${maxNo}` : null;
                        return (
                          <div
                            key={inv.raw_name}
                            title={[
                              `${inv.raw_name} — ${strCount} strings`,
                              rangeLabel ? `range ${rangeLabel}` : '',
                              hasMissing ? `missing: ${missingNos!.join(', ')}` : '',
                              isInferred ? '(inferred)' : '',
                            ].filter(Boolean).join(' | ')}
                            className={`flex flex-col items-center justify-center rounded-lg border p-2 text-center relative ${
                              isInferred
                                ? 'border-dashed border-orange-300 bg-orange-50 text-orange-700'
                                : hasMissing
                                ? 'border-yellow-300 bg-yellow-50 text-yellow-800'
                                : strCount >= 22
                                ? 'border-indigo-200 bg-indigo-50 text-indigo-800'
                                : 'border-gray-200 bg-gray-50 text-gray-800'
                            }`}
                          >
                            <span className="font-mono font-bold text-xs">{inv.raw_name}</span>
                            <span className="text-xs mt-0.5 opacity-75">
                              {strCount > 0 ? `${strCount}s` : '—'}
                            </span>
                            {hasMissing && (
                              <span className="absolute -top-1.5 -right-1.5 bg-yellow-400 text-yellow-900 rounded-full w-4 h-4 text-[9px] flex items-center justify-center font-bold">
                                {missingNos!.length}
                              </span>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ));
              })()}

              {/* Per-inverter gap detail */}
              {result.missing_strings_by_inverter && Object.keys(result.missing_strings_by_inverter).length > 0 && (
                <div className="mt-4 rounded-lg bg-yellow-50 border border-yellow-200 p-3">
                  <p className="text-xs font-semibold text-yellow-800 mb-2">
                    Missing strings within declared range ({Object.keys(result.missing_strings_by_inverter).length} inverters affected)
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(result.missing_strings_by_inverter).map(([inv, nos]) => (
                      <span key={inv} className="font-mono text-xs bg-yellow-100 border border-yellow-300 text-yellow-900 rounded px-2 py-0.5">
                        {inv}: [{nos.join(', ')}]
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {result.validation_findings?.some(f => f.risk_code === 'INVERTER_COUNT_MISMATCH') && (
                <p className="mt-3 text-xs text-orange-600 bg-orange-50 border border-orange-200 rounded-lg px-3 py-2">
                  {result.validation_findings.find(f => f.risk_code === 'INVERTER_COUNT_MISMATCH')?.description}
                  {' '}Dashed inverters are inferred from gaps or document count.
                </p>
              )}
            </div>
          )}

          {/* Topology Findings */}
          {((result.topology_findings ?? []).length > 0 || (result.reconciliation?.issues ?? []).length > 0) && (
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <h3 className="font-semibold text-gray-800 mb-4 flex items-center gap-2">
                <Activity className="h-4 w-4 text-purple-600" />
                Topology Validation
                <span className="ml-auto text-xs text-gray-400">
                  {result.icb_zones?.length ? `${result.icb_zones.length} ICB zones` : ''}
                  {result.mppt_channels?.length ? ` · ${result.mppt_channels.length} MPPT groups` : ''}
                </span>
              </h3>

              <div className="space-y-2">
                {([
                  ...(result.topology_findings ?? []),
                  ...(result.reconciliation?.issues ?? []).map(i => ({
                    risk_code: i.code,
                    severity: i.severity,
                    title: i.code.replace(/_/g, ' '),
                    description: i.message,
                    related_assets: [] as string[],
                  })),
                ]).map((f, idx) => {
                  const colors: Record<string, string> = {
                    high: 'bg-red-50 border-red-200 text-red-700',
                    medium: 'bg-orange-50 border-orange-200 text-orange-700',
                    low: 'bg-yellow-50 border-yellow-200 text-yellow-700',
                  };
                  const cls = colors[f.severity] || 'bg-gray-50 border-gray-200 text-gray-700';
                  const assets = f.related_assets ?? [];
                  return (
                    <div key={idx} className={`rounded-lg border px-3 py-2 text-sm ${cls}`}>
                      <div className="font-semibold">{f.title}</div>
                      <div className="text-xs mt-0.5 opacity-90">{f.description}</div>
                      {assets.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-1">
                          {assets.map((a: string) => (
                            <span key={a} className="font-mono text-xs bg-white/60 px-1.5 py-0.5 rounded border">{a}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* Reconciliation summary */}
              {result.reconciliation && (
                <div className="mt-4 pt-4 border-t border-gray-100 grid grid-cols-2 md:grid-cols-4 gap-3 text-xs text-gray-600">
                  {result.reconciliation.table_inverter_count != null && (
                    <div><span className="text-gray-400">Table inverters</span><br/><strong>{result.reconciliation.table_inverter_count}</strong></div>
                  )}
                  {result.reconciliation.map_inverter_count != null && (
                    <div><span className="text-gray-400">Map inverters</span><br/><strong>{result.reconciliation.map_inverter_count}</strong></div>
                  )}
                  {result.reconciliation.map_string_total != null && (
                    <div><span className="text-gray-400">Detected strings</span><br/><strong>{result.reconciliation.map_string_total}</strong></div>
                  )}
                  {result.reconciliation.table_string_count != null && (
                    <div><span className="text-gray-400">Table strings</span><br/><strong>{result.reconciliation.table_string_count}</strong></div>
                  )}
                  {result.reconciliation.icb_zones_detected?.length ? (
                    <div className="col-span-2"><span className="text-gray-400">ICB Zones</span><br/>
                      <span className="font-mono">{result.reconciliation.icb_zones_detected.join(' · ')}</span>
                    </div>
                  ) : null}
                </div>
              )}
            </div>
          )}

          {/* Strings by section */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h3 className="font-semibold text-gray-800 mb-4 flex items-center gap-2">
              <Layers className="h-4 w-4 text-blue-600" />
              Strings by Section
            </h3>
            <div className="space-y-2">
              {Object.entries(result.strings).map(([section, codes]) => {
                const isOpen = expandedSections.has(section);
                const sectionGapKeys = Object.keys(result.gaps).filter(k => k.startsWith(section + '.'));
                return (
                  <div key={section} className="border border-gray-200 rounded-lg overflow-hidden">
                    <button
                      onClick={() => toggleSection(section)}
                      className="w-full flex items-center gap-3 px-4 py-2.5 bg-gray-50 hover:bg-gray-100 text-left transition-colors"
                    >
                      {isOpen ? <ChevronDown className="h-4 w-4 text-gray-400" /> : <ChevronRight className="h-4 w-4 text-gray-400" />}
                      <span className="font-mono font-semibold text-gray-800">{section}</span>
                      <span className="text-xs text-gray-500 ml-1">{codes.length} strings</span>
                      {sectionGapKeys.length > 0 && (
                        <span className="ml-auto text-xs bg-yellow-100 text-yellow-700 px-2 py-0.5 rounded-full font-medium">
                          {sectionGapKeys.length} gap{sectionGapKeys.length > 1 ? 's' : ''}
                        </span>
                      )}
                    </button>
                    {isOpen && (
                      <div className="px-4 py-3 flex flex-wrap gap-1.5">
                        {codes.map(code => {
                          const inGap = Object.values(result.gaps).flat().includes(code);
                          return (
                            <span
                              key={code}
                              className={`px-2 py-0.5 rounded text-xs font-mono border ${
                                inGap
                                  ? 'bg-yellow-50 text-yellow-700 border-yellow-200'
                                  : 'bg-blue-50 text-blue-700 border-blue-100'
                              }`}
                            >
                              {code}
                            </span>
                          );
                        })}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </>
      )}
    </div>
    </>
  );
}

/* ── Upload & Scan Modal ── */

interface UploadScanModalProps {
  onClose: () => void;
  onScan: (files: FileList) => void;
}

function formatBytes(b: number) {
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / (1024 * 1024)).toFixed(1)} MB`;
}

function UploadScanModal({ onClose, onScan }: UploadScanModalProps) {
  const [staged, setStaged] = useState<File[]>([]);
  const fileRef   = useRef<HTMLInputElement>(null);
  const folderRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', h);
    return () => document.removeEventListener('keydown', h);
  }, [onClose]);

  function add(files: File[]) {
    setStaged(prev => {
      const seen = new Set(prev.map(f => f.name + f.size));
      return [...prev, ...files.filter(f => !seen.has(f.name + f.size))];
    });
  }

  function remove(i: number) { setStaged(p => p.filter((_, idx) => idx !== i)); }

  function handleScan() {
    if (!staged.length) return;
    const dt = new DataTransfer();
    staged.forEach(f => dt.items.add(f));
    onScan(dt.files);
  }

  return (
    <div
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}
      style={{
        position: 'fixed', inset: 0, zIndex: 2100,
        background: 'rgba(0,0,0,0.45)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 24,
      }}
    >
      <div style={{
        background: '#fff', borderRadius: 12, width: '100%', maxWidth: 580,
        boxShadow: '0 20px 60px rgba(0,0,0,0.25)',
        display: 'flex', flexDirection: 'column', maxHeight: '88vh', overflow: 'hidden',
      }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 20px', borderBottom: '1px solid #e5e7eb' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Upload size={16} style={{ color: '#2563eb' }} />
            <span style={{ fontWeight: 700, fontSize: 15, color: '#111827' }}>Upload & Scan Design Files</span>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#9ca3af', padding: 4, borderRadius: 6, display: 'flex' }}
            onMouseEnter={e => (e.currentTarget.style.color = '#374151')}
            onMouseLeave={e => (e.currentTarget.style.color = '#9ca3af')}>
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div style={{ padding: 20, overflowY: 'auto', flex: 1 }}>
          <p style={{ fontSize: 13, color: '#6b7280', marginBottom: 14, lineHeight: 1.5 }}>
            Add <strong>PDF</strong> design files to scan for string identifiers, gaps, and anomalies.
            Stage multiple files or an entire folder — remove any you don't need before scanning.
          </p>

          {/* Buttons */}
          <div style={{ display: 'flex', gap: 8, marginBottom: 14, flexWrap: 'wrap', alignItems: 'center' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '7px 14px', background: '#f9fafb', border: '1px solid #e5e7eb', borderRadius: 8, fontSize: 13, color: '#374151', cursor: 'pointer', fontWeight: 500 }}>
              <FileText size={13} style={{ color: '#2563eb' }} /> Add Files
              <input ref={fileRef} type="file" accept=".pdf,.PDF" multiple style={{ display: 'none' }}
                onChange={e => { add(Array.from(e.target.files || [])); e.target.value = ''; }} />
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '7px 14px', background: '#f9fafb', border: '1px solid #e5e7eb', borderRadius: 8, fontSize: 13, color: '#374151', cursor: 'pointer', fontWeight: 500 }}>
              <FolderOpen size={13} style={{ color: '#f59e0b' }} /> Add Folder
              <input ref={folderRef} type="file"
                // @ts-ignore
                webkitdirectory="" multiple style={{ display: 'none' }}
                onChange={e => {
                  const pdfs = Array.from(e.target.files || []).filter(f => f.name.toLowerCase().endsWith('.pdf'));
                  add(pdfs);
                  e.target.value = '';
                }} />
            </label>
            {staged.length > 0 && (
              <>
                <button onClick={() => setStaged([])}
                  style={{ padding: '7px 12px', background: 'transparent', border: '1px solid #e5e7eb', borderRadius: 8, fontSize: 13, color: '#6b7280', cursor: 'pointer' }}>
                  Clear all
                </button>
                <span style={{ marginLeft: 'auto', fontSize: 13, color: '#2563eb', fontWeight: 600 }}>
                  {staged.length} file{staged.length > 1 ? 's' : ''} queued
                </span>
              </>
            )}
          </div>

          {/* Staged list */}
          {staged.length > 0 ? (
            <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, maxHeight: 240, overflowY: 'auto' }}>
              {staged.map((f, i) => (
                <div key={i} style={{
                  display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px',
                  borderBottom: i < staged.length - 1 ? '1px solid #f3f4f6' : undefined,
                  background: i % 2 === 0 ? '#fff' : '#fafafa',
                }}>
                  <FileText size={13} style={{ color: '#6b7280', flexShrink: 0 }} />
                  <span style={{ flex: 1, fontSize: 13, color: '#111827', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.name}</span>
                  <span style={{ fontSize: 12, color: '#9ca3af', flexShrink: 0 }}>{formatBytes(f.size)}</span>
                  <button onClick={() => remove(i)}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#d1d5db', padding: 2, display: 'flex', flexShrink: 0 }}
                    onMouseEnter={e => (e.currentTarget.style.color = '#ef4444')}
                    onMouseLeave={e => (e.currentTarget.style.color = '#d1d5db')}>
                    <Trash2 size={13} />
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ border: '2px dashed #e5e7eb', borderRadius: 10, padding: '28px 20px', textAlign: 'center', color: '#9ca3af', fontSize: 13 }}>
              <Upload size={24} style={{ margin: '0 auto 8px', display: 'block', color: '#d1d5db' }} />
              No files added yet — use the buttons above
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, padding: '14px 20px', borderTop: '1px solid #e5e7eb', background: '#f9fafb' }}>
          <button onClick={onClose}
            style={{ padding: '8px 18px', background: '#fff', border: '1px solid #d1d5db', borderRadius: 8, fontSize: 13, color: '#374151', fontWeight: 500, cursor: 'pointer' }}>
            Cancel
          </button>
          <button onClick={handleScan} disabled={staged.length === 0}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '8px 20px',
              background: staged.length === 0 ? '#93c5fd' : '#2563eb',
              color: '#fff', border: 'none', borderRadius: 8,
              fontSize: 13, fontWeight: 600,
              cursor: staged.length === 0 ? 'not-allowed' : 'pointer',
            }}>
            <Zap size={14} />
            Scan{staged.length > 0 ? ` (${staged.length})` : ''}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ── Busy overlay ── */

const SCAN_STEPS = [
  'Reading PDF content…',
  'Extracting text layers…',
  'Parsing string identifiers…',
  'Detecting gaps and duplicates…',
  'Analysing anomalies…',
  'Finalising results…',
];

function ScanBusyOverlay() {
  const [stepIdx, setStepIdx] = useState(0);

  useEffect(() => {
    const id = setInterval(() => {
      setStepIdx(i => (i + 1) % SCAN_STEPS.length);
    }, 2200);
    return () => clearInterval(id);
  }, []);

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 2000,
      background: 'rgba(15,23,42,0.65)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      backdropFilter: 'blur(3px)',
      cursor: 'wait',
    }}>
      <div style={{
        background: '#fff', borderRadius: 16,
        padding: '36px 44px',
        boxShadow: '0 24px 64px rgba(0,0,0,0.3)',
        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 20,
        minWidth: 320,
      }}>
        {/* Spinner */}
        <div style={{ position: 'relative', width: 56, height: 56 }}>
          <div style={{
            width: 56, height: 56,
            border: '4px solid #e0e7ff',
            borderTopColor: '#2563eb',
            borderRadius: '50%',
            animation: 'spin 0.9s linear infinite',
          }} />
          <FileSearch
            size={22}
            style={{ position: 'absolute', inset: 0, margin: 'auto', color: '#2563eb' }}
          />
        </div>

        <div style={{ textAlign: 'center' }}>
          <p style={{ fontWeight: 700, fontSize: 16, color: '#111827', marginBottom: 6 }}>
            Scanning Design PDF
          </p>
          <p style={{
            fontSize: 13, color: '#6b7280', minHeight: 20,
            transition: 'opacity 0.3s',
          }}>
            {SCAN_STEPS[stepIdx]}
          </p>
        </div>

        {/* Progress dots */}
        <div style={{ display: 'flex', gap: 6 }}>
          {SCAN_STEPS.map((_, i) => (
            <div key={i} style={{
              width: 7, height: 7, borderRadius: '50%',
              background: i === stepIdx ? '#2563eb' : '#e5e7eb',
              transition: 'background 0.3s',
            }} />
          ))}
        </div>

        <p style={{ fontSize: 11, color: '#9ca3af' }}>
          Large PDFs may take up to a minute — please wait
        </p>
      </div>
    </div>
  );
}

/* ── helpers ── */

function StatCard({ label, value, color, icon }: { label: string; value: number; color: string; icon: React.ReactNode }) {
  const colors: Record<string, string> = {
    blue:   'bg-blue-50 text-blue-700 border-blue-100',
    green:  'bg-green-50 text-green-700 border-green-100',
    red:    'bg-red-50 text-red-700 border-red-100',
    yellow: 'bg-yellow-50 text-yellow-700 border-yellow-100',
    gray:   'bg-gray-50 text-gray-500 border-gray-100',
  };
  return (
    <div className={`rounded-xl border p-4 ${colors[color] ?? colors.gray}`}>
      <div className="flex items-center gap-2 mb-1 opacity-70">{icon}<span className="text-xs font-medium">{label}</span></div>
      <p className="text-2xl font-bold">{value}</p>
    </div>
  );
}

function Section({
  title, color, icon, children,
}: { title: string; color: string; icon: React.ReactNode; children: React.ReactNode }) {
  const colors: Record<string, string> = {
    yellow: 'bg-yellow-50 border-yellow-200 text-yellow-800',
    red:    'bg-red-50 border-red-200 text-red-800',
    orange: 'bg-orange-50 border-orange-200 text-orange-800',
  };
  return (
    <div className={`rounded-xl border p-4 ${colors[color] ?? ''}`}>
      <h4 className="font-semibold text-sm flex items-center gap-2 mb-3">{icon}{title}</h4>
      {children}
    </div>
  );
}
