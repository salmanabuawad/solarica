import { useState, useRef, useEffect } from 'react';
import {
  Check, ChevronLeft, ChevronRight, Loader2, X,
  FileText, FolderOpen, Trash2, Upload,
  CheckCircle2, AlertTriangle, XCircle, Zap, ArrowRight,
  Building2, Users, Plus,
} from 'lucide-react';
import * as api from '../../lib/api';
import type {
  ApprovedStringPattern,
  Company,
  Customer,
  StringPatternDetectionResult,
  StringScanResult,
} from '../../lib/api';
import type { ProjectCreate } from '../../lib/types';
import StringPatternBusyModal from './StringPatternBusyModal';
import StringPatternConfirmModal from './StringPatternConfirmModal';
import StructuredParseReportPanel from './StructuredParseReportPanel';
import { extractStructuredParseReport } from '../../lib/parseReportUtils';

interface ProjectWizardProps {
  onClose: () => void;
  /** Fired after successful create; includes name for tab label. */
  onCreated?: (info: { id: number; name: string }) => void;
}

/* ─── Steps ─────────────────────────────────────────────────── */
const STEPS = ['Company', 'Customer', 'Design Files', 'Parse & Validate', 'Details', 'Create'];

/* ─── Form ──────────────────────────────────────────────────── */
interface FormData {
  name: string; project_type: string; site_name: string;
  capacity_kw: string; description: string;
  naming_prefix: string; inverter_count: string; strings_per_inverter: string;
}
const INIT: FormData = {
  name: '', project_type: 'utility', site_name: '',
  capacity_kw: '', description: '', naming_prefix: '', inverter_count: '', strings_per_inverter: '',
};
const PROJECT_TYPES = ['residential', 'commercial', 'industrial', 'utility', 'agrivoltaic', 'mini-grid'];

/* ─── Shared styles ─────────────────────────────────────────── */
const inp: React.CSSProperties = {
  width: '100%', padding: '9px 12px', fontSize: 14, color: '#111827',
  background: '#fff', border: '1px solid #d1d5db', borderRadius: 8,
  outline: 'none', boxSizing: 'border-box',
};
const inpFocus: React.CSSProperties = { borderColor: '#2563eb', boxShadow: '0 0 0 3px rgba(37,99,235,0.12)' };
const lbl: React.CSSProperties = { display: 'block', fontSize: 13, fontWeight: 500, color: '#374151', marginBottom: 5 };

function Field({ as: Tag = 'input', style, ...props }: { as?: 'input' | 'select' | 'textarea' } & React.InputHTMLAttributes<HTMLInputElement> & React.SelectHTMLAttributes<HTMLSelectElement> & React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  const [focused, setFocused] = useState(false);
  const merged = { ...inp, ...(focused ? inpFocus : {}), ...style };
  if (Tag === 'select') return <select {...(props as any)} style={merged} onFocus={() => setFocused(true)} onBlur={() => setFocused(false)} />;
  if (Tag === 'textarea') return <textarea {...(props as any)} style={{ ...merged, resize: 'none' }} onFocus={() => setFocused(true)} onBlur={() => setFocused(false)} />;
  return <input {...(props as any)} style={merged} onFocus={() => setFocused(true)} onBlur={() => setFocused(false)} />;
}

