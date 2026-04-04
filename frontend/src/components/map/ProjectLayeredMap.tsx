import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { AlertTriangle, BatteryCharging, Cable, CheckCircle2, Layers3, MapPinned, Package, Route, ShieldCheck } from 'lucide-react';
import * as api from '../../lib/api';
import type { ProjectMapWorkspace, ProjectMapObject, ProjectMapLayer } from '../../lib/api';

interface Props {
  projectId: number;
}

function layerColor(layer: ProjectMapLayer): string {
  const fallback: Record<string, string> = {
    topology: '#1d4ed8',
    structural: '#334155',
    electrical: '#7c3aed',
    storage: '#059669',
    workflow: '#f59e0b',
    qa: '#ef4444',
  };
  return (layer.style_json as any)?.fill || (layer.style_json as any)?.stroke || fallback[layer.layer_type] || '#64748b';
}

function objectStroke(obj: ProjectMapObject): string {
  if (obj.object_type === 'workflow_item') return '#f59e0b';
  if (obj.object_type === 'qc_group') return '#ef4444';
  if (obj.object_type === 'storage_unit') return '#059669';
  if (obj.object_type === 'electrical_node') return '#7c3aed';
  if (obj.object_type.includes('row')) return '#475569';
  return '#2563eb';
}

function ObjectShape({ object, selected, onSelect }: { object: ProjectMapObject; selected: boolean; onSelect: () => void }) {
  const g = object.geometry || {};
  const stroke = selected ? '#111827' : objectStroke(object);
  const common = {
    onClick: onSelect,
    style: { cursor: 'pointer' },
  } as const;

  if (object.geometry_type === 'polygon') {
    return (
      <g {...common}>
        <rect x={g.x ?? 0} y={g.y ?? 0} width={g.width ?? 120} height={g.height ?? 60} rx={10} fill={selected ? 'rgba(17,24,39,0.08)' : 'rgba(37,99,235,0.08)'} stroke={stroke} strokeWidth={selected ? 2.5 : 1.4} />
        {object.label ? <text x={(g.x ?? 0) + 10} y={(g.y ?? 0) + 20} fontSize="12" fill="#0f172a">{object.label}</text> : null}
      </g>
    );
  }
  if (object.geometry_type === 'line') {
    return (
      <g {...common}>
        <line x1={g.x1 ?? 0} y1={g.y1 ?? 0} x2={g.x2 ?? 100} y2={g.y2 ?? 0} stroke={stroke} strokeWidth={selected ? 3 : 1.8} strokeDasharray={selected ? '0' : '6 3'} />
        {object.label ? <text x={(g.x1 ?? 0) + 4} y={(g.y1 ?? 0) - 4} fontSize="11" fill="#334155">{object.label}</text> : null}
      </g>
    );
  }
  const cx = g.cx ?? 0;
  const cy = g.cy ?? 0;
  return (
    <g {...common}>
      <circle cx={cx} cy={cy} r={selected ? 8 : 6} fill={stroke} opacity={0.9} />
      {object.label ? <text x={cx + 10} y={cy + 4} fontSize="11" fill="#0f172a">{object.label}</text> : null}
    </g>
  );
}

function MetricCard({ icon, label, value }: { icon: ReactNode; label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
      <div className="mb-2 flex items-center gap-2 text-slate-500">{icon}<span className="text-xs font-medium uppercase tracking-wide">{label}</span></div>
      <div className="text-xl font-semibold text-slate-900">{value}</div>
    </div>
  );
}

