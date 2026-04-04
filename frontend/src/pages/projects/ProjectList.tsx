import { useState, useEffect, useCallback, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import { AgGridReact } from 'ag-grid-react';
import type { ColDef, ICellRendererParams } from 'ag-grid-community';
import { Plus, RefreshCcw, Download, FolderKanban, Trash2, Loader2 } from 'lucide-react';
import * as api from '../../lib/api';
import type { Project } from '../../lib/types';
import { useTabs, useApp } from '../../contexts/AppContext';
import DataPageShell from '../../components/layout/DataPageShell';
import { useFieldConfig } from '../../lib/useFieldConfig';
import { registerAgGridModules } from '../../lib/agGridModules';


registerAgGridModules();
const PHASE_COLORS: Record<string, { bg: string; color: string }> = {
  design:         { bg: '#ede9fe', color: '#7c3aed' },
  validation:     { bg: '#fef3c7', color: '#d97706' },
  implementation: { bg: '#dbeafe', color: '#2563eb' },
  testing:        { bg: '#ffedd5', color: '#ea580c' },
  commissioning:  { bg: '#ccfbf1', color: '#0f766e' },
  maintenance:    { bg: '#dcfce7', color: '#16a34a' },
  closed:         { bg: '#f3f4f6', color: '#6b7280' },
};

function PhaseBadge({ value }: { value: string }) {
  const c = PHASE_COLORS[value] ?? { bg: '#f3f4f6', color: '#6b7280' };
  return (
    <span style={{ display:'inline-block', padding:'2px 8px', borderRadius:12, fontSize:11, fontWeight:600, background:c.bg, color:c.color }}>
      {value}
    </span>
  );
}

function ProgressBar({ value }: { value: number }) {
  return (
    <div style={{ display:'flex', alignItems:'center', gap:6, width:'100%' }}>
      <div style={{ flex:1, background:'#e5e7eb', borderRadius:4, height:6 }}>
        <div style={{ width:`${Math.min(value,100)}%`, background:'#2563eb', borderRadius:4, height:6 }} />
      </div>
      <span style={{ fontSize:11, color:'#6b7280', width:28, textAlign:'right' }}>{value}%</span>
    </div>
  );
}

function DeleteProjectModal({
  project,
  busy,
  error,
  onClose,
  onConfirm,
}: {
  project: Project;
  busy: boolean;
  error: string | null;
  onClose: () => void;
  onConfirm: () => void;
}) {
  const { t } = useTranslation();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !busy) onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [busy, onClose]);

  const modal = (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-[600] p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="delete-project-title"
      onClick={busy ? undefined : onClose}
    >
      <div
        className="bg-white rounded-2xl shadow-2xl p-6 max-w-md w-full mx-auto border border-gray-200"
        onClick={e => e.stopPropagation()}
      >
        <p id="delete-project-title" className="text-base font-semibold text-gray-800 mb-3">
          {t('projects.delete_confirm', { name: project.name })}
        </p>
        {error && (
          <p className="text-red-600 text-sm mb-4" role="alert">
            {error}
          </p>
        )}
        <div className="flex gap-3 justify-end">
          <button type="button" disabled={busy} onClick={onClose} className="btn btn-cancel btn-md">
            {t('common.cancel')}
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={onConfirm}
            className="btn btn-danger btn-md inline-flex items-center gap-2"
          >
            {busy && <Loader2 className="w-4 h-4 animate-spin" />}
            {t('common.delete')}
          </button>
        </div>
      </div>
    </div>
  );

  return createPortal(modal, document.body);
}