function fmt(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1048576).toFixed(1)} MB`;
}

/* ─── Main ──────────────────────────────────────────────────── */
export default function ProjectWizard({ onClose, onCreated }: ProjectWizardProps) {
  const [step, setStep]   = useState(0);
  const [error, setError] = useState<string | null>(null);

  // Step 0 — Company
  const [companies, setCompanies]         = useState<Company[]>([]);
  const [selectedCompany, setSelectedCompany] = useState<Company | null>(null);
  const [newCompanyName, setNewCompanyName]   = useState('');
  const [creatingCompany, setCreatingCompany] = useState(false);
  const [showNewCompany, setShowNewCompany]   = useState(false);

  // Step 1 — Customer
  const [customers, setCustomers]             = useState<Customer[]>([]);
  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null);
  const [newCustomerName, setNewCustomerName]   = useState('');
  const [creatingCustomer, setCreatingCustomer] = useState(false);
  const [showNewCustomer, setShowNewCustomer]   = useState(false);

  // Step 2 — files
  const [stagedFiles, setStagedFiles] = useState<File[]>([]);
  const fileRef   = useRef<HTMLInputElement>(null);
  const folderRef = useRef<HTMLInputElement>(null);

  // Step 3 — parse
  const [parsing, setParsing]         = useState(false);
  const [parseResult, setParseResult] = useState<StringScanResult | null>(null);
  const [parseError, setParseError]   = useState<string | null>(null);
  const [approvedPattern, setApprovedPattern] = useState<ApprovedStringPattern | null>(null);
  const [patternDetection, setPatternDetection] = useState<StringPatternDetectionResult | null>(null);
  const [patternModalOpen, setPatternModalOpen] = useState(false);
  const [patternBusy, setPatternBusy] = useState(false);
  const [patternBusyFileCount, setPatternBusyFileCount] = useState(0);
  const pendingParseFilesRef = useRef<File[]>([]);

  // Step 4 — details form
  const [form, setForm] = useState<FormData>(INIT);
  const upd = (f: keyof FormData, v: string) => setForm(p => ({ ...p, [f]: v }));

  // Step 5 — create
  const [creating, setCreating] = useState(false);

  /* load companies on mount */
  useEffect(() => {
    api.listCompanies().then(setCompanies).catch(() => {});
  }, []);

  /* load customers when company selected */
  useEffect(() => {
    if (!selectedCompany) { setCustomers([]); return; }
    api.listCustomers(selectedCompany.id).then(setCustomers).catch(() => {});
  }, [selectedCompany]);

  /* auto-parse when entering step 3 */
  useEffect(() => {
    if (step !== 3) return;
    const pdfs = stagedFiles.filter(f => f.name.toLowerCase().endsWith('.pdf'));
    if (!pdfs.length) return;
    startPatternApproval(pdfs);
  }, [step]); // eslint-disable-line

  const pdfs = stagedFiles.filter(f => f.name.toLowerCase().endsWith('.pdf'));

  async function handleCreateCompany() {
    if (!newCompanyName.trim()) return;
    setCreatingCompany(true);
    try {
      const c = await api.createCompany({ name: newCompanyName.trim() });
      setCompanies(p => [...p, c]);
      setSelectedCompany(c);
      setShowNewCompany(false);
      setNewCompanyName('');
    } catch { setError('Failed to create company.'); }
    finally { setCreatingCompany(false); }
  }

  async function handleCreateCustomer() {
    if (!newCustomerName.trim() || !selectedCompany) return;
    setCreatingCustomer(true);
    try {
      const c = await api.createCustomer({ company_id: selectedCompany.id, name: newCustomerName.trim() });
      setCustomers(p => [...p, c]);
      setSelectedCustomer(c);
      setShowNewCustomer(false);
      setNewCustomerName('');
    } catch { setError('Failed to create customer.'); }
    finally { setCreatingCustomer(false); }
  }

  function addFiles(files: File[]) {
    setApprovedPattern(null);
    setParseResult(null);
    setParseError(null);
    setStagedFiles(prev => {
      const seen = new Set(prev.map(f => f.name + f.size));
      return [...prev, ...files.filter(f => !seen.has(f.name + f.size))];
    });
  }

  async function startPatternApproval(pdfFiles: File[]) {
    pendingParseFilesRef.current = pdfFiles;
    setPatternBusyFileCount(pdfFiles.length);
    setPatternBusy(true);
    setParseError(null);
    setParseResult(null);
    try {
      const dt = new DataTransfer();
      pdfFiles.forEach(f => dt.items.add(f));
      // Start background detect job — returns immediately
      const { job_id } = await api.detectStringPatternStart(0, dt.files);

      // Poll every 2 s until done or error
      await new Promise<void>((resolve, reject) => {
        const poll = async () => {
          try {
            const status = await api.detectStringPatternStatus(0, job_id);
            if (status.state === 'error') {
              reject(new Error(status.error ?? 'Pattern detection failed.'));
            } else if (status.state === 'done') {
              if (status.scan_summary) {
                setPatternDetection(status.scan_summary);
                setPatternModalOpen(true);
              }
              resolve();
            } else {
              window.setTimeout(poll, 2_000);
            }
          } catch (e) {
            reject(e);
          }
        };
        window.setTimeout(poll, 1_000);
      });
    } catch (e: any) {
      setParseError(e?.response?.data?.detail || e?.message || 'Could not detect a string pattern.');
    } finally {
      setPatternBusy(false);
    }
  }

  async function runParse(pdfFiles: File[], pattern: ApprovedStringPattern, detectToken?: string | null) {
    setParsing(true); setParseError(null); setParseResult(null);
    try {
      const dt = new DataTransfer();
      pdfFiles.forEach(f => dt.items.add(f));

      // Start background scan job (project_id=0 → skip DB sync, return full result)
      const { job_id } = await api.scanProjectStart(0, undefined, dt.files, pattern, detectToken ?? null);

      // Poll every 2 s until done or error
      await new Promise<void>((resolve, reject) => {
        const poll = async () => {
          try {
            const status = await api.scanProjectStatus(0, job_id);
            if (status.state === 'error') {
              reject(new Error(status.error ?? 'Parse failed.'));
            } else if (status.state === 'done') {
              const res = status.scan_summary as api.StringScanResult;
              setApprovedPattern(pattern);
              setParseResult(res);
              const pr = extractStructuredParseReport(res as unknown);
              const siteLabel = pr?.site?.name ?? res.site_name ?? res.site_code ?? '';
              const invTotal = pr?.inverters?.total ?? res.inverter_count_detected;
              setForm(prev => ({
                ...prev,
                name: prev.name || siteLabel,
                site_name: prev.site_name || siteLabel,
                capacity_kw: prev.capacity_kw || (res.plant_capacity_mw != null ? String(res.plant_capacity_mw * 1000) : ''),
                naming_prefix: prev.naming_prefix || res.site_code || '',
                inverter_count: prev.inverter_count || (invTotal != null && invTotal > 0 ? String(invTotal) : ''),
              }));
              resolve();
            } else {
              window.setTimeout(poll, 2_000);
            }
          } catch (e) {
            reject(e);
          }
        };
        window.setTimeout(poll, 1_000);
      });
    } catch (e: any) {
      setParseError(e?.response?.data?.detail || e?.message || 'Parse failed.');
    } finally { setParsing(false); }
  }

  function validateForm() {
    if (!form.name.trim()) return 'Project name is required';
    return null;
  }

  async function handleCreate() {
    const err = validateForm();
    if (err) { setError(err); return; }
    setCreating(true); setError(null);
    try {
      const payload: ProjectCreate = {
        name: form.name.trim(),
        customer_id: selectedCustomer?.id ?? null,
        customer_name: selectedCustomer?.name ?? null,
        site_name: form.site_name.trim() || form.name.trim(),
        project_type: form.project_type,
        description: form.description.trim() || null,
      };
      const project = await api.createProject(payload);
      if (approvedPattern?.pattern_name) {
        try {
          await api.updateStringPattern(project.id, approvedPattern.pattern_name);
        } catch {}
      }
      if (stagedFiles.length > 0) {
        try { await api.uploadProjectFiles(project.id, stagedFiles); } catch {}
      }
      onCreated?.({ id: project.id, name: project.name });
      onClose();
    } catch { setError('Failed to create project. Please try again.'); }
    finally { setCreating(false); }
  }

  function goNext() {
    setError(null);
    if (step === 0 && !selectedCompany) { setError('Select or create a company.'); return; }
    if (step === 1 && !selectedCustomer) { setError('Select or create a customer.'); return; }
    if (step === 2 && !pdfs.length) { setStep(4); return; } // skip parse
    setStep(s => s + 1);
  }
  function goBack() {
    setError(null);
    if (step === 4 && !pdfs.length) { setStep(2); return; }
    setStep(s => s - 1);
  }

  /* ── Card selector ── */
  function SelectCard({ label, selected, onClick }: { label: string; selected: boolean; onClick: () => void }) {
    return (
      <button onClick={onClick} style={{
        display: 'flex', alignItems: 'center', gap: 8,
        padding: '10px 14px', borderRadius: 8, border: `2px solid ${selected ? '#2563eb' : '#e5e7eb'}`,
        background: selected ? '#eff6ff' : '#fafafa', cursor: 'pointer', textAlign: 'left',
        fontSize: 13, fontWeight: selected ? 600 : 400, color: selected ? '#1d4ed8' : '#374151',
        transition: 'border-color 0.15s, background 0.15s',
      }}>
        {selected && <Check size={13} style={{ flexShrink: 0, color: '#2563eb' }} />}
        {label}
      </button>
    );
  }

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 9500, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.55)', backdropFilter: 'blur(3px)', padding: 16 }}>
      <StringPatternBusyModal
        open={patternBusy && !patternModalOpen && !parsing}
        projectName={form.name.trim() || 'new project'}
        fileCount={patternBusyFileCount}
      />
      <StringPatternConfirmModal
        open={patternModalOpen}
        detection={patternDetection}
        busy={patternBusy}
        onCancel={() => {
          setPatternModalOpen(false);
          setPatternDetection(null);
        }}
        onConfirm={async (pattern) => {
          setPatternBusy(true);
          try {
            const detectToken = patternDetection?.detect_token;
            setPatternModalOpen(false);
            setPatternDetection(null);
            await runParse(pendingParseFilesRef.current, pattern, detectToken);
          } finally {
            setPatternBusy(false);
          }
        }}
      />
      <div style={{ background: '#fff', borderRadius: 16, width: '100%', maxWidth: 620, boxShadow: '0 20px 60px rgba(0,0,0,0.2)', display: 'flex', flexDirection: 'column', maxHeight: '92vh', overflow: 'hidden' }}>

        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '18px 24px 16px', borderBottom: '1px solid #e5e7eb' }}>
          <div>
            <h2 style={{ fontSize: 17, fontWeight: 700, color: '#111827', margin: 0 }}>New Project</h2>
            {selectedCompany && (
              <p style={{ fontSize: 12, color: '#6b7280', margin: '2px 0 0' }}>
                {selectedCompany.name}{selectedCustomer ? ` → ${selectedCustomer.name}` : ''}
              </p>
            )}
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 4, color: '#9ca3af', display: 'flex', borderRadius: 6 }}>
            <X size={18} />
          </button>
        </div>

        {/* Stepper */}
        <div style={{ padding: '14px 24px 0', overflowX: 'auto' }}>
          <div style={{ display: 'flex', alignItems: 'center', minWidth: 500 }}>
            {STEPS.map((label, i) => (
              <div key={label} style={{ display: 'flex', alignItems: 'center', flex: 1 }}>
                <div style={{ width: 24, height: 24, borderRadius: '50%', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, fontWeight: 700, background: i < step ? '#16a34a' : i === step ? '#2563eb' : '#e5e7eb', color: i <= step ? '#fff' : '#6b7280' }}>
                  {i < step ? <Check size={11} /> : i + 1}
                </div>
                <span style={{ fontSize: 10, marginLeft: 4, whiteSpace: 'nowrap', color: i === step ? '#2563eb' : i < step ? '#16a34a' : '#9ca3af', fontWeight: i === step ? 600 : 400 }}>{label}</span>
                {i < STEPS.length - 1 && <div style={{ flex: 1, height: 2, margin: '0 5px', background: i < step ? '#16a34a' : '#e5e7eb', borderRadius: 1 }} />}
              </div>
            ))}
          </div>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '18px 24px' }}>
          {error && <div style={{ padding: '10px 14px', borderRadius: 8, background: '#fef2f2', border: '1px solid #fecaca', color: '#dc2626', fontSize: 13, marginBottom: 14 }}>{error}</div>}

          {/* ── Step 0: Company ── */}
          {step === 0 && (
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
                <Building2 size={16} style={{ color: '#2563eb' }} />
                <span style={{ fontWeight: 600, fontSize: 14, color: '#111827' }}>Select a Company</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 14, maxHeight: 200, overflowY: 'auto' }}>
                {companies.map(c => (
                  <SelectCard key={c.id} label={`${c.name}${c.country ? ` · ${c.country}` : ''}`} selected={selectedCompany?.id === c.id} onClick={() => { setSelectedCompany(c); setSelectedCustomer(null); }} />
                ))}
                {companies.length === 0 && <p style={{ fontSize: 13, color: '#9ca3af', padding: '8px 0' }}>No companies yet — create one below.</p>}
              </div>

              {!showNewCompany ? (
                <button onClick={() => setShowNewCompany(true)} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 14px', background: '#f9fafb', border: '1px dashed #d1d5db', borderRadius: 8, fontSize: 13, color: '#6b7280', cursor: 'pointer' }}>
                  <Plus size={13} /> New Company
                </button>
              ) : (
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <input autoFocus value={newCompanyName} onChange={e => setNewCompanyName(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && handleCreateCompany()}
                    placeholder="Company name…" style={{ ...inp, flex: 1 }} />
                  <button onClick={handleCreateCompany} disabled={creatingCompany || !newCompanyName.trim()}
                    style={{ padding: '9px 14px', background: '#2563eb', color: '#fff', border: 'none', borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: 'pointer', whiteSpace: 'nowrap' }}>
                    {creatingCompany ? <Loader2 size={14} className="animate-spin" /> : 'Add'}
                  </button>
                  <button onClick={() => setShowNewCompany(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#9ca3af', padding: 4 }}><X size={16} /></button>
                </div>
              )}
            </div>
          )}

          {/* ── Step 1: Customer ── */}
          {step === 1 && (
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <Users size={16} style={{ color: '#2563eb' }} />
                <span style={{ fontWeight: 600, fontSize: 14, color: '#111827' }}>Select a Customer</span>
              </div>
              <p style={{ fontSize: 12, color: '#6b7280', marginBottom: 14 }}>Under: <strong>{selectedCompany?.name}</strong></p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 14, maxHeight: 200, overflowY: 'auto' }}>
                {customers.map(c => (
                  <SelectCard key={c.id} label={`${c.name}${c.project_count ? ` · ${c.project_count} project(s)` : ''}`} selected={selectedCustomer?.id === c.id} onClick={() => setSelectedCustomer(c)} />
                ))}
                {customers.length === 0 && <p style={{ fontSize: 13, color: '#9ca3af', padding: '8px 0' }}>No customers yet — create one below.</p>}
              </div>

              {!showNewCustomer ? (
                <button onClick={() => setShowNewCustomer(true)} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 14px', background: '#f9fafb', border: '1px dashed #d1d5db', borderRadius: 8, fontSize: 13, color: '#6b7280', cursor: 'pointer' }}>
                  <Plus size={13} /> New Customer
                </button>
              ) : (
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <input autoFocus value={newCustomerName} onChange={e => setNewCustomerName(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && handleCreateCustomer()}
                    placeholder="Customer name…" style={{ ...inp, flex: 1 }} />
                  <button onClick={handleCreateCustomer} disabled={creatingCustomer || !newCustomerName.trim()}
                    style={{ padding: '9px 14px', background: '#2563eb', color: '#fff', border: 'none', borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: 'pointer', whiteSpace: 'nowrap' }}>
                    {creatingCustomer ? <Loader2 size={14} className="animate-spin" /> : 'Add'}
                  </button>
                  <button onClick={() => setShowNewCustomer(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#9ca3af', padding: 4 }}><X size={16} /></button>
                </div>
              )}
            </div>
          )}

          {/* ── Step 2: Design Files ── */}
          {step === 2 && (
            <div>
              <p style={{ fontSize: 13, color: '#6b7280', marginBottom: 14, lineHeight: 1.6 }}>
                Upload <strong>PDF</strong> or <strong>DXF</strong> design files. The parser will extract site details, detect strings, inverters, and AC assets automatically. Skip to enter details manually.
              </p>
              <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap', alignItems: 'center' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '7px 14px', background: '#f9fafb', border: '1px solid #e5e7eb', borderRadius: 8, fontSize: 13, color: '#374151', cursor: 'pointer', fontWeight: 500 }}>
                  <FileText size={13} style={{ color: '#2563eb' }} /> Add Files
                  <input ref={fileRef} type="file" accept=".pdf,.PDF,.dxf,.DXF" multiple style={{ display: 'none' }}
                    onChange={e => { addFiles(Array.from(e.target.files || [])); e.target.value = ''; }} />
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '7px 14px', background: '#f9fafb', border: '1px solid #e5e7eb', borderRadius: 8, fontSize: 13, color: '#374151', cursor: 'pointer', fontWeight: 500 }}>
                  <FolderOpen size={13} style={{ color: '#f59e0b' }} /> Add Folder
                  <input ref={folderRef} type="file" // @ts-ignore
                    webkitdirectory="" multiple style={{ display: 'none' }}
                    onChange={e => {
                      addFiles(Array.from(e.target.files || []).filter(f => /\.(pdf|dxf)$/i.test(f.name)));
                      e.target.value = '';
                    }} />
                </label>
                {stagedFiles.length > 0 && (
                  <span style={{ marginLeft: 'auto', fontSize: 13, color: '#2563eb', fontWeight: 600 }}>
                    {stagedFiles.length} file{stagedFiles.length > 1 ? 's' : ''}
                    {pdfs.length > 0 && <span style={{ color: '#16a34a', marginLeft: 6 }}>· {pdfs.length} PDF{pdfs.length > 1 ? 's' : ''} will be parsed</span>}
                  </span>
                )}
              </div>
              {stagedFiles.length > 0 ? (
                <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, maxHeight: 200, overflowY: 'auto' }}>
                  {stagedFiles.map((f, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '7px 12px', borderBottom: i < stagedFiles.length - 1 ? '1px solid #f3f4f6' : undefined, background: i % 2 === 0 ? '#fff' : '#fafafa' }}>
                      <FileText size={13} style={{ color: /\.pdf$/i.test(f.name) ? '#2563eb' : '#6b7280', flexShrink: 0 }} />
                      <span style={{ flex: 1, fontSize: 13, color: '#111827', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.name}</span>
                      <span style={{ fontSize: 11, color: '#9ca3af', flexShrink: 0 }}>{fmt(f.size)}</span>
                      <button onClick={() => {
                        setApprovedPattern(null);
                        setParseResult(null);
                        setParseError(null);
                        setStagedFiles(p => p.filter((_, idx) => idx !== i));
                      }}
                        style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#d1d5db', padding: 2, display: 'flex' }}
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
                  No files — add above or click <strong>Skip</strong>
                </div>
              )}
            </div>
          )}

          {/* ── Step 3: Parse ── */}
          {step === 3 && (
            <div>
              {parsing && (
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '28px 0', gap: 14 }}>
                  <div style={{ position: 'relative', width: 48, height: 48 }}>
                    <div style={{ width: 48, height: 48, border: '4px solid #e0e7ff', borderTopColor: '#2563eb', borderRadius: '50%', animation: 'spin 0.9s linear infinite' }} />
                    <Zap size={18} style={{ position: 'absolute', inset: 0, margin: 'auto', color: '#2563eb' }} />
                  </div>
                  <p style={{ fontSize: 14, fontWeight: 600, color: '#111827' }}>Parsing design files…</p>
                  <p style={{ fontSize: 13, color: '#6b7280' }}>Extracting site details, strings, inverters</p>
                </div>
              )}
              {parseError && !parsing && (
                <div style={{ padding: '12px 14px', background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 8, color: '#dc2626', fontSize: 13, marginBottom: 14 }}>
                  Parse failed: {parseError} — you can still continue manually.
                </div>
              )}
              {parseResult && !parsing && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                  {extractStructuredParseReport(parseResult as unknown) && (
                    <StructuredParseReportPanel report={extractStructuredParseReport(parseResult as unknown)!} />
                  )}
                  {approvedPattern && (
                    <div style={{ padding: '8px 12px', background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: 8, fontSize: 12, color: '#1d4ed8' }}>
                      Approved string pattern: <strong>{approvedPattern.pattern_name}</strong>
                    </div>
                  )}
                  <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: 10, padding: '12px 16px' }}>
                    <p style={{ fontWeight: 600, fontSize: 13, color: '#15803d', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
                      <CheckCircle2 size={14} /> Extracted from design
                    </p>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, fontSize: 12 }}>
                      {(() => {
                        const pr = extractStructuredParseReport(parseResult as unknown);
                        const vStr = pr?.strings?.valid_total ?? parseResult.valid_count;
                        const invN = pr?.inverters?.total ?? parseResult.inverter_count_detected;
                        return [
                          ['Strings', vStr],
                          ['Inverters', invN || '—'],
                          ['AC Assets', parseResult.ac_assets?.length || '—'],
                          ['Capacity', parseResult.plant_capacity_mw != null ? `${parseResult.plant_capacity_mw} MW` : '—'],
                          ['Module Pwr', parseResult.module_power_wp != null ? `${parseResult.module_power_wp} Wp` : '—'],
                          ['Modules/Str', parseResult.modules_per_string ?? '—'],
                          ['Tracker', parseResult.tracker_enabled ? 'Yes' : 'No'],
                          ['BESS', parseResult.batteries?.length ? `${parseResult.batteries.length}` : '—'],
                          ['Gaps', Object.keys(parseResult.gaps ?? {}).length || '—'],
                        ] as [string, string | number][];
                      })().map(([k, v]) => (
                        <div key={k as string}>
                          <p style={{ fontSize: 10, color: '#6b7280' }}>{k}</p>
                          <p style={{ fontSize: 13, fontWeight: 600, color: '#111827' }}>{v}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                  {parseResult.validation_findings?.length > 0 && (
                    <div style={{ background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 10, padding: '12px 16px' }}>
                      <p style={{ fontWeight: 600, fontSize: 13, color: '#d97706', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                        <AlertTriangle size={14} /> {parseResult.validation_findings.length} validation finding(s)
                      </p>
                      {parseResult.validation_findings.map((f, i) => (
                        <p key={i} style={{ fontSize: 12, color: '#92400e', marginBottom: 4 }}>• {f.title}: {f.description}</p>
                      ))}
                    </div>
                  )}
                  {(parseResult.has_errors ||
                    (extractStructuredParseReport(parseResult as unknown)?.strings?.invalid_total ?? 0) > 0) && (
                    <div style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 10, padding: '10px 14px', fontSize: 12, color: '#dc2626', display: 'flex', alignItems: 'center', gap: 6 }}>
                      <XCircle size={13} />{' '}
                      {extractStructuredParseReport(parseResult as unknown)?.strings?.invalid_total ??
                        parseResult.invalid_count}{' '}
                      invalid string(s) — review in Strings tab after creation.
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* ── Step 4: Details ── */}
          {step === 4 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {parseResult && <div style={{ padding: '7px 12px', background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: 8, fontSize: 12, color: '#1d4ed8' }}>Fields pre-filled from design — edit as needed.</div>}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div style={{ gridColumn: '1 / -1' }}>
                  <label style={lbl}>Project Name <span style={{ color: '#ef4444' }}>*</span></label>
                  <Field type="text" value={form.name} onChange={e => upd('name', e.target.value)} placeholder="e.g. Solar Farm Alpha" autoFocus />
                </div>
                <div>
                  <label style={lbl}>Project Type</label>
                  <Field as="select" value={form.project_type} onChange={e => upd('project_type', e.target.value)}>
                    {PROJECT_TYPES.map(t => <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>)}
                  </Field>
                </div>
                <div>
                  <label style={lbl}>Site Name</label>
                  <Field type="text" value={form.site_name} onChange={e => upd('site_name', e.target.value)} placeholder="e.g. Hamadia North" />
                </div>
                <div>
                  <label style={lbl}>Capacity (kW)</label>
                  <Field type="number" value={form.capacity_kw} onChange={e => upd('capacity_kw', e.target.value)} placeholder="e.g. 5000" />
                </div>
                <div>
                  <label style={lbl}>Naming Prefix</label>
                  <Field type="text" value={form.naming_prefix} onChange={e => upd('naming_prefix', e.target.value)} placeholder="e.g. SFA" />
                </div>
                <div>
                  <label style={lbl}>
                    Inverters (detected:{' '}
                    {parseResult
                      ? extractStructuredParseReport(parseResult as unknown)?.inverters?.total ??
                        parseResult.inverter_count_detected ??
                        '—'
                      : '—'}
                    )
                  </label>
                  <Field type="number" value={form.inverter_count} onChange={e => upd('inverter_count', e.target.value)} placeholder="Count" />
                </div>
                <div>
                  <label style={lbl}>Strings/Inverter (modules/str: {parseResult?.modules_per_string ?? '—'})</label>
                  <Field type="number" value={form.strings_per_inverter} onChange={e => upd('strings_per_inverter', e.target.value)} placeholder="Count" />
                </div>
                <div style={{ gridColumn: '1 / -1' }}>
                  <label style={lbl}>Description</label>
                  <Field as="textarea" value={form.description} onChange={e => upd('description', e.target.value)} rows={2} placeholder="Optional…" />
                </div>
              </div>
            </div>
          )}

          {/* ── Step 5: Create ── */}
          {step === 5 && (
            <div>
              <p style={{ fontSize: 14, fontWeight: 600, color: '#111827', marginBottom: 12 }}>Ready to create</p>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 12 }}>
                {[
                  ['Company', selectedCompany?.name],
                  ['Customer', selectedCustomer?.name],
                  ['Project', form.name],
                  ['Site', form.site_name || '—'],
                  ['Type', form.project_type],
                  ...(form.capacity_kw ? [['Capacity', `${form.capacity_kw} kW`]] : []),
                ].map(([k, v]) => (
                  <div key={k} style={{ background: '#f9fafb', border: '1px solid #e5e7eb', borderRadius: 8, padding: '8px 12px' }}>
                    <p style={{ fontSize: 11, color: '#6b7280', marginBottom: 2 }}>{k}</p>
                    <p style={{ fontSize: 13, fontWeight: 500, color: '#111827' }}>{v || '—'}</p>
                  </div>
                ))}
              </div>
              {stagedFiles.length > 0 && (
                <div style={{ padding: '8px 12px', background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: 8, fontSize: 13, color: '#1d4ed8', marginBottom: 8 }}>
                  {stagedFiles.length} design file{stagedFiles.length > 1 ? 's' : ''} will be uploaded automatically.
                </div>
              )}
              {parseResult && (
                <div style={{ padding: '8px 12px', background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: 8, fontSize: 13, color: '#15803d' }}>
                  <strong>
                    {extractStructuredParseReport(parseResult as unknown)?.strings?.valid_total ??
                      parseResult.valid_count}
                  </strong>{' '}
                  valid strings ·{' '}
                  <strong>
                    {extractStructuredParseReport(parseResult as unknown)?.inverters?.total ??
                      parseResult.inverter_count_detected}
                  </strong>{' '}
                  inverters detected
                  {approvedPattern && <span> · pattern <strong>{approvedPattern.pattern_name}</strong></span>}
                  {parseResult.validation_findings?.length > 0 && <span style={{ color: '#d97706' }}> · {parseResult.validation_findings.length} finding(s) to review</span>}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 24px', borderTop: '1px solid #e5e7eb', background: '#f9fafb' }}>
          {step === 0 ? (
            <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 14, color: '#6b7280', padding: '8px 4px', display: 'flex', alignItems: 'center', gap: 4 }}>
              <ChevronLeft size={16} /> Cancel
            </button>
          ) : (
            <button onClick={goBack} disabled={step === 3 && (parsing || patternBusy)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 14, color: '#6b7280', padding: '8px 4px', display: 'flex', alignItems: 'center', gap: 4, opacity: step === 3 && (parsing || patternBusy) ? 0.6 : 1 }}>
              <ChevronLeft size={16} /> Back
            </button>
          )}

          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            {step === 2 && stagedFiles.length === 0 && (
              <button onClick={() => setStep(4)} style={{ fontSize: 13, color: '#6b7280', background: 'none', border: 'none', cursor: 'pointer', padding: '8px 4px' }}>Skip</button>
            )}
            {(step === 0 || step === 1) && (
              <button onClick={goNext} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '9px 20px', background: '#2563eb', color: '#fff', border: 'none', borderRadius: 8, fontSize: 14, fontWeight: 600, cursor: 'pointer' }}>
                Next <ChevronRight size={16} />
              </button>
            )}
            {step === 2 && stagedFiles.length > 0 && (
              <button onClick={goNext} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '9px 20px', background: '#2563eb', color: '#fff', border: 'none', borderRadius: 8, fontSize: 14, fontWeight: 600, cursor: 'pointer' }}>
                {pdfs.length > 0 ? <><Zap size={14} /> Parse & Continue</> : <>Next <ChevronRight size={16} /></>}
              </button>
            )}
            {step === 3 && !parsing && !patternBusy && (
              <button onClick={() => setStep(4)} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '9px 20px', background: '#2563eb', color: '#fff', border: 'none', borderRadius: 8, fontSize: 14, fontWeight: 600, cursor: 'pointer' }}>
                Continue <ChevronRight size={16} />
              </button>
            )}
            {step === 3 && patternBusy && !parsing && (
              <button disabled style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '9px 20px', background: '#93c5fd', color: '#fff', border: 'none', borderRadius: 8, fontSize: 14, fontWeight: 600, cursor: 'not-allowed' }}>
                <Loader2 size={14} className="animate-spin" /> Detecting pattern…
              </button>
            )}
            {step === 3 && parsing && (
              <button disabled style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '9px 20px', background: '#93c5fd', color: '#fff', border: 'none', borderRadius: 8, fontSize: 14, fontWeight: 600, cursor: 'not-allowed' }}>
                <Loader2 size={14} className="animate-spin" /> Parsing…
              </button>
            )}
            {step === 4 && (
              <button onClick={() => { const e = validateForm(); if (e) { setError(e); return; } setError(null); setStep(5); }} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '9px 20px', background: '#2563eb', color: '#fff', border: 'none', borderRadius: 8, fontSize: 14, fontWeight: 600, cursor: 'pointer' }}>
                Review <ChevronRight size={16} />
              </button>
            )}
            {step === 5 && (
              <button onClick={handleCreate} disabled={creating} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '9px 22px', background: creating ? '#6b7280' : '#16a34a', color: '#fff', border: 'none', borderRadius: 8, fontSize: 14, fontWeight: 600, cursor: creating ? 'not-allowed' : 'pointer', opacity: creating ? 0.7 : 1 }}>
                {creating ? <><Loader2 size={14} className="animate-spin" /> Creating…</> : <><ArrowRight size={14} /> Create Project</>}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
