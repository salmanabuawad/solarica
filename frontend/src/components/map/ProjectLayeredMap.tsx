import { useEffect, useMemo, useState, type ReactNode } from 'react';
import {
  AlertTriangle,
  BatteryCharging,
  Cable,
  CheckCircle2,
  Crosshair,
  Layers3,
  MapPinned,
  Move,
  Package,
  Pencil,
  PlusCircle,
  RefreshCw,
  Route,
  Save,
  ShieldCheck,
  Square,
} from 'lucide-react';
import * as api from '../../lib/api';
import type { ProjectMapWorkspace, ProjectMapObject, ProjectMapLayer } from '../../lib/api';

interface Props {
  projectId: number;
}

type EditMode = 'select' | 'move' | 'create-point' | 'create-box';

function layerColor(layer: ProjectMapLayer): string {
  const fallback: Record<string, string> = {
    topology: '#1d4ed8',
    structural: '#334155',
    electrical: '#7c3aed',
    storage: '#059669',
    workflow: '#f59e0b',
    qa: '#ef4444',
  };
  return (layer.style_json as Record<string, string> | undefined)?.fill || (layer.style_json as Record<string, string> | undefined)?.stroke || fallback[layer.layer_type] || '#64748b';
}

function objectStroke(obj: ProjectMapObject): string {
  if (obj.object_type === 'workflow_item') return '#f59e0b';
  if (obj.object_type === 'qc_group') return '#ef4444';
  if (obj.object_type === 'storage_unit') return '#059669';
  if (obj.object_type === 'electrical_node') return '#7c3aed';
  if (obj.object_type.includes('row')) return '#475569';
  return '#2563eb';
}

function MetricCard({ icon, label, value }: { icon: ReactNode; label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
      <div className="mb-2 flex items-center gap-2 text-slate-500">{icon}<span className="text-xs font-medium uppercase tracking-wide">{label}</span></div>
      <div className="text-xl font-semibold text-slate-900">{value}</div>
    </div>
  );
}

function ObjectShape({ object, selected, onSelect }: { object: ProjectMapObject; selected: boolean; onSelect: () => void }) {
  const g = object.geometry || {};
  const stroke = selected ? '#111827' : objectStroke(object);
  const common = {
    onClick: (e: React.MouseEvent) => {
      e.stopPropagation();
      onSelect();
    },
    style: { cursor: 'pointer' },
  } as const;

  if (object.geometry_type === 'polygon') {
    return (
      <g {...common}>
        <rect x={Number(g.x ?? 0)} y={Number(g.y ?? 0)} width={Number(g.width ?? 120)} height={Number(g.height ?? 60)} rx={10} fill={selected ? 'rgba(17,24,39,0.08)' : 'rgba(37,99,235,0.08)'} stroke={stroke} strokeWidth={selected ? 2.5 : 1.4} />
        {object.label ? <text x={Number(g.x ?? 0) + 10} y={Number(g.y ?? 0) + 20} fontSize="12" fill="#0f172a">{object.label}</text> : null}
      </g>
    );
  }
  if (object.geometry_type === 'line') {
    return (
      <g {...common}>
        <line x1={Number(g.x1 ?? 0)} y1={Number(g.y1 ?? 0)} x2={Number(g.x2 ?? 100)} y2={Number(g.y2 ?? 0)} stroke={stroke} strokeWidth={selected ? 3 : 1.8} strokeDasharray={selected ? '0' : '6 3'} />
        {object.label ? <text x={Number(g.x1 ?? 0) + 4} y={Number(g.y1 ?? 0) - 4} fontSize="11" fill="#334155">{object.label}</text> : null}
      </g>
    );
  }
  const cx = Number(g.cx ?? 0);
  const cy = Number(g.cy ?? 0);
  return (
    <g {...common}>
      <circle cx={cx} cy={cy} r={selected ? 8 : 6} fill={stroke} opacity={0.9} />
      {object.label ? <text x={cx + 10} y={cy + 4} fontSize="11" fill="#0f172a">{object.label}</text> : null}
    </g>
  );
}

