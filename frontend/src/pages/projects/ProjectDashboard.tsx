import { useTranslation } from 'react-i18next';
import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import {
  Building2,
  ChevronDown,
  ChevronUp,
  Cpu,
  Gauge,
  Package,
  Shield,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  FolderOpen,
  GitBranch,
  Upload,
  FlaskConical,
} from 'lucide-react';
import { AgGridReact } from 'ag-grid-react';
import type { ColDef } from 'ag-grid-community';
import ProjectFiles from './ProjectFiles';
import ProjectTesting from './ProjectTesting';
import StringPatternBusyModal from './StringPatternBusyModal';
import ParsePatternSelectModal from './ParsePatternSelectModal';
import StructuredParseReportPanel from './StructuredParseReportPanel';
import { extractStructuredParseReport } from '../../lib/parseReportUtils';
import * as api from '../../lib/api';
import type { Project, MaintenanceTask, Measurement, ValidationRun, MaterialIssue } from '../../lib/types';
import type {
  ApprovedStringPattern,
  ProjectTopologyInverter,
  ProjectDesignString,
  ScanAnalytics,
} from '../../lib/api';
import { useApp } from '../../contexts/AppContext';
import { registerAgGridModules } from '../../lib/agGridModules';

registerAgGridModules();

interface ProjectDashboardProps {
  projectId: string;
}

type TabId    = 'overview' | 'tasks' | 'measurements' | 'validation' | 'testing';
type SubTabId = 'inverters' | 'strings' | 'materials' | 'files' | 'scan';

/* ── AgGrid column defs for sub-tabs ── */
const INV_COLS: ColDef<ProjectTopologyInverter>[] = [
  {
    field: 'inverter_label' as any,
    headerName: 'Label',
    flex: 1,
    minWidth: 140,
    cellStyle: { fontFamily: 'monospace', fontSize: '12px' },
  },
  {
    field: 'icb_zone' as any,
    headerName: 'ICB',
    width: 110,
    valueFormatter: (p: any) => p.value || '—',
  },
  {
    headerName: 'Strings (found / expected)',
    flex: 1,
    minWidth: 180,
    valueGetter: (p: any) =>
      `${p.data?.detected_string_count ?? ''}${p.data?.expected_string_count != null ? ` / ${p.data.expected_string_count}` : ''}`,
  },
];

const INVALID_COLS: ColDef[] = [
  { headerName: 'Raw Value',  field: 'raw_value',      flex: 1, minWidth: 120, cellStyle: { fontFamily: 'monospace', fontSize: '11px' } },
  { headerName: 'Inverter',   field: 'inverter_key',   width: 90,  valueFormatter: (p: any) => p.value || '—', cellStyle: { fontFamily: 'monospace', fontSize: '11px' } },
  { headerName: 'Reason',     field: 'invalid_reason', flex: 1, minWidth: 140, cellStyle: { color: '#b91c1c', fontSize: '11px' } },
];

const MISSING_COLS: ColDef[] = [
  { headerName: 'Inverter',  field: 'inverter',   width: 100, cellStyle: { fontFamily: 'monospace', fontSize: '11px' } },
  { headerName: 'String No', field: 'string_no',  flex: 1 },
];

const DUPLICATE_COLS: ColDef[] = [
  { headerName: 'String Code', field: 'string_code', flex: 1, minWidth: 110, cellStyle: { fontFamily: 'monospace', fontSize: '11px' } },
  { headerName: 'Inverter',    field: 'inverter',    width: 90,  cellStyle: { fontFamily: 'monospace', fontSize: '11px' } },
  { headerName: 'String No',   field: 'string_no',   width: 90 },
];

const STR_COLS: ColDef<ProjectDesignString>[] = [
  {
    field: 'string_no' as any,
    headerName: 'String',
    flex: 1,
    minWidth: 120,
    cellStyle: { fontFamily: 'monospace', fontSize: '12px' },
  },
  {
    field: 'inverter_no' as any,
    headerName: 'Inverter',
    flex: 1,
    minWidth: 120,
    cellStyle: { fontFamily: 'monospace', fontSize: '12px' },
    valueFormatter: (p: any) => p.value || '—',
  },
  {
    field: 'status' as any,
    headerName: 'Status',
    width: 120,
    cellRenderer: ({ value }: any) => (
      <span className="capitalize">{value}</span>
    ),
  },
];

const MAT_COLS: ColDef<MaterialIssue>[] = [
  { field: 'id' as any, headerName: '#', width: 70 },
  {
    field: 'status' as any,
    headerName: 'Status',
    width: 120,
    cellRenderer: ({ value }: any) => <span className="capitalize">{value}</span>,
  },
  {
    headerName: 'Items',
    flex: 2,
    minWidth: 200,
    valueGetter: (p: any) =>
      p.data?.items?.length
        ? (p.data.items as any[])
            .map((it: any) => `${it.material_name ?? '?'}: ${it.quantity_issued ?? 0} ${it.unit ?? ''}`.trim())
            .join('; ')
        : '—',
  },
  {
    field: 'issued_at' as any,
    headerName: 'Issued',
    width: 150,
    valueFormatter: (p: any) => p.value || '—',
  },
];

const TASK_COLS: ColDef<MaintenanceTask>[] = [
  { field: 'title' as any, headerName: 'Title', flex: 2, minWidth: 160 },
  {
    field: 'status' as any,
    headerName: 'Status',
    width: 120,
    cellRenderer: ({ value }: any) => (
      <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700">{value}</span>
    ),
  },
  {
    field: 'priority' as any,
    headerName: 'Priority',
    width: 110,
    cellRenderer: ({ value }: any) => <span className="capitalize">{value || 'normal'}</span>,
  },
  {
    field: 'task_type' as any,
    headerName: 'Type',
    width: 120,
    cellRenderer: ({ value }: any) => <span className="capitalize">{value || '—'}</span>,
  },
  {
    field: 'assigned_to' as any,
    headerName: 'Assigned To',
    flex: 1,
    minWidth: 120,
    valueFormatter: (p: any) => p.value || '—',
  },
];

const MEAS_COLS: ColDef<Measurement>[] = [
  { field: 'file_name' as any, headerName: 'Filename', flex: 2, minWidth: 160 },
  { field: 'uploaded_at' as any, headerName: 'Uploaded', width: 160 },
  {
    headerName: 'Records',
    width: 110,
    valueGetter: (p: any) => p.data?.records?.length ?? 0,
  },
];

