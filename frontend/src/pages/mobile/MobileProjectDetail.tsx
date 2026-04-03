import { useState, useEffect, useMemo } from 'react';
import { ArrowLeft, Zap, GitBranch, AlertTriangle, ChevronDown, ChevronUp } from 'lucide-react';
import * as api from '../../lib/api';
import type { Project } from '../../lib/types';
import type { ProjectTopologyInverter, ProjectDesignString } from '../../lib/api';

const PHASE_COLORS: Record<string, { bg: string; color: string }> = {
  design:         { bg: '#ede9fe', color: '#7c3aed' },
  validation:     { bg: '#fef3c7', color: '#d97706' },
  implementation: { bg: '#dbeafe', color: '#2563eb' },
  testing:        { bg: '#ffedd5', color: '#ea580c' },
  commissioning:  { bg: '#ccfbf1', color: '#0f766e' },
  maintenance:    { bg: '#dcfce7', color: '#16a34a' },
  closed:         { bg: '#f3f4f6', color: '#6b7280' },
};

const STRING_STATUS_COLORS: Record<string, { bg: string; color: string }> = {
  ok:       { bg: '#dcfce7', color: '#16a34a' },
  warning:  { bg: '#fef3c7', color: '#d97706' },
  fault:    { bg: '#fee2e2', color: '#dc2626' },
  pending:  { bg: '#f3f4f6', color: '#6b7280' },
};

interface Props {
  project: Project;
  onBack: () => void;
}

