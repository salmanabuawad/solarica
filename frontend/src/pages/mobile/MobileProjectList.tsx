import { useState, useEffect } from 'react';
import { FolderKanban, ChevronRight, AlertTriangle } from 'lucide-react';
import * as api from '../../lib/api';
import type { Project } from '../../lib/types';

const PHASE_COLORS: Record<string, { bg: string; color: string }> = {
  design:         { bg: '#ede9fe', color: '#7c3aed' },
  validation:     { bg: '#fef3c7', color: '#d97706' },
  implementation: { bg: '#dbeafe', color: '#2563eb' },
  testing:        { bg: '#ffedd5', color: '#ea580c' },
  commissioning:  { bg: '#ccfbf1', color: '#0f766e' },
  maintenance:    { bg: '#dcfce7', color: '#16a34a' },
  closed:         { bg: '#f3f4f6', color: '#6b7280' },
};

interface Props {
  onSelectProject: (project: Project) => void;
}

export default function MobileProjectList({ onSelectProject }: Props) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState<string | null>(null);
  const [search, setSearch]     = useState('');

  useEffect(() => {
    api.listProjects()
      .then(all => setProjects(all.filter(p => p.is_active !== false)))
      .catch(() => setError('Failed to load projects'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-50">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-screen bg-gray-50 px-6">
        <AlertTriangle className="h-12 w-12 text-red-400 mb-3" />
        <p className="text-red-600 text-center">{error}</p>
      </div>
    );
  }

  const filtered = search
    ? projects.filter(p =>
        p.name.toLowerCase().includes(search.toLowerCase()) ||
        p.customer_name?.toLowerCase().includes(search.toLowerCase()) ||
        p.site_name?.toLowerCase().includes(search.toLowerCase())
      )
    : projects;

  return (
    <div className="min-h-screen bg-gray-50 pb-8">
      {/* Header */}
      <div className="bg-blue-600 text-white px-5 pt-12 pb-6">
        <div className="flex items-center gap-3 mb-4">
          <FolderKanban className="h-6 w-6 text-blue-200" />
          <h1 className="text-xl font-bold">Projects</h1>
          <span style={{ marginLeft:'auto', background:'rgba(255,255,255,0.18)', fontSize:12, fontWeight:600, padding:'2px 10px', borderRadius:12 }}>
            {projects.length}
          </span>
        </div>
        <input
          type="text"
          placeholder="Search projects…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={{
            width: '100%', padding: '9px 14px', fontSize: 14,
            borderRadius: 10, border: 'none', outline: 'none',
            background: 'rgba(255,255,255,0.18)', color: '#fff',
            boxSizing: 'border-box',
          }}
        />
      </div>

      {/* Project list */}
      <div className="px-4 mt-4 flex flex-col gap-3">
        {filtered.length === 0 ? (
          <p className="text-center text-gray-400 text-sm mt-10">No projects found.</p>
        ) : (
          filtered.map(p => {
            const phase = p.phase ?? 'design';
            const pc = PHASE_COLORS[phase] ?? { bg: '#f3f4f6', color: '#6b7280' };
            return (
              <button
                key={p.id}
                onClick={() => onSelectProject(p)}
                className="bg-white rounded-xl shadow-sm p-4 text-left active:scale-95 transition-transform touch-manipulation w-full"
                style={{ border: 'none' }}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <p className="font-semibold text-gray-900 text-base truncate">{p.name}</p>
                    {p.customer_name && (
                      <p className="text-sm text-gray-500 truncate mt-0.5">{p.customer_name}</p>
                    )}
                    {p.site_name && (
                      <p className="text-xs text-gray-400 truncate">{p.site_name}</p>
                    )}
                  </div>
                  <div className="flex flex-col items-end gap-2 shrink-0">
                    <span style={{
                      fontSize: 11, fontWeight: 600, padding: '2px 9px', borderRadius: 10,
                      background: pc.bg, color: pc.color,
                    }}>
                      {phase}
                    </span>
                    <ChevronRight className="h-4 w-4 text-gray-300" />
                  </div>
                </div>

                {/* Progress bar */}
                {p.progress_percent !== undefined && (
                  <div className="mt-3">
                    <div style={{ display:'flex', alignItems:'center', gap:8 }}>
                      <div style={{ flex:1, background:'#e5e7eb', borderRadius:4, height:5 }}>
                        <div style={{ width:`${Math.min(p.progress_percent, 100)}%`, background:'#2563eb', borderRadius:4, height:5 }} />
                      </div>
                      <span style={{ fontSize:11, color:'#6b7280', width:30, textAlign:'right' }}>
                        {p.progress_percent}%
                      </span>
                    </div>
                  </div>
                )}
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}