/* ── Mobile Project View ──────────────────────────────────────── */
function MobileProjectView({
  project, tasks, measurements, inverters, stringsByInverter,
  canManage, phaseColors, pc, openTasks, phases,
  activeBusy, phaseDropdownOpen, setPhaseDropdownOpen,
  onSetActive, onUpdatePhase,
}: {
  project: Project;
  tasks: MaintenanceTask[];
  measurements: Measurement[];
  inverters: import('../../lib/api').ProjectTopologyInverter[];
  stringsByInverter: Map<number | null, import('../../lib/api').ProjectDesignString[]>;
  loading: boolean;
  canManage: boolean;
  phaseColors: Record<string, { bg: string; color: string }>;
  pc: { bg: string; color: string };
  openTasks: number;
  phases: string[];
  activeBusy: boolean;
  phaseDropdownOpen: boolean;
  setPhaseDropdownOpen: (v: boolean) => void;
  onSetActive: (v: boolean) => void;
  onUpdatePhase: (p: string) => void;
}) {
  const [expandedInv, setExpandedInv] = useState<Set<number>>(new Set());
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['details']));

  function toggleSection(id: string) {
    setExpandedSections(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  function toggleInv(id: number) {
    setExpandedInv(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  const TASK_STATUS_COLOR: Record<string, string> = {
    open:        '#2563eb',
    in_progress: '#d97706',
    completed:   '#16a34a',
    closed:      '#6b7280',
  };

  const totalStrings = Array.from(stringsByInverter.values()).flat().length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: '#f1f5f9', overflow: 'hidden' }}>

      {/* ── Header ── */}
      <div style={{ background: '#1e3a5f', padding: '16px', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
          <h1 style={{ color: '#fff', fontSize: 17, fontWeight: 700, margin: 0 }}>{project.name}</h1>
          <span style={{ background: pc.bg, color: pc.color, fontSize: 11, fontWeight: 600, padding: '3px 10px', borderRadius: 12 }}>
            {project.phase}
          </span>
        </div>
        {/* Progress bar */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ flex: 1, background: 'rgba(255,255,255,0.2)', borderRadius: 4, height: 5 }}>
            <div style={{ width: `${project.progress_percent}%`, background: '#60a5fa', borderRadius: 4, height: 5, transition: 'width 0.3s' }} />
          </div>
          <span style={{ color: '#93c5fd', fontSize: 12 }}>{project.progress_percent}%</span>
        </div>
      </div>

      {/* ── Action bar ── */}
      <div style={{ background: '#fff', borderBottom: '1px solid #e2e8f0', padding: '10px 16px', display: 'flex', gap: 8, flexShrink: 0, overflowX: 'auto' }}>
        {/* Phase dropdown */}
        <div style={{ position: 'relative' }}>
          <button
            onClick={() => setPhaseDropdownOpen(!phaseDropdownOpen)}
            style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '6px 12px', background: '#f8fafc', border: '1px solid #cbd5e1', borderRadius: 8, fontSize: 13, fontWeight: 500, color: '#334155', cursor: 'pointer', whiteSpace: 'nowrap' }}
          >
            Phase <ChevronDown style={{ width: 14, height: 14 }} />
          </button>
          {phaseDropdownOpen && (
            <div style={{ position: 'absolute', top: '100%', left: 0, zIndex: 50, background: '#fff', border: '1px solid #e2e8f0', borderRadius: 8, boxShadow: '0 4px 16px rgba(0,0,0,0.12)', minWidth: 160, marginTop: 4 }}>
              {phases.map(ph => {
                const c = phaseColors[ph] ?? { bg: '#f3f4f6', color: '#6b7280' };
                return (
                  <button key={ph} onClick={() => onUpdatePhase(ph)}
                    style={{ display: 'block', width: '100%', textAlign: 'left', padding: '9px 14px', fontSize: 13, color: project.phase === ph ? '#2563eb' : '#374151', fontWeight: project.phase === ph ? 600 : 400, background: 'none', border: 'none', cursor: 'pointer' }}>
                    <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: c.color, marginRight: 8 }} />
                    {ph.charAt(0).toUpperCase() + ph.slice(1)}
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Active/Inactive toggle */}
        {canManage && (
          <button
            disabled={activeBusy}
            onClick={() => onSetActive(project.is_active === false)}
            style={{ padding: '6px 12px', background: project.is_active === false ? '#16a34a' : '#f1f5f9', border: `1px solid ${project.is_active === false ? '#16a34a' : '#cbd5e1'}`, borderRadius: 8, fontSize: 13, fontWeight: 500, color: project.is_active === false ? '#fff' : '#334155', cursor: 'pointer', whiteSpace: 'nowrap', opacity: activeBusy ? 0.6 : 1 }}
          >
            {project.is_active === false ? 'Activate' : 'Deactivate'}
          </button>
        )}
      </div>

      {/* ── Stats row ── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 1, background: '#e2e8f0', flexShrink: 0 }}>
        {[
          { label: 'Tasks Open', value: openTasks, icon: '📋' },
          { label: 'Measurements', value: measurements.length, icon: '📊' },
          { label: 'Inverters', value: inverters.length, icon: '⚡' },
          { label: 'Strings', value: totalStrings, icon: '🔗' },
        ].map(s => (
          <div key={s.label} style={{ background: '#fff', padding: '10px 8px', textAlign: 'center' }}>
            <div style={{ fontSize: 18 }}>{s.icon}</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: '#1e293b', lineHeight: 1.1 }}>{s.value}</div>
            <div style={{ fontSize: 10, color: '#64748b', marginTop: 1 }}>{s.label}</div>
          </div>
        ))}
      </div>

      {/* ── Scrollable sections ── */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '12px 12px 24px' }}>

        {/* Project Details */}
        <div style={{ background: '#fff', borderRadius: 12, marginBottom: 10, overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,0.06)' }}>
          <button onClick={() => toggleSection('details')} style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '13px 16px', background: 'none', border: 'none', cursor: 'pointer' }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: '#1e293b' }}>Project Details</span>
            {expandedSections.has('details') ? <ChevronUp style={{ width: 16, height: 16, color: '#64748b' }} /> : <ChevronDown style={{ width: 16, height: 16, color: '#64748b' }} />}
          </button>
          {expandedSections.has('details') && (
            <div style={{ borderTop: '1px solid #f1f5f9', padding: '12px 16px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px 16px' }}>
              {[
                ['Customer',  project.customer_name || '—'],
                ['Site',      project.site_name],
                ['Type',      project.project_type],
                ['Created',   project.created_at ? new Date(project.created_at).toLocaleDateString(undefined, { dateStyle: 'medium' }) : '—'],
              ].map(([l, v]) => (
                <div key={l}>
                  <div style={{ fontSize: 10, fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 2 }}>{l}</div>
                  <div style={{ fontSize: 13, color: '#1e293b' }}>{v}</div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Topology */}
        <div style={{ background: '#fff', borderRadius: 12, marginBottom: 10, overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,0.06)' }}>
          <button onClick={() => toggleSection('topology')} style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '13px 16px', background: 'none', border: 'none', cursor: 'pointer' }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: '#1e293b' }}>Inverters & Strings</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ fontSize: 11, color: '#64748b' }}>{inverters.length} inv · {totalStrings} str</span>
              {expandedSections.has('topology') ? <ChevronUp style={{ width: 16, height: 16, color: '#64748b' }} /> : <ChevronDown style={{ width: 16, height: 16, color: '#64748b' }} />}
            </div>
          </button>
          {expandedSections.has('topology') && (
            <div style={{ borderTop: '1px solid #f1f5f9' }}>
              {inverters.length === 0 ? (
                <p style={{ padding: '12px 16px', fontSize: 13, color: '#94a3b8' }}>No inverters found.</p>
              ) : inverters.map(inv => {
                const strs = stringsByInverter.get(inv.id) ?? [];
                const expanded = expandedInv.has(inv.id);
                return (
                  <div key={inv.id} style={{ borderBottom: '1px solid #f8fafc' }}>
                    <button onClick={() => toggleInv(inv.id)} style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 16px', background: 'none', border: 'none', cursor: 'pointer' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <Cpu style={{ width: 14, height: 14, color: '#2563eb' }} />
                        <span style={{ fontSize: 13, fontFamily: 'monospace', color: '#1e293b' }}>{inv.inverter_label}</span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span style={{ fontSize: 11, color: '#64748b' }}>{strs.length} strings</span>
                        {expanded ? <ChevronUp style={{ width: 14, height: 14, color: '#94a3b8' }} /> : <ChevronDown style={{ width: 14, height: 14, color: '#94a3b8' }} />}
                      </div>
                    </button>
                    {expanded && strs.length > 0 && (
                      <div style={{ padding: '8px 16px 12px', display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                        {strs.map(s => (
                          <span key={s.id} style={{ fontSize: 11, fontFamily: 'monospace', padding: '3px 8px', borderRadius: 6, background: '#f1f5f9', color: '#334155' }}>{`STR-${s.string_no}`}</span>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Tasks */}
        <div style={{ background: '#fff', borderRadius: 12, marginBottom: 10, overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,0.06)' }}>
          <button onClick={() => toggleSection('tasks')} style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '13px 16px', background: 'none', border: 'none', cursor: 'pointer' }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: '#1e293b' }}>Tasks</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ fontSize: 11, color: '#64748b' }}>{tasks.length} total</span>
              {expandedSections.has('tasks') ? <ChevronUp style={{ width: 16, height: 16, color: '#64748b' }} /> : <ChevronDown style={{ width: 16, height: 16, color: '#64748b' }} />}
            </div>
          </button>
          {expandedSections.has('tasks') && (
            <div style={{ borderTop: '1px solid #f1f5f9' }}>
              {tasks.length === 0
                ? <p style={{ padding: '12px 16px', fontSize: 13, color: '#94a3b8' }}>No tasks yet.</p>
                : tasks.slice(0, 20).map(task => (
                  <div key={task.id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 16px', borderBottom: '1px solid #f8fafc' }}>
                    <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: TASK_STATUS_COLOR[task.status] ?? '#6b7280', flexShrink: 0 }} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 13, color: '#1e293b', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{task.title}</div>
                      <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 1 }}>{task.status} · {task.priority}</div>
                    </div>
                  </div>
                ))
              }
            </div>
          )}
        </div>

        {/* Measurements */}
        <div style={{ background: '#fff', borderRadius: 12, marginBottom: 10, overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,0.06)' }}>
          <button onClick={() => toggleSection('meas')} style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '13px 16px', background: 'none', border: 'none', cursor: 'pointer' }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: '#1e293b' }}>Measurements</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ fontSize: 11, color: '#64748b' }}>{measurements.length} records</span>
              {expandedSections.has('meas') ? <ChevronUp style={{ width: 16, height: 16, color: '#64748b' }} /> : <ChevronDown style={{ width: 16, height: 16, color: '#64748b' }} />}
            </div>
          </button>
          {expandedSections.has('meas') && (
            <div style={{ borderTop: '1px solid #f1f5f9' }}>
              {measurements.length === 0
                ? <p style={{ padding: '12px 16px', fontSize: 13, color: '#94a3b8' }}>No measurements yet.</p>
                : measurements.slice(0, 10).map(m => (
                  <div key={m.id} style={{ padding: '10px 16px', borderBottom: '1px solid #f8fafc', fontSize: 12, color: '#334155' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                      <span style={{ fontFamily: 'monospace' }}>{m.string_label || m.site_label || '—'}</span>
                      <span style={{ color: '#64748b' }}>{m.uploaded_at ? new Date(m.uploaded_at).toLocaleDateString() : '—'}</span>
                    </div>
                    <div style={{ display: 'flex', gap: 12, color: '#64748b', fontSize: 11 }}>
                      {m.voc_v != null && <span>Voc {m.voc_v}V</span>}
                      {m.isc_a != null && <span>Isc {m.isc_a}A</span>}
                      {m.pmax_w != null && <span>Pmax {m.pmax_w}W</span>}
                    </div>
                  </div>
                ))
              }
            </div>
          )}
        </div>

      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════ */
export default function ProjectDashboard({ projectId }: ProjectDashboardProps) {
  const { t } = useTranslation();
  const { user } = useApp();
  const canManageProject = user?.role === 'admin' || user?.role === 'manager';
  const [project, setProject] = useState<Project | null>(null);
  const [tasks, setTasks] = useState<MaintenanceTask[]>([]);
  const [measurements, setMeasurements] = useState<Measurement[]>([]);
  const [validation, setValidation] = useState<ValidationRun | null>(null);
  const [activeTab,    setActiveTab]    = useState<TabId>('overview');
  const [activeSubTab, setActiveSubTab] = useState<SubTabId>('files');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [phaseDropdownOpen, setPhaseDropdownOpen] = useState(false);
  const [showValidationResults, setShowValidationResults] = useState(false);
  const [projectFiles, setProjectFiles] = useState<{ id: string; original_name: string; file_type: string; is_active?: boolean }[]>([]);
  const [topologyInverters, setTopologyInverters] = useState<ProjectTopologyInverter[]>([]);
  const [designStrings, setDesignStrings] = useState<ProjectDesignString[]>([]);
  const [projectIssues, setProjectIssues] = useState<MaterialIssue[]>([]);
  const [scanAnalytics, setScanAnalytics] = useState<ScanAnalytics | null>(null);
  const [suiUploading, setSuiUploading] = useState(false);
  const [activeBusy, setActiveBusy] = useState(false);
  const [scanBusy, setScanBusy] = useState(false);
  // Step-progress modal state
  type ScanStep = { label: string; state: 'pending' | 'running' | 'done' | 'error' };
  const [scanSteps, setScanSteps] = useState<ScanStep[]>([]);
  const [scanModalOpen, setScanModalOpen] = useState(false);
  const [scanSummary, setScanSummary] = useState<string | null>(null);
  const [scanError, setScanError] = useState<string | null>(null);
  const [scanPct, setScanPct] = useState(0);
  const [scanSubLabel, setScanSubLabel] = useState<string | null>(null);
  // Confirmation modal (shown before re-parse when existing data is present)
  const [confirmScanOpen, setConfirmScanOpen] = useState(false);
  const [pendingScanIds, setPendingScanIds] = useState<string[]>([]);
  const [parsePatternModalOpen, setParsePatternModalOpen] = useState(false);
  const [patternBusy, setPatternBusy] = useState(false);
  const [patternBusyFileCount, setPatternBusyFileCount] = useState(0);
  const suiInputRef = useRef<HTMLInputElement>(null);

  // ── Mobile detection (must be at top level, before any early returns) ──
  const [windowWidth, setWindowWidth] = useState(() => window.innerWidth);
  useEffect(() => {
    const handler = () => setWindowWidth(window.innerWidth);
    window.addEventListener('resize', handler);
    return () => window.removeEventListener('resize', handler);
  }, []);
  const isMobile = windowWidth < 768;

  // ── Groups strings by inverter for mobile topology view ───────────────
  const stringsByInverter = useMemo(() => {
    const map = new Map<number | null, typeof designStrings>();
    for (const s of designStrings) {
      const key = s.inverter_id ?? null;
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(s);
    }
    return map;
  }, [designStrings]);

  const allInvalidRows = useMemo(() => {
    const rows = [...(scanAnalytics?.invalid_rows ?? [])];
    const suffixRows = (scanAnalytics?.design_metadata?.suffix_string_issues ?? []).map((issue) => ({
      string_code: null,
      raw_value: issue.found,
      inverter_key: null,
      invalid_reason: issue.issue,
    }));
    const invalidAbRows = (scanAnalytics?.design_metadata?.invalid_ab_labels ?? []).map((label) => ({
      string_code: null,
      raw_value: label,
      inverter_key: null,
      invalid_reason: 'String has alphabetic A/B suffix and does not match the configured naming pattern.',
    }));
    const merged = [...rows, ...suffixRows, ...invalidAbRows];
    const seen = new Set<string>();
    return merged.filter((row) => {
      const key = JSON.stringify([
        row.string_code ?? null,
        row.raw_value ?? null,
        row.inverter_key ?? null,
        row.invalid_reason ?? null,
      ]);
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }, [scanAnalytics]);

  const dashboardStructuredReport = useMemo(() => {
    if (!scanAnalytics) return null;
    if (scanAnalytics.parse_report) return scanAnalytics.parse_report;
    const dm = scanAnalytics.design_metadata;
    if (dm && typeof dm === 'object' && 'parse_report' in dm && dm.parse_report) {
      return dm.parse_report;
    }
    return extractStructuredParseReport(dm as unknown);
  }, [scanAnalytics]);

  const refreshProjectFiles = useCallback(() => {
    fetch(`/api/projects/${projectId}/files`)
      .then((r) => r.json())
      .then((data) => setProjectFiles(Array.isArray(data) ? data : []))
      .catch(() => setProjectFiles([]));
  }, [projectId]);

  /** Called by ProjectFiles after any file list change (upload/replace/toggle/delete). No scan. */
  const onFilesUpdated = useCallback(() => {
    refreshProjectFiles();
  }, [refreshProjectFiles]);

  /** Internal: run full parse/sync via POST /scan-run (avoids chunked SSE through proxies). */
  const _runScan = useCallback((newFileIds: string[], approvedPattern?: ApprovedStringPattern, detectToken?: string | null) => {
    const STEPS: ScanStep[] = [
      { label: 'Parsing design file',           state: 'pending' },
      { label: 'Extracting strings & inverters', state: 'pending' },
      { label: 'Syncing topology',               state: 'pending' },
      { label: 'Syncing design strings',         state: 'pending' },
      { label: 'Refreshing project data',        state: 'pending' },
    ];

    const set = (idx: number, state: ScanStep['state']) =>
      setScanSteps(prev => prev.map((s, i) => i === idx ? { ...s, state } : s));

    setScanSteps(STEPS);
    setScanSummary(null);
    setScanError(null);
    setScanPct(0);
    setScanSubLabel(null);
    setScanModalOpen(true);
    setScanBusy(true);

    if (approvedPattern) {
      setProject((prev) => (prev ? { ...prev, string_pattern: approvedPattern.pattern_name } : prev));
    }

    const applyScanCompleteRefetch = (note?: string) => {
      const pid = Number(projectId);
      setScanPct(100);
      setScanSubLabel(null);
      Promise.all([
        api.listProjectTopologyInverters(pid).catch(() => [] as ProjectTopologyInverter[]),
        api.listProjectDesignStrings(pid).catch(() => [] as ProjectDesignString[]),
        api.getScanAnalytics(pid).catch(() => null),
      ]).then(([inv, strs, analytics]) => {
        if (analytics) setScanAnalytics(analytics);
        setTopologyInverters(inv);
        setDesignStrings(strs);
        setScanSteps((prev) => prev.map((s) => ({ ...s, state: 'done' })));
        const base = `${inv.length} inverters · ${strs.length} strings synced`;
        setScanSummary(note ? `${base} — ${note}` : base);
        setScanBusy(false);
        setActiveSubTab('inverters');
      }).catch(() => {
        setScanBusy(false);
      });
    };

    void (async () => {
      const progressLabels = [
        'Parsing design file…',
        'Extracting strings & inverters…',
        'Syncing topology…',
        'Syncing design strings…',
        'Saving analytics…',
      ];
      let labelIdx = 0;
      set(0, 'running');
      setScanSubLabel(progressLabels[0]!);
      setScanPct(8);
      const tick = window.setInterval(() => {
        labelIdx = Math.min(labelIdx + 1, progressLabels.length - 1);
        setScanSubLabel(progressLabels[labelIdx]!);
        setScanPct((p) => Math.min(90, p + 12));
      }, 5000);

      try {
        const res = await fetch(`/api/projects/${projectId}/scan-run`, {
          method: 'POST',
          credentials: 'include',
          headers: {
            ...api.scanStreamFetchHeaders(),
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            file_ids: newFileIds.join(','),
            approved_pattern_name: approvedPattern?.pattern_name ?? undefined,
            approved_pattern_regex: approvedPattern?.pattern_regex ?? undefined,
            detect_token: detectToken ?? undefined,
          }),
        });
        const raw = await res.text();
        let j: Record<string, unknown> = {};
        try {
          j = raw ? (JSON.parse(raw) as Record<string, unknown>) : {};
        } catch {
          /* ignore */
        }
        if (!res.ok) {
          const d = j.detail;
          const msg =
            typeof d === 'string'
              ? d
              : Array.isArray(d)
                ? d
                    .map((x) => (typeof x === 'object' && x !== null ? JSON.stringify(x) : String(x)))
                    .join('; ')
                : d != null
                  ? JSON.stringify(d)
                  : `Scan failed (${res.status})`;
          setScanError(msg);
          setScanSteps((prev) => prev.map((s) => (s.state === 'running' ? { ...s, state: 'error' } : s)));
          setScanBusy(false);
          return;
        }
        setScanPct(100);
        setScanSubLabel(null);
        applyScanCompleteRefetch();
      } catch {
        setScanError('Connection to server lost during scan. Please try again.');
        setScanSteps((prev) => prev.map((s) => (s.state === 'running' ? { ...s, state: 'error' } : s)));
        setScanBusy(false);
      } finally {
        window.clearInterval(tick);
      }
    })();
  }, [projectId]);

  const openParsePatternChoice = useCallback((fileIds: string[]) => {
    if (!fileIds.length) return;
    setPendingScanIds(fileIds);
    setPatternBusyFileCount(fileIds.length);
    setParsePatternModalOpen(true);
  }, []);

  /** Called when user clicks "Parse Data" — shows confirmation if existing data. */
  const onParseFiles = useCallback((fileIds: string[]) => {
    if (!fileIds.length) return;
    if (topologyInverters.length > 0 || designStrings.length > 0) {
      setPendingScanIds(fileIds);
      setConfirmScanOpen(true);
    } else {
      openParsePatternChoice(fileIds);
    }
  }, [topologyInverters.length, designStrings.length, openParsePatternChoice]);

  const phases = ['design','validation','implementation','testing','commissioning','maintenance','closed'];

  useEffect(() => {
    async function load() {
      const pid = Number(projectId);
      try {
        setLoading(true);
        const [proj, taskList, allMeasurements, files, inv, strRows, issues, analytics] = await Promise.all([
          api.getProject(pid),
          api.listTasks(pid),
          api.listMeasurements(),
          fetch(`/api/projects/${projectId}/files`).then((r) => r.json()).catch(() => []),
          api.listProjectTopologyInverters(pid).catch(() => [] as ProjectTopologyInverter[]),
          api.listProjectDesignStrings(pid).catch(() => [] as ProjectDesignString[]),
          api.listIssues(pid).catch(() => [] as MaterialIssue[]),
          api.getScanAnalytics(pid),
        ]);
        setProject(proj);
        setTasks(taskList);
        setMeasurements(allMeasurements);
        setProjectFiles(Array.isArray(files) ? files : []);
        setTopologyInverters(inv);
        setDesignStrings(strRows);
        setProjectIssues(issues);
        setScanAnalytics(analytics);
      } catch (err) {
        console.error('Failed to load project:', err);
        setError('Failed to load project data');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [projectId]);

  async function handleValidateDesign() {
    try {
      const result = await api.validateDesign(Number(projectId));
      setValidation(result);
      setActiveTab('validation');
      setShowValidationResults(result.issues.length > 0);
    } catch (err) {
      console.error('Validation failed:', err);
    }
  }

  async function handleUploadSui(e: React.ChangeEvent<HTMLInputElement>) {
    if (!e.target.files?.length) return;
    setSuiUploading(true);
    try {
      await api.uploadSui(e.target.files);
      const all = await api.listMeasurements();
      setMeasurements(all);
    } catch (err: any) {
      console.error('SUI upload failed:', err);
    } finally {
      setSuiUploading(false);
      e.target.value = '';
    }
  }

  async function handleUpdatePhase(phase: string) {
    try {
      const updated = await api.updatePhase(Number(projectId), phase);
      setProject(updated);
      setPhaseDropdownOpen(false);
    } catch (err) {
      console.error('Failed to update phase:', err);
    }
  }

  async function handleSetActive(is_active: boolean) {
    setActiveBusy(true);
    try {
      const updated = await api.setProjectActive(Number(projectId), is_active);
      setProject(updated);
    } catch (err) {
      console.error('Failed to update project status:', err);
    } finally {
      setActiveBusy(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    );
  }

  if (error || !project) {
    return (
      <div className="p-6 text-center text-red-600">
        <p>{error || 'Project not found'}</p>
      </div>
    );
  }

  const PHASE_COLORS: Record<string, { bg: string; color: string }> = {
    design:         { bg: '#ede9fe', color: '#7c3aed' },
    validation:     { bg: '#fef3c7', color: '#d97706' },
    implementation: { bg: '#dbeafe', color: '#2563eb' },
    testing:        { bg: '#ffedd5', color: '#ea580c' },
    commissioning:  { bg: '#ccfbf1', color: '#0f766e' },
    maintenance:    { bg: '#dcfce7', color: '#16a34a' },
    closed:         { bg: '#f3f4f6', color: '#6b7280' },
  };

  // ── Mobile render ─────────────────────────────────────────────────
  if (isMobile) {
    const pc = PHASE_COLORS[project.phase] ?? { bg: '#f3f4f6', color: '#6b7280' };
    const openTasks = tasks.filter(t => t.status !== 'completed' && t.status !== 'closed').length;
    return <MobileProjectView
      project={project}
      tasks={tasks}
      measurements={measurements}
      inverters={topologyInverters}
      stringsByInverter={stringsByInverter}
      loading={false}
      canManage={canManageProject}
      phaseColors={PHASE_COLORS}
      pc={pc}
      openTasks={openTasks}
      phases={phases}
      activeBusy={activeBusy}
      phaseDropdownOpen={phaseDropdownOpen}
      setPhaseDropdownOpen={setPhaseDropdownOpen}
      onSetActive={handleSetActive}
      onUpdatePhase={handleUpdatePhase}
    />;
  }

  const phaseColor: Record<string, string> = {
    design:         'bg-purple-100 text-purple-700',
    validation:     'bg-yellow-100 text-yellow-700',
    implementation: 'bg-blue-100 text-blue-700',
    testing:        'bg-orange-100 text-orange-700',
    commissioning:  'bg-teal-100 text-teal-700',
    maintenance:    'bg-green-100 text-green-700',
    closed:         'bg-gray-100 text-gray-600',
  };

  const tabs: { id: TabId; label: string; icon?: React.ReactNode }[] = [
    { id: 'overview',     label: t('project.overview', 'Overview') },
    { id: 'tasks',        label: t('project.tasks', 'Tasks') },
    { id: 'measurements', label: t('project.measurements', 'Measurements'), icon: <Gauge className="h-3.5 w-3.5" /> },
    { id: 'testing',      label: 'Testing',    icon: <FlaskConical className="h-3.5 w-3.5" /> },
    { id: 'validation',   label: t('project.validation', 'Validation') },
  ];

  /* ── Empty-state helper for grids ── */
  const GridEmpty = ({ msg }: { msg: string }) => (
    <p className="p-4 text-sm text-gray-500">{msg}</p>
  );

  return (
    <>
    {/* ── Main shell: flex column fills parent (App content area is flex-1 overflow-hidden) ── */}
    <div className="flex flex-col h-full overflow-hidden">

      {/* ── Fixed top: inactive banner + project header + tab bar ── */}
      <div className="shrink-0 px-6 pt-4 pb-0 space-y-3">

        {project.is_active === false && (
          <div
            className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-2.5 text-amber-900"
            role="status"
          >
            <p className="text-sm font-medium">{t('projects.inactive_banner')}</p>
            {canManageProject && (
              <button
                type="button"
                disabled={activeBusy}
                onClick={() => void handleSetActive(true)}
                className="inline-flex items-center gap-2 rounded-lg bg-amber-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-amber-700 disabled:opacity-60"
              >
                {activeBusy && <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />}
                {t('projects.set_active')}
              </button>
            )}
          </div>
        )}

        {/* Project header */}
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-3 mb-1.5">
              <h1 className="text-xl font-bold text-gray-900">{project.name}</h1>
              <span className={`px-3 py-0.5 rounded-full text-xs font-medium ${phaseColor[project.phase] || 'bg-gray-100 text-gray-700'}`}>
                {project.phase}
              </span>
            </div>
            <div className="w-56">
              <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
                <span>Progress</span>
                <span>{project.progress_percent}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-1.5">
                <div className="bg-blue-600 h-1.5 rounded-full" style={{ width: `${project.progress_percent}%` }} />
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {canManageProject && project.is_active !== false && (
              <button
                type="button"
                disabled={activeBusy}
                onClick={() => void handleSetActive(false)}
                className="inline-flex items-center gap-2 px-3 py-1.5 border border-gray-300 bg-white text-gray-700 rounded-lg hover:bg-gray-50 text-sm font-medium disabled:opacity-60"
              >
                {t('projects.set_inactive')}
              </button>
            )}
            <button
              onClick={handleValidateDesign}
              className="inline-flex items-center gap-2 px-3 py-1.5 bg-amber-500 text-white rounded-lg hover:bg-amber-600 text-sm font-medium"
            >
              <Shield className="h-4 w-4" />
              Validate Design
            </button>
            <div className="relative">
              <button
                onClick={() => setPhaseDropdownOpen(!phaseDropdownOpen)}
                className="inline-flex items-center gap-2 px-3 py-1.5 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 text-sm font-medium"
              >
                Update Phase <ChevronDown className="h-4 w-4" />
              </button>
              {phaseDropdownOpen && (
                <div className="absolute right-0 mt-1 w-48 bg-white border border-gray-200 rounded-lg shadow-lg z-10">
                  {phases.map((phase) => (
                    <button
                      key={phase}
                      onClick={() => handleUpdatePhase(phase)}
                      className={`w-full text-left px-4 py-2 text-sm hover:bg-gray-50 first:rounded-t-lg last:rounded-b-lg ${
                        project.phase === phase ? 'font-medium text-blue-600' : 'text-gray-700'
                      }`}
                    >
                      {phase.charAt(0).toUpperCase() + phase.slice(1)}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Main tab bar */}
        <div className="border-b border-gray-200">
          <div className="flex gap-6">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`pb-2.5 text-sm font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
                  activeTab === tab.id
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                {tab.icon}{tab.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* ── Flex-1 content area: each tab fills remaining height ── */}
      <div className="flex-1 min-h-0 overflow-hidden px-6 pb-4">

        {/* ── Overview tab ── */}
        {activeTab === 'overview' && (
          <div className="flex flex-col h-full gap-3 pt-3">

            {/* Project metadata — compact, fixed height */}
            <section className="shrink-0">
              <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-1.5">
                <Building2 className="h-3.5 w-3.5" />
                {t('project.overview_metadata', 'Project details')}
              </h2>
              <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
                <dl className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 divide-x divide-gray-100">
                  {[
                    ['ID',                              String(project.id)],
                    [t('projects.fields.customer'),     project.customer_name || '—'],
                    [t('projects.fields.site'),         project.site_name],
                    [t('projects.fields.type'),         project.project_type],
                    [t('project.created', 'Created'),   project.created_at ? new Date(project.created_at).toLocaleDateString(undefined, { dateStyle: 'medium' }) : '—'],
                  ].map(([label, value]) => (
                    <div key={String(label)} className="px-3 py-2">
                      <dt className="text-[10px] font-medium text-gray-400 uppercase tracking-wide">{label}</dt>
                      <dd className="text-sm text-gray-900 mt-0.5 truncate" title={String(value)}>{value}</dd>
                    </div>
                  ))}
                </dl>

                {project.description?.trim() && (
                  <div className="px-3 py-2 border-t border-gray-100">
                    <dt className="text-[10px] font-medium text-gray-400 uppercase tracking-wide">Description</dt>
                    <dd className="text-sm text-gray-700 mt-0.5">{project.description}</dd>
                  </div>
                )}
              </div>
            </section>

            {/* Sub-tabs section — takes all remaining height */}
            <section className="flex flex-col flex-1 min-h-0">

              {/* Sub-tab bar */}
              <div className="flex gap-1 border-b border-gray-200 mb-1 overflow-x-auto shrink-0">
                {(
                  [
                    { id: 'files'     as SubTabId, label: t('project.files', 'Files'),              icon: <FolderOpen className="h-3.5 w-3.5" />, badge: projectFiles.length || undefined },
                    { id: 'inverters' as SubTabId, label: t('project.overview_inverters', 'Inverters'),     icon: <Cpu className="h-3.5 w-3.5" />,       badge: topologyInverters.length || undefined },
                    { id: 'strings'   as SubTabId, label: t('project.overview_strings', 'Strings'),         icon: <GitBranch className="h-3.5 w-3.5" />,  badge: designStrings.length || undefined },
                    { id: 'materials' as SubTabId, label: t('project.overview_inventory', 'Materials'),     icon: <Package className="h-3.5 w-3.5" />,    badge: projectIssues.length || undefined },
                    { id: 'scan'      as SubTabId, label: 'Design Scan', icon: <AlertTriangle className="h-3.5 w-3.5" />,
                      badge: scanAnalytics?.design_metadata
                        ? ((scanAnalytics.design_metadata.validation_findings?.length ?? 0) + (scanAnalytics.design_metadata.output_validation_findings?.length ?? 0)) || undefined
                        : undefined },
                  ] as { id: SubTabId; label: string; icon: React.ReactNode; badge?: number }[]
                ).map(st => (
                  <button
                    key={st.id}
                    onClick={() => setActiveSubTab(st.id)}
                    className={`flex items-center gap-1.5 px-3 py-2 text-xs font-medium whitespace-nowrap border-b-2 transition-colors ${
                      activeSubTab === st.id
                        ? 'border-blue-600 text-blue-600'
                        : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                    }`}
                  >
                    {st.icon}
                    {st.label}
                    {st.badge != null && st.badge > 0 && (
                      <span className={`ml-1 rounded-full px-1.5 py-0.5 text-[10px] font-semibold ${
                        activeSubTab === st.id ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-500'
                      }`}>{st.badge}</span>
                    )}
                  </button>
                ))}
              </div>

              {/* Sub-tab grid panels — fill remaining height */}
              <div className="flex-1 min-h-0 pt-1">

                {/* Files */}
                {activeSubTab === 'files' && (
                  <ProjectFiles
                    projectId={Number(projectId)}
                    onFilesUpdated={onFilesUpdated}
                    onParseFiles={onParseFiles}
                  />
                )}

                {/* Inverters */}
                {activeSubTab === 'inverters' && (() => {
                  const missingRows = Object.entries(scanAnalytics?.missing_strings_by_inverter ?? {})
                    .flatMap(([inverter, nos]) => nos.map(string_no => ({ inverter, string_no })));

                  // Build duplicate rows with string_code derived from inverter + string_no
                  const dupRows = Object.entries(scanAnalytics?.duplicate_string_numbers_by_inverter ?? {})
                    .flatMap(([inverter, nos]) => nos.map(string_no => ({
                      inverter,
                      string_no,
                      string_code: `S.${inverter}.${string_no}`,
                    })));

                  // Outlier strings — numbers that exist in the PDF but are far outside
                  // the main cluster for their inverter (likely misattributed / erroneous labels)
                  const outlierRows = Object.entries(scanAnalytics?.outlier_strings_by_inverter ?? {})
                    .flatMap(([inverter, nos]) => nos.map(string_no => ({
                      inverter,
                      string_no,
                      string_code: `S.${inverter}.${string_no}`,
                    })));

                  // Exclude "invalid" rows that are really just duplicate reports — they already appear in dupRows
                  const invalidRows = allInvalidRows
                    .filter(r => !r.invalid_reason?.toLowerCase().includes('duplicate'));
                  const hasAnalytics = !!scanAnalytics;

                  return (
                    <div className="flex flex-col h-full gap-2">
                      {dashboardStructuredReport && (
                        <div className="shrink-0 overflow-y-auto max-h-[min(480px,45vh)]">
                          <StructuredParseReportPanel report={dashboardStructuredReport} />
                        </div>
                      )}
                      {/* Pattern badge + totals */}
                      <div className="shrink-0 flex items-center gap-3 flex-wrap">
                        <span className="text-xs text-gray-400">
                          {topologyInverters.length} inverters · {designStrings.length} strings
                          {scanAnalytics && (<>
                            {' · '}<span className="text-green-600">{scanAnalytics.valid_count} valid</span>
                            {scanAnalytics.invalid_count > 0 && <>{', '}<span className="text-red-500">{scanAnalytics.invalid_count} invalid</span></>}
                            {missingRows.length > 0 && <>{', '}<span className="text-amber-500">{missingRows.length} missing</span></>}
                            {dupRows.length > 0 && <>{', '}<span className="text-orange-500">{dupRows.length} duplicate</span></>}
                            {outlierRows.length > 0 && <>{', '}<span className="text-purple-500">{outlierRows.length} outlier</span></>}
                          </>)}
                        </span>
                      </div>

                      {/* Main inverters grid */}
                      {topologyInverters.length === 0
                        ? <GridEmpty msg={t('project.overview_none_inverters', 'No inverter topology stored yet. Upload a design file to auto-scan.')} />
                        : <div className="ag-theme-quartz flex-1 min-h-0 rounded-lg overflow-hidden border border-gray-200">
                            <AgGridReact<ProjectTopologyInverter>
                              rowData={topologyInverters}
                              columnDefs={INV_COLS}
                              rowHeight={36}
                              headerHeight={32}
                              suppressCellFocus
                            />
                          </div>
                      }

                      {/* Analytics grids — shown when any data exists */}
                      {hasAnalytics && (
                        <div className="shrink-0 grid grid-cols-4 gap-2" style={{ height: 200 }}>
                          {/* Invalid */}
                          <div className="flex flex-col min-h-0">
                            <p className="text-[11px] font-semibold text-red-600 mb-1 shrink-0">
                              Invalid strings ({invalidRows.length})
                            </p>
                            <div className="ag-theme-quartz flex-1 min-h-0 rounded-lg overflow-hidden border border-red-200">
                              <AgGridReact rowData={invalidRows} columnDefs={INVALID_COLS}
                                rowHeight={30} headerHeight={28} suppressCellFocus
                                overlayNoRowsTemplate="<span style='font-size:11px;color:#9ca3af'>None</span>" />
                            </div>
                          </div>
                          {/* Missing */}
                          <div className="flex flex-col min-h-0">
                            <p className="text-[11px] font-semibold text-amber-600 mb-1 shrink-0">
                              Missing strings ({missingRows.length})
                            </p>
                            <div className="ag-theme-quartz flex-1 min-h-0 rounded-lg overflow-hidden border border-amber-200">
                              <AgGridReact rowData={missingRows} columnDefs={MISSING_COLS}
                                rowHeight={30} headerHeight={28} suppressCellFocus
                                overlayNoRowsTemplate="<span style='font-size:11px;color:#9ca3af'>None</span>" />
                            </div>
                          </div>
                          {/* Duplicates */}
                          <div className="flex flex-col min-h-0">
                            <p className="text-[11px] font-semibold text-orange-600 mb-1 shrink-0">
                              Duplicate strings ({dupRows.length})
                            </p>
                            <div className="ag-theme-quartz flex-1 min-h-0 rounded-lg overflow-hidden border border-orange-200">
                              <AgGridReact rowData={dupRows} columnDefs={DUPLICATE_COLS}
                                rowHeight={30} headerHeight={28} suppressCellFocus
                                overlayNoRowsTemplate="<span style='font-size:11px;color:#9ca3af'>None</span>" />
                            </div>
                          </div>
                          {/* Outliers — strings present in PDF but far outside the expected cluster for their inverter */}
                          <div className="flex flex-col min-h-0">
                            <p className="text-[11px] font-semibold text-purple-600 mb-1 shrink-0">
                              Outlier strings ({outlierRows.length})
                            </p>
                            <div className="ag-theme-quartz flex-1 min-h-0 rounded-lg overflow-hidden border border-purple-200">
                              <AgGridReact rowData={outlierRows} columnDefs={DUPLICATE_COLS}
                                rowHeight={30} headerHeight={28} suppressCellFocus
                                overlayNoRowsTemplate="<span style='font-size:11px;color:#9ca3af'>None</span>" />
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })()}

                {/* Strings */}
                {activeSubTab === 'strings' && (
                  <div className="flex flex-col h-full min-h-0">
                    {designStrings.length === 0 && allInvalidRows.length === 0 ? (
                      <GridEmpty msg={t('project.overview_none_strings', 'No DC strings in the design model yet.')} />
                    ) : (
                      <div className="flex flex-col flex-1 min-h-0 gap-2">
                        <div className="shrink-0 text-xs text-gray-500">
                          <span>{designStrings.length} synced design strings</span>
                          {allInvalidRows.length > 0 && (
                            <span>{' · '}<span className="text-red-600">{allInvalidRows.length} invalid strings</span></span>
                          )}
                        </div>
                        <div className="grid grid-cols-1 xl:grid-cols-2 gap-3 flex-1 min-h-0">
                          <div className="flex flex-col min-h-0">
                            <p className="text-[11px] font-semibold text-gray-700 mb-1 shrink-0">
                              Design strings ({designStrings.length})
                            </p>
                            {designStrings.length === 0 ? (
                              <GridEmpty msg={t('project.overview_none_strings', 'No DC strings in the design model yet.')} />
                            ) : (
                              <div className="ag-theme-quartz flex-1 min-h-0 rounded-lg overflow-hidden border border-gray-200">
                                <AgGridReact<ProjectDesignString>
                                  rowData={designStrings}
                                  columnDefs={STR_COLS}
                                  rowHeight={38}
                                  headerHeight={34}
                                  suppressCellFocus
                                />
                              </div>
                            )}
                          </div>
                          <div className="flex flex-col min-h-0">
                            <p className="text-[11px] font-semibold text-red-600 mb-1 shrink-0">
                              Invalid strings ({allInvalidRows.length})
                            </p>
                            {allInvalidRows.length === 0 ? (
                              <GridEmpty msg="No invalid strings detected." />
                            ) : (
                              <div className="ag-theme-quartz flex-1 min-h-0 rounded-lg overflow-hidden border border-red-200">
                                <AgGridReact
                                  rowData={allInvalidRows}
                                  columnDefs={INVALID_COLS}
                                  rowHeight={34}
                                  headerHeight={30}
                                  suppressCellFocus
                                />
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Materials */}
                {activeSubTab === 'materials' && (
                  <div className="flex flex-col h-full min-h-0">
                    {projectIssues.length === 0
                      ? <GridEmpty msg={t('project.overview_none_inventory', 'No material issues recorded for this project.')} />
                      : <div className="ag-theme-quartz flex-1 min-h-0 rounded-lg overflow-hidden border border-gray-200">
                          <AgGridReact<MaterialIssue>
                            rowData={projectIssues}
                            columnDefs={MAT_COLS}
                            rowHeight={38}
                            headerHeight={34}
                            suppressCellFocus
                          />
                        </div>
                    }
                  </div>
                )}

                {/* Design Scan metadata */}
                {activeSubTab === 'scan' && (() => {
                  const dm = scanAnalytics?.design_metadata;
                  if (!dm) {
                    return (
                      <div className="flex flex-col items-center justify-center h-full gap-2 text-gray-400">
                        <AlertTriangle className="h-8 w-8 text-gray-300" />
                        <p className="text-sm">No design scan data yet. Upload a design file to auto-scan.</p>
                      </div>
                    );
                  }
                  const findings = [...(dm.validation_findings ?? []), ...(dm.output_validation_findings ?? [])];
                  const severityColor = (s: string) =>
                    s === 'high' ? 'text-red-600 bg-red-50 border-red-200'
                    : s === 'medium' ? 'text-amber-600 bg-amber-50 border-amber-200'
                    : 'text-blue-600 bg-blue-50 border-blue-200';
                  const MetaSection = ({ title, children }: { title: string; children: React.ReactNode }) => (
                    <div>
                      <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-widest mb-1.5">{title}</p>
                      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
                        <dl className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 divide-x divide-y divide-gray-100">
                          {children}
                        </dl>
                      </div>
                    </div>
                  );
                  const Cell = ({ label, value }: { label: string; value: React.ReactNode }) => (
                    <div className="px-3 py-2">
                      <dt className="text-[10px] font-medium text-gray-400 uppercase tracking-wide">{label}</dt>
                      <dd className="text-sm text-gray-900 mt-0.5 truncate font-mono" title={String(value ?? '')}>{value ?? '—'}</dd>
                    </div>
                  );
                  return (
                    <div className="h-full overflow-y-auto pr-1 space-y-3 pb-2">
                      {/* Site info */}
                      <MetaSection title="Site">
                        <Cell label="Project Name" value={dm.project_name} />
                        <Cell label="Site Code" value={dm.site_code} />
                        <Cell label="Site Name" value={dm.site_name} />
                        <Cell label="Source File" value={dm.source_document} />
                        <Cell label="Country" value={dm.country} />
                        <Cell label="Region" value={dm.region} />
                        <Cell label="Coordinates" value={dm.coordinates ?? (dm.latitude != null ? `${dm.latitude}N ${dm.longitude}E` : null)} />
                        <Cell label="Pages" value={dm.page_count} />
                      </MetaSection>

                      {/* System specs */}
                      <MetaSection title="System Specs">
                        <Cell label="System Rating" value={dm.system_rating_kwp != null ? `${dm.system_rating_kwp} kWp` : dm.plant_capacity_mw != null ? `${(dm.plant_capacity_mw * 1000).toFixed(0)} kWp` : null} />
                        <Cell label="Plant Capacity" value={dm.plant_capacity_mw != null ? `${dm.plant_capacity_mw} MW` : null} />
                        <Cell label="Module Type" value={dm.module_type} />
                        <Cell label="Module Count" value={dm.module_count?.toLocaleString()} />
                        <Cell label="Module Power" value={dm.module_power_wp != null ? `${dm.module_power_wp} Wp` : null} />
                        <Cell label="Modules / String" value={dm.modules_per_string} />
                        <Cell label="Total Strings (doc)" value={dm.total_strings_doc} />
                        <Cell label="Inverters Detected" value={dm.inverter_count_detected} />
                        <Cell label="Tracker" value={dm.tracker_enabled ? `Yes${dm.tracker_rotation_deg != null ? ` (${dm.tracker_rotation_deg}°)` : ''}` : 'No'} />
                        <Cell label="Azimuth" value={dm.azimuth_deg != null ? `${dm.azimuth_deg}°` : null} />
                        <Cell label="System License" value={dm.system_license} />
                      </MetaSection>

                      {/* Storage (only if any storage data) */}
                      {(dm.battery_capacity_mwh != null || dm.battery_type || dm.storage_capacity_mwh != null || dm.bess_inv) && (
                        <MetaSection title="Storage / BESS">
                          <Cell label="Battery Capacity" value={dm.battery_capacity_mwh != null ? `${dm.battery_capacity_mwh} MWh` : null} />
                          <Cell label="Storage Capacity" value={dm.storage_capacity_mwh != null ? `${dm.storage_capacity_mwh} MWh` : null} />
                          <Cell label="Battery Type" value={dm.battery_type} />
                          <Cell label="BESS Inverter" value={dm.bess_inv} />
                        </MetaSection>
                      )}

                      {/* Site dimensions (only if any) */}
                      {(dm.building_area_ha != null || dm.fenced_area_ha != null || dm.fence_length_m != null) && (
                        <MetaSection title="Site Dimensions">
                          <Cell label="Building Area" value={dm.building_area_ha != null ? `${dm.building_area_ha} ha` : null} />
                          <Cell label="Fenced Area" value={dm.fenced_area_ha != null ? `${dm.fenced_area_ha} ha` : null} />
                          <Cell label="Fence Length" value={dm.fence_length_m != null ? `${dm.fence_length_m} m` : null} />
                        </MetaSection>
                      )}

                      {/* Inverter models */}
                      {(dm.inverter_models?.length ?? 0) > 0 && (
                        <div>
                          <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-widest mb-1.5">Inverter Models</p>
                          <div className="bg-white rounded-lg border border-gray-200 px-3 py-2 flex flex-wrap gap-2">
                            {dm.inverter_models!.map((m, i) => (
                              <span key={i} className="px-2 py-0.5 rounded bg-blue-50 text-blue-700 text-xs font-mono border border-blue-100">{m}</span>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Validation findings */}
                      {findings.length > 0 && (
                        <div>
                          <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-widest mb-1.5">
                            Validation Findings ({findings.length})
                          </p>
                          <div className="space-y-1.5">
                            {findings.map((f, i) => (
                              <div key={i} className={`rounded-lg border px-3 py-2 ${severityColor(f.severity)}`}>
                                <div className="flex items-center gap-2 mb-0.5">
                                  <span className="text-[10px] font-bold uppercase">{f.severity}</span>
                                  <span className="text-xs font-mono text-gray-400">{f.risk_code}</span>
                                </div>
                                <p className="text-sm font-medium">{f.title}</p>
                                <p className="text-xs mt-0.5 opacity-80">{f.description}</p>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* MPPT sequence issues */}
                      {(dm.mppt_validation_issues?.length ?? 0) > 0 && (
                        <div>
                          <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-widest mb-1.5">MPPT Sequence Issues</p>
                          <div className="space-y-1">
                            {dm.mppt_validation_issues!.map((m, i) => (
                              <div key={`mx-${i}`} className="text-xs rounded-lg border border-orange-200 bg-orange-50 text-orange-700 px-3 py-1.5">
                                MPPT {m.mppt_no} — {m.issue.replace(/_/g, ' ')}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* All clear */}
                      {findings.length === 0 && (dm.mppt_validation_issues?.length ?? 0) === 0 && (
                        <div className="flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-green-700">
                          <CheckCircle2 className="h-4 w-4 shrink-0" />
                          <span className="text-sm">No validation issues detected in this design file.</span>
                        </div>
                      )}
                    </div>
                  );
                })()}

              </div>
            </section>
          </div>
        )}

        {/* ── Tasks tab ── */}
        {activeTab === 'tasks' && (
          <div className="flex flex-col h-full pt-3 gap-0">
            {tasks.length === 0
              ? <p className="p-6 text-gray-500 text-sm text-center">No tasks for this project.</p>
              : <div className="ag-theme-quartz flex-1 min-h-0 rounded-xl overflow-hidden border border-gray-200">
                  <AgGridReact<MaintenanceTask>
                    rowData={tasks}
                    columnDefs={TASK_COLS}
                    rowHeight={40}
                    headerHeight={36}
                    suppressCellFocus
                  />
                </div>
            }
          </div>
        )}

        {/* ── Measurements tab ── */}
        {activeTab === 'measurements' && (
          <div className="flex flex-col h-full pt-3 gap-3">
            {/* Upload SUI */}
            <div className="shrink-0 bg-white rounded-xl border border-gray-200 p-4">
              <div className="flex items-center justify-between flex-wrap gap-3">
                <div>
                  <h3 className="font-semibold text-gray-800 text-sm">PVPM Measurements</h3>
                  <p className="text-xs text-gray-500 mt-0.5">Upload .SUI files exported from your PVPM analyzer</p>
                </div>
                <button
                  onClick={() => suiInputRef.current?.click()}
                  disabled={suiUploading}
                  className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
                >
                  {suiUploading
                    ? <span className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
                    : <Upload className="h-4 w-4" />}
                  Import .SUI File
                </button>
                <input ref={suiInputRef} type="file" accept=".sui,.SUI,.zip,.ZIP" multiple className="hidden" onChange={handleUploadSui} />
              </div>
            </div>

            {/* Measurements grid */}
            {measurements.length === 0
              ? <p className="p-6 text-gray-500 text-sm text-center">No measurements imported yet.</p>
              : <div className="ag-theme-quartz flex-1 min-h-0 rounded-xl overflow-hidden border border-gray-200">
                  <AgGridReact<Measurement>
                    rowData={measurements}
                    columnDefs={MEAS_COLS}
                    rowHeight={40}
                    headerHeight={36}
                    suppressCellFocus
                  />
                </div>
            }
          </div>
        )}

        {/* ── Testing tab ── */}
        {activeTab === 'testing' && (
          <div className="h-full overflow-y-auto pt-3">
            <ProjectTesting projectId={Number(projectId)} />
          </div>
        )}

        {/* ── Validation tab ── */}
        {activeTab === 'validation' && (
          <div className="h-full overflow-y-auto pt-3">
            <div className="space-y-4">
              {!validation ? (
                <div className="bg-white rounded-lg shadow-sm p-8 text-center">
                  <Shield className="h-12 w-12 text-gray-300 mx-auto mb-3" />
                  <p className="text-gray-500 text-sm mb-4">No validation has been run yet.</p>
                  <button
                    onClick={handleValidateDesign}
                    className="px-4 py-2 bg-amber-500 text-white rounded-lg hover:bg-amber-600 text-sm font-medium"
                  >
                    Run Design Validation
                  </button>
                </div>
              ) : (
                <>
                  <div className={`rounded-xl border-2 p-5 ${
                    validation.status === 'pass'
                      ? 'border-green-200 bg-green-50'
                      : validation.status === 'warning'
                      ? 'border-yellow-200 bg-yellow-50'
                      : 'border-red-200 bg-red-50'
                  }`}>
                    <div className="flex items-center justify-between flex-wrap gap-3">
                      <div className="flex items-center gap-3">
                        {validation.status === 'pass' ? (
                          <CheckCircle2 className="h-8 w-8 text-green-600" />
                        ) : validation.status === 'warning' ? (
                          <AlertTriangle className="h-8 w-8 text-yellow-600" />
                        ) : (
                          <XCircle className="h-8 w-8 text-red-600" />
                        )}
                        <div>
                          <p className={`text-lg font-bold uppercase tracking-wide ${
                            validation.status === 'pass' ? 'text-green-700'
                            : validation.status === 'warning' ? 'text-yellow-700'
                            : 'text-red-700'
                          }`}>
                            {validation.status}
                          </p>
                          <p className="text-sm text-gray-600 mt-0.5">
                            {validation.issues.length === 0
                              ? 'No issues found — design looks good.'
                              : `${validation.issues.length} issue${validation.issues.length !== 1 ? 's' : ''} found`}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {validation.issues.length > 0 && (
                          <button
                            onClick={() => setShowValidationResults(v => !v)}
                            className={`inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium border transition-colors ${
                              validation.status === 'warning'
                                ? 'border-yellow-300 bg-white text-yellow-700 hover:bg-yellow-100'
                                : 'border-red-300 bg-white text-red-700 hover:bg-red-100'
                            }`}
                          >
                            {showValidationResults
                              ? <><ChevronUp className="h-4 w-4" /> Hide Results</>
                              : <><ChevronDown className="h-4 w-4" /> Show Results</>}
                          </button>
                        )}
                        <button
                          onClick={handleValidateDesign}
                          className="inline-flex items-center gap-1.5 px-4 py-2 bg-amber-500 text-white rounded-lg hover:bg-amber-600 text-sm font-medium"
                        >
                          <Shield className="h-4 w-4" /> Re-run
                        </button>
                      </div>
                    </div>
                  </div>

                  {showValidationResults && validation.issues.length > 0 && (
                    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                      <div className="px-5 py-3 border-b border-gray-100 bg-gray-50">
                        <h3 className="font-semibold text-gray-800 text-sm">
                          Validation Issues ({validation.issues.length})
                        </h3>
                      </div>
                      <div className="divide-y divide-gray-100">
                        {validation.issues.map((issue, i) => (
                          <div key={i} className="px-5 py-4 flex items-start gap-4">
                            <div className="mt-0.5">
                              {issue.severity === 'error'
                                ? <XCircle className="h-5 w-5 text-red-500 shrink-0" />
                                : <AlertTriangle className="h-5 w-5 text-yellow-500 shrink-0" />}
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 flex-wrap mb-1">
                                <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${
                                  issue.severity === 'error'
                                    ? 'bg-red-100 text-red-700'
                                    : 'bg-yellow-100 text-yellow-700'
                                }`}>
                                  {issue.severity}
                                </span>
                                <span className="text-xs text-gray-400 font-mono">{issue.issue_type}</span>
                                {issue.asset_type && (
                                  <span className="text-xs text-blue-600 font-medium">
                                    {issue.asset_type}{issue.asset_ref ? ` · ${issue.asset_ref}` : ''}
                                  </span>
                                )}
                              </div>
                              <p className="text-sm text-gray-800">{issue.message}</p>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        )}

      </div>
    </div>

    <StringPatternBusyModal
      open={patternBusy && !parsePatternModalOpen && !scanModalOpen}
      projectName={project?.name ?? `Project ${projectId}`}
      fileCount={patternBusyFileCount}
    />

    <ParsePatternSelectModal
      open={parsePatternModalOpen}
      projectId={Number(projectId)}
      defaultPatternName={project?.string_pattern ?? null}
      onCancel={() => {
        setParsePatternModalOpen(false);
        setPendingScanIds([]);
      }}
      onStartAuto={async () => {
        const ids = [...pendingScanIds];
        setParsePatternModalOpen(false);
        setPatternBusy(true);
        setError(null);
        try {
          const detection = await api.detectStringPattern(Number(projectId), ids);
          const name = detection.selected_pattern_name ?? detection.detected_pattern_name;
          const pat =
            detection.patterns.find((p) => p.pattern_name === name) ?? detection.patterns[0];
          if (!pat) {
            setError('No string pattern could be determined from the files.');
            return;
          }
          _runScan(
            ids,
            { pattern_name: pat.pattern_name, pattern_regex: pat.pattern_regex },
            detection.detect_token ?? null,
          );
        } catch (err: any) {
          setError(err?.response?.data?.detail || err?.message || 'Could not detect a string pattern.');
        } finally {
          setPatternBusy(false);
          setPendingScanIds([]);
        }
      }}
      onStartManual={(pattern) => {
        const ids = [...pendingScanIds];
        setParsePatternModalOpen(false);
        _runScan(ids, pattern, null);
        setPendingScanIds([]);
      }}
    />

    {/* ── Re-parse confirmation modal ── */}
    {confirmScanOpen && (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
        <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm mx-4 overflow-hidden">
          <div className="px-6 py-5">
            <div className="flex items-start gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-amber-100 flex items-center justify-center shrink-0">
                <svg className="w-5 h-5 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                </svg>
              </div>
              <div>
                <h3 className="font-semibold text-gray-900">Replace existing data?</h3>
                <p className="text-sm text-gray-500 mt-1">
                  This project already has{' '}
                  <span className="font-medium text-gray-700">{topologyInverters.length} inverters</span> and{' '}
                  <span className="font-medium text-gray-700">{designStrings.length} strings</span> from a previous parse.
                  Proceeding will delete all existing topology data and replace it with the new file.
                </p>
              </div>
            </div>
          </div>
          <div className="px-6 pb-5 flex justify-end gap-2">
            <button
              onClick={() => { setConfirmScanOpen(false); setPendingScanIds([]); }}
              className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              onClick={() => {
                setConfirmScanOpen(false);
                openParsePatternChoice(pendingScanIds);
              }}
              className="px-4 py-2 text-sm font-medium bg-amber-600 text-white rounded-lg hover:bg-amber-700"
            >
              Yes, replace data
            </button>
          </div>
        </div>
      </div>
    )}

    {/* ── Scan progress modal ── */}
    {scanModalOpen && (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
        <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">
          <div className="bg-gradient-to-r from-blue-600 to-indigo-600 px-6 py-4">
            <h2 className="text-white font-semibold text-base">Processing Design File</h2>
            <p className="text-blue-100 text-xs mt-0.5">Extracting and syncing project data…</p>
          </div>

          <div className="px-6 py-5 space-y-3">
            {scanSteps.map((step, i) => (
              <div key={i} className="flex items-center gap-3">
                <div className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 text-xs font-bold transition-colors ${
                  step.state === 'done'    ? 'bg-green-100 text-green-600' :
                  step.state === 'running' ? 'bg-blue-100 text-blue-600'  :
                  step.state === 'error'   ? 'bg-red-100 text-red-500'    :
                  'bg-gray-100 text-gray-400'
                }`}>
                  {step.state === 'done'    ? '✓' :
                   step.state === 'error'   ? '✕' :
                   step.state === 'running' ? (
                     <span className="block w-3.5 h-3.5 rounded-full border-2 border-blue-500 border-t-transparent animate-spin" />
                   ) : String(i + 1)}
                </div>
                <span className={`text-sm flex-1 ${
                  step.state === 'running' ? 'text-blue-700 font-medium' :
                  step.state === 'done'    ? 'text-green-700'            :
                  step.state === 'error'   ? 'text-red-600 font-medium'  :
                  'text-gray-400'
                }`}>
                  {step.label}
                </span>
              </div>
            ))}
          </div>

          <div className="px-6 pb-2">
            {scanSubLabel && (
              <p className="text-xs text-blue-500 mb-1.5 animate-pulse">{scanSubLabel}</p>
            )}
            <div className="w-full bg-gray-100 rounded-full h-2">
              <div className="h-2 rounded-full transition-all duration-300 bg-blue-500" style={{ width: `${scanPct}%` }} />
            </div>
            <p className="text-right text-xs text-gray-400 mt-1">{scanPct}%</p>
          </div>

          {(scanSummary || scanError) && (
            <div className={`mx-6 mb-4 rounded-lg px-4 py-2.5 text-sm ${
              scanError
                ? 'bg-red-50 border border-red-200 text-red-700'
                : 'bg-green-50 border border-green-200 text-green-700'
            }`}>
              {scanError ?? scanSummary}
            </div>
          )}

          <div className="px-6 pb-5 flex justify-end">
            {!scanBusy && (
              <button
                onClick={() => setScanModalOpen(false)}
                className="px-5 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors"
              >
                {scanError ? 'Close' : 'Done'}
              </button>
            )}
          </div>
        </div>
      </div>
    )}
    </>
  );
}