export default function ProjectList() {
  const { t } = useTranslation();
  const { openTab, closeTab } = useTabs();
  const { user } = useApp();
  const canManageProject = user?.role === 'admin' || user?.role === 'manager';
  const canDeleteProject = canManageProject;
  const [projects, setProjects]   = useState<Project[]>([]);
  const [loading, setLoading]     = useState(true);
  const [searchText, setSearchText] = useState('');
  const [pendingDelete, setPendingDelete] = useState<Project | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [busyActiveId, setBusyActiveId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try { setProjects(await api.listProjects()); }
    catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const requestDelete = useCallback((p: Project) => {
    setDeleteError(null);
    setPendingDelete(p);
  }, []);

  const cancelDelete = useCallback(() => {
    if (deleteBusy) return;
    setPendingDelete(null);
    setDeleteError(null);
  }, [deleteBusy]);

  const confirmDelete = useCallback(async () => {
    if (!pendingDelete) return;
    setDeleteBusy(true);
    setDeleteError(null);
    try {
      await api.deleteProject(pendingDelete.id);
      closeTab(`project-${pendingDelete.id}`);
      setPendingDelete(null);
      await load();
    } catch (e) {
      console.error(e);
      setDeleteError(t('projects.delete_failed'));
    } finally {
      setDeleteBusy(false);
    }
  }, [pendingDelete, closeTab, load, t]);

  const setProjectActiveFlag = useCallback(async (p: Project, is_active: boolean) => {
    if (p.is_active === is_active) return;
    setBusyActiveId(p.id);
    try {
      const updated = await api.setProjectActive(p.id, is_active);
      setProjects((prev) => prev.map((x) => (x.id === updated.id ? updated : x)));
    } catch (e) {
      console.error(e);
    } finally {
      setBusyActiveId(null);
    }
  }, []);

  // Configurable data columns (no closures over local state)
  const defaultDataCols = useMemo<ColDef<Project>[]>(() => [
    { field: 'id',               headerName: 'ID',                             width: 70,  maxWidth: 80 },
    { field: 'name',             headerName: t('common.name'),                 flex: 2,    filter: true },
    { field: 'customer_name',    headerName: t('projects.fields.customer'),    flex: 1.5 },
    { field: 'site_name',        headerName: t('projects.fields.site'),        flex: 1.5 },
    { field: 'project_type',     headerName: t('projects.fields.type'),        flex: 1 },
    { field: 'phase',            headerName: t('projects.fields.phase'),       flex: 1,
      cellRenderer: (p: ICellRendererParams) => p.value ? <PhaseBadge value={p.value}/> : null },
    { field: 'progress_percent', headerName: t('projects.fields.progress'),    flex: 1.5,
      cellRenderer: (p: ICellRendererParams) => p.value !== undefined ? <ProgressBar value={p.value}/> : null },
  ], [t]);

  const configuredDataCols = useFieldConfig('projects', defaultDataCols);

  const columnDefs = useMemo<ColDef<Project>[]>(() => {
    const activeCol: ColDef<Project> = {
      colId: 'active',
      headerName: t('projects.fields.active'),
      width: 120,
      maxWidth: 140,
      sortable: true,
      filter: true,
      suppressHeaderMenuButton: true,
      cellRendererParams: {
        suppressMouseEventHandling: () => true,
      },
      cellRenderer: (params: ICellRendererParams<Project>) => {
        if (!params.data) return null;
        const row = params.data;
        const active = row.is_active !== false;
        if (canManageProject) {
          return (
            <label
              className="inline-flex items-center gap-2 cursor-pointer select-none py-0.5"
              onClick={(e) => e.stopPropagation()}
            >
              <input
                type="checkbox"
                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                checked={active}
                disabled={busyActiveId === row.id}
                onChange={(e) => {
                  e.stopPropagation();
                  void setProjectActiveFlag(row, e.target.checked);
                }}
              />
              <span className="text-xs text-gray-600">{active ? t('projects.active_label') : t('projects.inactive_label')}</span>
            </label>
          );
        }
        return (
          <span
            className={`text-xs font-medium px-2 py-0.5 rounded-full ${
              active ? 'bg-emerald-50 text-emerald-800' : 'bg-gray-100 text-gray-600'
            }`}
          >
            {active ? t('projects.active_label') : t('projects.inactive_label')}
          </span>
        );
      },
    };
    const deleteCol: ColDef<Project> = {
      colId: 'delete',
      width: 44,
      maxWidth: 44,
      sortable: false,
      filter: false,
      resizable: false,
      suppressHeaderMenuButton: true,
      headerName: '',
      cellRendererParams: {
        suppressMouseEventHandling: () => true,
      },
      cellRenderer: (params: ICellRendererParams<Project>) => {
        if (!params.data) return null;
        const row = params.data;
        return (
          <button
            type="button"
            title={t('common.delete')}
            className="p-1 rounded-md text-gray-400 hover:text-red-600 hover:bg-red-50 transition-colors"
            onClick={(e) => {
              e.stopPropagation();
              e.preventDefault();
              requestDelete(row);
            }}
            onMouseDown={(e) => e.stopPropagation()}
          >
            <Trash2 className="w-4 h-4" strokeWidth={2} />
          </button>
        );
      },
    };
    return [
      ...(canDeleteProject ? [deleteCol] : []),
      activeCol,
      ...configuredDataCols,
    ];
  }, [requestDelete, canDeleteProject, canManageProject, busyActiveId, setProjectActiveFlag, configuredDataCols]);

  const filtered = useMemo(() => {
    if (!searchText) return projects;
    const q = searchText.toLowerCase();
    return projects.filter(p =>
      p.name.toLowerCase().includes(q) ||
      (p.customer_name?.toLowerCase().includes(q)) ||
      p.site_name.toLowerCase().includes(q)
    );
  }, [projects, searchText]);

  const actions = [
    { icon: <Plus size={18}/>,        label: t('projects.create'), variant: 'primary' as const,
      onClick: () => openTab({ id:'new-project', type:'project-wizard', label: t('projects.create') }) },
    { icon: <RefreshCcw size={18}/>,  label: t('common.refresh'),  onClick: load },
    { icon: <Download size={18}/>,    label: t('common.export'),
      onClick: () => {} },
  ];

  return (
    <>
      <DataPageShell
        title={t('projects.list_title')}
        icon={<FolderKanban size={17}/>}
        count={projects.length}
        actions={actions}
        searchValue={searchText}
        searchPlaceholder={t('common.search') + '...'}
        onSearchChange={setSearchText}
      >
        {loading ? (
          <div style={{ display:'flex', alignItems:'center', justifyContent:'center', height:200 }}>
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"/>
          </div>
        ) : (
          <div className="ag-theme-quartz" style={{ height:'100%', width:'100%' }}>
            <AgGridReact<Project>
              rowData={filtered}
              columnDefs={columnDefs}
              onRowClicked={(p) => {
                const ev = p.event;
                if (ev?.target instanceof Element) {
                  if (ev.target.closest('button, [role="button"], label, input, .ag-selection-checkbox, input.ag-input-field-input')) return;
                }
                if (p.data) {
                  openTab({ id: `project-${p.data.id}`, type: 'project', label: p.data.name, projectId: String(p.data.id) });
                }
              }}
              rowSelection={{ mode: 'multiRow', checkboxes: true, headerCheckbox: true }}
              animateRows
              pagination
              paginationPageSize={20}
              paginationPageSizeSelector={[20, 50, 100]}
              getRowStyle={(params) =>
                params.data && params.data.is_active === false
                  ? { backgroundColor: 'rgb(249 250 251)' }
                  : undefined
              }
            />
          </div>
        )}
      </DataPageShell>

      {pendingDelete && (
        <DeleteProjectModal
          project={pendingDelete}
          busy={deleteBusy}
          error={deleteError}
          onClose={cancelDelete}
          onConfirm={() => void confirmDelete()}
        />
      )}
    </>
  );
}