export default function ProjectLayeredMap({ projectId }: Props) {
  const [workspace, setWorkspace] = useState<ProjectMapWorkspace | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [visibleLayers, setVisibleLayers] = useState<Record<number, boolean>>({});

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    api.getProjectMapWorkspace(projectId)
      .then((data) => {
        if (!mounted) return;
        setWorkspace(data);
        const next: Record<number, boolean> = {};
        data.layers.forEach((layer) => {
          next[layer.id] = layer.is_visible_default !== false;
        });
        setVisibleLayers(next);
        setSelectedId(data.objects[0]?.id ?? null);
      })
      .catch((err) => {
        if (!mounted) return;
        setError(err?.response?.data?.detail || err?.message || 'Failed to load map workspace');
      })
      .finally(() => mounted && setLoading(false));
    return () => { mounted = false; };
  }, [projectId]);

  const selectedObject = useMemo(() => workspace?.objects.find((obj) => obj.id === selectedId) ?? null, [workspace, selectedId]);
  const objectsByLayer = useMemo(() => {
    const grouped: Record<number, ProjectMapObject[]> = {};
    for (const obj of workspace?.objects ?? []) {
      if (!grouped[obj.layer_id ?? -1]) grouped[obj.layer_id ?? -1] = [];
      grouped[obj.layer_id ?? -1].push(obj);
    }
    return grouped;
  }, [workspace]);

  if (loading) {
    return <div className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-500">Loading layered map…</div>;
  }

  if (error || !workspace) {
    return <div className="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-sm text-rose-700">{error || 'Unable to load map workspace.'}</div>;
  }

  return (
    <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50 p-4 shadow-sm">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-slate-900"><Layers3 className="h-5 w-5 text-blue-600" /><h3 className="text-lg font-semibold">Layered project map</h3></div>
          <p className="mt-1 text-sm text-slate-500">Persistent workspace driven by backend map layers and objects. Kendo-ready adapter path, working today with SVG rendering.</p>
        </div>
        <div className="grid min-w-[320px] grid-cols-2 gap-2 md:grid-cols-4">
          <MetricCard icon={<MapPinned className="h-4 w-4" />} label="Topology" value={workspace.topology.replace(/_/g, ' ')} />
          <MetricCard icon={<BatteryCharging className="h-4 w-4" />} label="Energy" value={workspace.energy_system.replace(/_/g, ' ')} />
          <MetricCard icon={<Package className="h-4 w-4" />} label="Objects" value={workspace.metrics.objects ?? workspace.objects.length} />
          <MetricCard icon={<ShieldCheck className="h-4 w-4" />} label="Open tasks" value={workspace.metrics.open_tasks ?? 0} />
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[260px_minmax(0,1fr)_300px]">
        <aside className="rounded-2xl border border-slate-200 bg-white p-3 shadow-sm">
          <div className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">Layers</div>
          <div className="space-y-2">
            {workspace.layers.map((layer) => (
              <label key={layer.id} className="flex items-center justify-between rounded-xl border border-slate-100 px-3 py-2 text-sm">
                <span className="flex items-center gap-2"><span className="inline-block h-2.5 w-2.5 rounded-full" style={{ backgroundColor: layerColor(layer) }} />{layer.name}</span>
                <input type="checkbox" checked={visibleLayers[layer.id] !== false} onChange={(e) => setVisibleLayers((prev) => ({ ...prev, [layer.id]: e.target.checked }))} />
              </label>
            ))}
          </div>
          <div className="mt-4 rounded-xl bg-slate-50 p-3 text-xs text-slate-600">
            <div className="mb-1 font-semibold text-slate-700">Workspace summary</div>
            <div>{workspace.inspector?.summary || 'Map layers linked to project files, workflow, QC, and inventory.'}</div>
          </div>
        </aside>

        <section className="rounded-2xl border border-slate-200 bg-white p-3 shadow-sm">
          <div className="mb-2 flex items-center justify-between">
            <div>
              <div className="text-sm font-semibold text-slate-900">Interactive site canvas</div>
              <div className="text-xs text-slate-500">Click any object to inspect its metadata and linked workflows.</div>
            </div>
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <Route className="h-4 w-4" /> SVG renderer · persistent API
            </div>
          </div>
          <div className="overflow-hidden rounded-2xl border border-slate-200 bg-gradient-to-br from-slate-50 to-slate-100">
            <svg viewBox="0 0 900 620" className="h-[560px] w-full">
              <defs>
                <pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse">
                  <path d="M 24 0 L 0 0 0 24" fill="none" stroke="#e2e8f0" strokeWidth="1" />
                </pattern>
              </defs>
              <rect x="0" y="0" width="900" height="620" fill="url(#grid)" />
              {workspace.layers
                .filter((layer) => visibleLayers[layer.id] !== false)
                .map((layer) => (
                  <g key={layer.id} data-layer={layer.name}>
                    {(objectsByLayer[layer.id] || []).map((obj) => (
                      <ObjectShape key={obj.id} object={obj} selected={obj.id === selectedId} onSelect={() => setSelectedId(obj.id)} />
                    ))}
                  </g>
                ))}
            </svg>
          </div>
        </section>

        <aside className="rounded-2xl border border-slate-200 bg-white p-3 shadow-sm">
          <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-500"><Cable className="h-4 w-4" />Inspector</div>
          {selectedObject ? (
            <div className="space-y-3 text-sm text-slate-700">
              <div>
                <div className="text-lg font-semibold text-slate-900">{selectedObject.label || selectedObject.object_uid}</div>
                <div className="mt-1 text-xs text-slate-500">{selectedObject.object_type} · {selectedObject.subtype || '—'}</div>
              </div>
              <div className="rounded-xl bg-slate-50 p-3">
                <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Geometry</div>
                <pre className="overflow-auto whitespace-pre-wrap text-xs text-slate-700">{JSON.stringify(selectedObject.geometry, null, 2)}</pre>
              </div>
              <div className="rounded-xl bg-slate-50 p-3">
                <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Properties</div>
                <pre className="overflow-auto whitespace-pre-wrap text-xs text-slate-700">{JSON.stringify(selectedObject.properties, null, 2)}</pre>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div className="rounded-xl border border-slate-200 p-3">
                  <div className="mb-1 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-500"><CheckCircle2 className="h-4 w-4 text-emerald-600" />Workflow</div>
                  <div className="text-xs text-slate-600">Linked workflow tasks and installation progress can attach here through map object links.</div>
                </div>
                <div className="rounded-xl border border-slate-200 p-3">
                  <div className="mb-1 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-500"><AlertTriangle className="h-4 w-4 text-amber-500" />QC</div>
                  <div className="text-xs text-slate-600">QC findings can color-code objects and block the next workflow step.</div>
                </div>
              </div>
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-slate-200 p-6 text-sm text-slate-500">Select an object on the map.</div>
          )}
        </aside>
      </div>
    </div>
  );
}