export default function MobileProjectDetail({ project, onBack }: Props) {
  const [inverters, setInverters] = useState<ProjectTopologyInverter[]>([]);
  const [strings,   setStrings]   = useState<ProjectDesignString[]>([]);
  const [loading,   setLoading]   = useState(true);
  const [error,     setError]     = useState<string | null>(null);
  const [expandedInv, setExpandedInv] = useState<Set<number>>(new Set());

  useEffect(() => {
    Promise.all([
      api.listProjectTopologyInverters(project.id).catch(() => [] as ProjectTopologyInverter[]),
      api.listProjectDesignStrings(project.id).catch(() => [] as ProjectDesignString[]),
    ]).then(([inv, strs]) => {
      setInverters(inv);
      setStrings(strs);
    }).catch(() => setError('Failed to load topology'))
      .finally(() => setLoading(false));
  }, [project.id]);

  // Group strings by inverter_id
  const stringsByInverter = useMemo(() => {
    const map = new Map<number | null, ProjectDesignString[]>();
    for (const s of strings) {
      const key = s.inverter_id ?? null;
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(s);
    }
    return map;
  }, [strings]);

  const toggleInverter = (id: number) => {
    setExpandedInv(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const phase = project.phase ?? 'design';
  const pc = PHASE_COLORS[phase] ?? { bg: '#f3f4f6', color: '#6b7280' };

  return (
    <div className="min-h-screen bg-gray-50 pb-10">
      {/* Header */}
      <div className="bg-blue-600 text-white px-4 pt-12 pb-6">
        <button
          onClick={onBack}
          className="flex items-center gap-2 text-blue-200 text-sm mb-4 active:opacity-70"
          style={{ background:'none', border:'none', padding:0, cursor:'pointer' }}
        >
          <ArrowLeft className="h-4 w-4" /> Back to Projects
        </button>
        <h1 className="text-xl font-bold leading-tight">{project.name}</h1>
        {project.customer_name && (
          <p className="text-blue-200 text-sm mt-0.5">{project.customer_name}</p>
        )}
        <div className="flex items-center gap-2 mt-3">
          <span style={{
            fontSize: 12, fontWeight: 600, padding: '3px 10px', borderRadius: 12,
            background: 'rgba(255,255,255,0.18)', color: '#fff',
          }}>
            {phase}
          </span>
          {project.progress_percent !== undefined && (
            <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.75)' }}>
              {project.progress_percent}% complete
            </span>
          )}
        </div>
      </div>

      <div className="px-4 mt-4 flex flex-col gap-4">

        {/* Project info card */}
        <div className="bg-white rounded-xl shadow-sm p-4">
          <p className="text-xs font-bold text-gray-400 uppercase tracking-wide mb-3">Project Details</p>
          <div className="flex flex-col gap-2">
            {[
              { label: 'Site',     value: project.site_name },
              { label: 'Type',     value: project.project_type },
              { label: 'Phase',    value: <span style={{ ...pc, fontSize:11, fontWeight:600, padding:'2px 8px', borderRadius:8 }}>{phase}</span> },
              { label: 'Progress', value: project.progress_percent !== undefined ? `${project.progress_percent}%` : undefined },
            ].filter(r => r.value !== undefined && r.value !== null && r.value !== '').map(row => (
              <div key={row.label} className="flex items-center justify-between">
                <span className="text-sm text-gray-500">{row.label}</span>
                <span className="text-sm font-medium text-gray-800">{row.value}</span>
              </div>
            ))}
          </div>

          {/* Progress bar */}
          {project.progress_percent !== undefined && (
            <div className="mt-4">
              <div style={{ background:'#e5e7eb', borderRadius:6, height:8 }}>
                <div style={{
                  width: `${Math.min(project.progress_percent, 100)}%`,
                  background: '#2563eb', borderRadius: 6, height: 8,
                  transition: 'width 0.4s ease',
                }} />
              </div>
            </div>
          )}
        </div>

        {/* Inverters & Strings */}
        {loading ? (
          <div className="flex items-center justify-center py-10">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
          </div>
        ) : error ? (
          <div className="bg-white rounded-xl shadow-sm p-4 flex items-center gap-3">
            <AlertTriangle className="h-5 w-5 text-red-400 shrink-0" />
            <p className="text-red-600 text-sm">{error}</p>
          </div>
        ) : inverters.length === 0 && strings.length === 0 ? (
          <div className="bg-white rounded-xl shadow-sm p-6 text-center">
            <Zap className="h-8 w-8 text-gray-300 mx-auto mb-2" />
            <p className="text-gray-400 text-sm">No inverter topology stored yet.</p>
            <p className="text-gray-300 text-xs mt-1">Upload a design file to auto-scan.</p>
          </div>
        ) : (
          <>
            {/* Stats row */}
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-white rounded-xl shadow-sm p-4 flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center">
                  <Zap className="h-5 w-5 text-blue-600" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-gray-900">{inverters.length}</p>
                  <p className="text-xs text-gray-500">Inverters</p>
                </div>
              </div>
              <div className="bg-white rounded-xl shadow-sm p-4 flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-green-50 flex items-center justify-center">
                  <GitBranch className="h-5 w-5 text-green-600" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-gray-900">{strings.length}</p>
                  <p className="text-xs text-gray-500">Strings</p>
                </div>
              </div>
            </div>

            {/* Inverter list with expandable strings */}
            <div className="flex flex-col gap-2">
              <p className="text-xs font-bold text-gray-400 uppercase tracking-wide px-1">Inverters & Strings</p>
              {inverters.map(inv => {
                const invStrings = stringsByInverter.get(inv.id) ?? [];
                const expanded = expandedInv.has(inv.id);
                return (
                  <div key={inv.id} className="bg-white rounded-xl shadow-sm overflow-hidden">
                    <button
                      onClick={() => toggleInverter(inv.id)}
                      className="w-full text-left p-4 active:bg-gray-50 touch-manipulation"
                      style={{ background:'none', border:'none', cursor:'pointer' }}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className="w-9 h-9 rounded-lg bg-blue-50 flex items-center justify-center shrink-0">
                            <Zap className="h-4 w-4 text-blue-600" />
                          </div>
                          <div>
                            <p className="font-semibold text-gray-900 text-sm">{inv.inverter_label}</p>
                            <p className="text-xs text-gray-400">
                              {invStrings.length} string{invStrings.length !== 1 ? 's' : ''}
                              {inv.expected_string_count ? ` / ${inv.expected_string_count} expected` : ''}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          {inv.icb_zone && (
                            <span style={{ fontSize:10, color:'#6b7280', background:'#f3f4f6', padding:'2px 7px', borderRadius:8, fontWeight:600 }}>
                              {inv.icb_zone}
                            </span>
                          )}
                          {expanded
                            ? <ChevronUp className="h-4 w-4 text-gray-400" />
                            : <ChevronDown className="h-4 w-4 text-gray-400" />
                          }
                        </div>
                      </div>
                    </button>

                    {/* Expanded strings */}
                    {expanded && invStrings.length > 0 && (
                      <div style={{ borderTop: '1px solid #f3f4f6', padding:'8px 16px 12px' }}>
                        <div className="flex flex-wrap gap-2">
                          {invStrings.map(s => {
                            const sc = STRING_STATUS_COLORS[s.status] ?? STRING_STATUS_COLORS['pending'];
                            return (
                              <span key={s.id} style={{
                                fontSize: 12, fontWeight: 600,
                                padding: '4px 10px', borderRadius: 8,
                                background: sc.bg, color: sc.color,
                              }}>
                                {s.string_no}
                              </span>
                            );
                          })}
                        </div>
                      </div>
                    )}
                    {expanded && invStrings.length === 0 && (
                      <div style={{ borderTop:'1px solid #f3f4f6', padding:'10px 16px', color:'#9ca3af', fontSize:13 }}>
                        No strings recorded for this inverter.
                      </div>
                    )}
                  </div>
                );
              })}

              {/* Unassigned strings */}
              {(stringsByInverter.get(null) ?? []).length > 0 && (
                <div className="bg-white rounded-xl shadow-sm p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <GitBranch className="h-4 w-4 text-gray-400" />
                    <p className="text-sm font-semibold text-gray-700">Unassigned Strings</p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {(stringsByInverter.get(null) ?? []).map(s => {
                      const sc = STRING_STATUS_COLORS[s.status] ?? STRING_STATUS_COLORS['pending'];
                      return (
                        <span key={s.id} style={{
                          fontSize: 12, fontWeight: 600,
                          padding: '4px 10px', borderRadius: 8,
                          background: sc.bg, color: sc.color,
                        }}>
                          {s.string_no}
                        </span>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