function toNumber(value: unknown, fallback = 0): number {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function moveGeometry(geometryType: string, geometry: Record<string, unknown>, dx: number, dy: number): Record<string, unknown> {
  const g = { ...geometry };
  if (geometryType === 'polygon') {
    return { ...g, x: toNumber(g.x) + dx, y: toNumber(g.y) + dy };
  }
  if (geometryType === 'line') {
    return {
      ...g,
      x1: toNumber(g.x1) + dx,
      y1: toNumber(g.y1) + dy,
      x2: toNumber(g.x2) + dx,
      y2: toNumber(g.y2) + dy,
    };
  }
  return { ...g, cx: toNumber(g.cx) + dx, cy: toNumber(g.cy) + dy };
}

export default function ProjectLayeredMap({ projectId }: Props) {
  const [workspace, setWorkspace] = useState<ProjectMapWorkspace | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [visibleLayers, setVisibleLayers] = useState<Record<number, boolean>>({});
  const [editMode, setEditMode] = useState<EditMode>('select');
  const [selectedLayerId, setSelectedLayerId] = useState<number | null>(null);
  const [draftLabel, setDraftLabel] = useState('');
  const [dirtyGeometry, setDirtyGeometry] = useState<Record<string, unknown> | null>(null);

  const loadWorkspace = async (bootstrap = false) => {
    setLoading(true);
    setError(null);
    try {
      const data = bootstrap
        ? await api.bootstrapProjectMapWorkspace(projectId, true)
        : await api.getProjectMapWorkspace(projectId);
      setWorkspace(data);
      const next: Record<number, boolean> = {};
      data.layers.forEach((layer) => {
        next[layer.id] = layer.is_visible_default !== false;
      });
      setVisibleLayers(next);
      const firstLayer = data.layers[0]?.id ?? null;
      const firstObject = data.objects[0]?.id ?? null;
      setSelectedLayerId(firstLayer);
      setSelectedId(firstObject);
      const selected = data.objects.find((obj) => obj.id === firstObject);
      setDraftLabel(selected?.label || '');
      setDirtyGeometry(selected?.geometry || null);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to load map workspace');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadWorkspace(false);
  }, [projectId]);

  const selectedObject = useMemo(() => workspace?.objects.find((obj) => obj.id === selectedId) ?? null, [workspace, selectedId]);

  useEffect(() => {
    setDraftLabel(selectedObject?.label || '');
    setDirtyGeometry(selectedObject?.geometry || null);
    if (selectedObject?.layer_id) setSelectedLayerId(selectedObject.layer_id);
  }, [selectedObject?.id]);

  const objectsByLayer = useMemo(() => {
    const grouped: Record<number, ProjectMapObject[]> = {};
    for (const obj of workspace?.objects ?? []) {
      if (!grouped[obj.layer_id ?? -1]) grouped[obj.layer_id ?? -1] = [];
      grouped[obj.layer_id ?? -1].push(obj);
    }
    return grouped;
  }, [workspace]);

  const updateLocalObject = (objectId: number, patch: Partial<ProjectMapObject>) => {
    setWorkspace((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        objects: prev.objects.map((obj) => (obj.id === objectId ? { ...obj, ...patch } : obj)),
      };
    });
  };

  const saveSelectedObject = async () => {
    if (!selectedObject) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await api.updateProjectMapObject(selectedObject.id, {
        label: draftLabel,
        geometry: dirtyGeometry || selectedObject.geometry,
      });
      updateLocalObject(selectedObject.id, updated);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to save map object');
    } finally {
      setSaving(false);
    }
  };

  const nudgeSelectedObject = (dx: number, dy: number) => {
    if (!selectedObject) return;
    const nextGeometry = moveGeometry(selectedObject.geometry_type, dirtyGeometry || selectedObject.geometry, dx, dy);
    setDirtyGeometry(nextGeometry);
    updateLocalObject(selectedObject.id, { geometry: nextGeometry });
  };

  const handleCanvasClick = async (event: React.MouseEvent<SVGSVGElement>) => {
    if (!workspace || editMode === 'select' || editMode === 'move') return;
    const svg = event.currentTarget;
    const rect = svg.getBoundingClientRect();
    const x = ((event.clientX - rect.left) / rect.width) * 900;
    const y = ((event.clientY - rect.top) / rect.height) * 620;
    const fallbackLayer = workspace.layers.find((layer) => layer.name === 'assets')?.id ?? workspace.layers[0]?.id ?? null;
    const layerId = selectedLayerId ?? fallbackLayer;
    if (!layerId) return;

    const defaultLabel = editMode === 'create-box' ? `New area ${Date.now().toString().slice(-4)}` : `New point ${Date.now().toString().slice(-4)}`;
    const payload = {
      layer_id: layerId,
      object_uid: `manual-${Date.now()}`,
      object_type: editMode === 'create-box' ? 'manual_area' : 'manual_point',
      subtype: 'manual',
      label: defaultLabel,
      geometry_type: editMode === 'create-box' ? 'polygon' : 'point',
      geometry: editMode === 'create-box'
        ? { x: Math.max(0, x - 45), y: Math.max(0, y - 25), width: 90, height: 50 }
        : { cx: x, cy: y },
      properties: { created_from_ui: true },
    };

    setSaving(true);
    setError(null);
    try {
      const created = await api.createProjectMapObject(projectId, payload);
      setWorkspace((prev) => (prev ? { ...prev, objects: [...prev.objects, created], metrics: { ...prev.metrics, objects: (prev.metrics.objects || prev.objects.length) + 1 } } : prev));
      setSelectedId(created.id);
      setDraftLabel(created.label || '');
      setDirtyGeometry(created.geometry);
      setEditMode('select');
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to create map object');
    } finally {
      setSaving(false);
    }
  };

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
          <p className="mt-1 text-sm text-slate-500">Persistent workspace driven by backend map layers and objects. Kendo-ready adapter path, working today with SVG rendering and live editing.</p>
        </div>
        <div className="grid min-w-[320px] grid-cols-2 gap-2 md:grid-cols-4">
          <MetricCard icon={<MapPinned className="h-4 w-4" />} label="Topology" value={workspace.topology.replace(/_/g, ' ')} />
          <MetricCard icon={<BatteryCharging className="h-4 w-4" />} label="Energy" value={workspace.energy_system.replace(/_/g, ' ')} />
          <MetricCard icon={<Package className="h-4 w-4" />} label="Objects" value={workspace.metrics.objects ?? workspace.objects.length} />
          <MetricCard icon={<ShieldCheck className="h-4 w-4" />} label="Open tasks" value={workspace.metrics.open_tasks ?? 0} />
        </div>
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-2 rounded-2xl border border-slate-200 bg-white p-3 shadow-sm">
        <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Edit mode</span>
        {[
          { key: 'select', label: 'Select', icon: <Pencil className="h-4 w-4" /> },
          { key: 'move', label: 'Move', icon: <Move className="h-4 w-4" /> },
          { key: 'create-point', label: 'Add point', icon: <PlusCircle className="h-4 w-4" /> },
          { key: 'create-box', label: 'Add box', icon: <Square className="h-4 w-4" /> },
        ].map((mode) => (
          <button
            key={mode.key}
            type="button"
            onClick={() => setEditMode(mode.key as EditMode)}
            className={`inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm ${editMode === mode.key ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-700 hover:bg-slate-200'}`}
          >
            {mode.icon}
            {mode.label}
          </button>
        ))}
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <select
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
            value={selectedLayerId ?? ''}
            onChange={(e) => setSelectedLayerId(e.target.value ? Number(e.target.value) : null)}
          >
            {workspace.layers.map((layer) => (
              <option key={layer.id} value={layer.id}>{layer.name}</option>
            ))}
          </select>
          <button
            type="button"
            onClick={saveSelectedObject}
            disabled={!selectedObject || saving}
            className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-3 py-2 text-sm text-white disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Save className="h-4 w-4" />
            {saving ? 'Saving…' : 'Save object'}
          </button>
          <button
            type="button"
            onClick={() => void loadWorkspace(true)}
            className="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-3 py-2 text-sm text-white"
          >
            <RefreshCw className="h-4 w-4" />
            Rebuild workspace
          </button>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[260px_minmax(0,1fr)_320px]">
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
              <div className="text-xs text-slate-500">Click any object to inspect. In create mode, click on the canvas to add new objects.</div>
            </div>
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <Route className="h-4 w-4" /> SVG renderer · persistent API
            </div>
          </div>
          <div className="overflow-hidden rounded-2xl border border-slate-200 bg-gradient-to-br from-slate-50 to-slate-100">
            <svg viewBox="0 0 900 620" className="h-[560px] w-full" onClick={handleCanvasClick}>
              <defs>
                <pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse">
                  <path d="M 24 0 L 0 0 0 24" fill="none" stroke="#e2e8f0" strokeWidth="1" />
                </pattern>
              </defs>
              <rect x="0" y="0" width="900" height="620" fill="url(#grid)" />
              {editMode !== 'select' ? (
                <text x="18" y="24" fontSize="12" fill="#475569">
                  {editMode === 'move' ? 'Move mode: use nudge controls in the inspector.' : 'Create mode: click anywhere on the canvas.'}
                </text>
              ) : null}
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

              <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500">
                Label
                <input
                  value={draftLabel}
                  onChange={(e) => {
                    setDraftLabel(e.target.value);
                    updateLocalObject(selectedObject.id, { label: e.target.value });
                  }}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900"
                />
              </label>

              <div className="rounded-xl bg-slate-50 p-3">
                <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-500"><Crosshair className="h-4 w-4" />Move / adjust</div>
                <div className="grid grid-cols-3 gap-2 text-center">
                  <div />
                  <button type="button" onClick={() => nudgeSelectedObject(0, -6)} className="rounded-lg bg-slate-200 px-3 py-2 text-sm">↑</button>
                  <div />
                  <button type="button" onClick={() => nudgeSelectedObject(-6, 0)} className="rounded-lg bg-slate-200 px-3 py-2 text-sm">←</button>
                  <button type="button" onClick={() => nudgeSelectedObject(0, 0)} className="rounded-lg bg-slate-100 px-3 py-2 text-xs text-slate-500">nudge</button>
                  <button type="button" onClick={() => nudgeSelectedObject(6, 0)} className="rounded-lg bg-slate-200 px-3 py-2 text-sm">→</button>
                  <div />
                  <button type="button" onClick={() => nudgeSelectedObject(0, 6)} className="rounded-lg bg-slate-200 px-3 py-2 text-sm">↓</button>
                  <div />
                </div>
              </div>

              <div className="rounded-xl bg-slate-50 p-3">
                <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Geometry</div>
                <pre className="overflow-auto whitespace-pre-wrap text-xs text-slate-700">{JSON.stringify(dirtyGeometry || selectedObject.geometry, null, 2)}</pre>
              </div>

              <div className="rounded-xl bg-slate-50 p-3">
                <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Properties</div>
                <pre className="overflow-auto whitespace-pre-wrap text-xs text-slate-700">{JSON.stringify(selectedObject.properties, null, 2)}</pre>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div className="rounded-xl border border-slate-200 p-3">
                  <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Source</div>
                  <div className="text-xs text-slate-700">{selectedObject.source_ref || 'manual / persistent map object'}</div>
                </div>
                <div className="rounded-xl border border-slate-200 p-3">
                  <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Layer</div>
                  <div className="text-xs text-slate-700">{workspace.layers.find((layer) => layer.id === selectedObject.layer_id)?.name || '—'}</div>
                </div>
              </div>

              <div className="rounded-xl border border-slate-200 bg-amber-50 p-3 text-xs text-amber-800">
                <div className="mb-1 flex items-center gap-2 font-semibold"><AlertTriangle className="h-4 w-4" />Operational note</div>
                Save commits the current label and geometry to the backend map tables. Rebuild workspace re-generates inferred layers from project data.
              </div>
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-slate-300 p-6 text-sm text-slate-500">Select an object to inspect and edit its metadata.</div>
          )}

          <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
            <div className="rounded-xl border border-slate-200 p-3">
              <div className="mb-1 flex items-center gap-2 font-semibold text-slate-700"><CheckCircle2 className="h-4 w-4 text-emerald-600" />Files</div>
              <div className="text-slate-500">{workspace.inspector?.source_files?.slice(0, 2).join(', ') || 'No linked files'}</div>
            </div>
            <div className="rounded-xl border border-slate-200 p-3">
              <div className="mb-1 flex items-center gap-2 font-semibold text-slate-700"><ShieldCheck className="h-4 w-4 text-rose-600" />QC</div>
              <div className="text-slate-500">{workspace.metrics.validation_issues ?? 0} open issues</div>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
