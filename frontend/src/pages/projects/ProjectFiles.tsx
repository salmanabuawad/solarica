/**
 * ProjectFiles — upload, list, replace, toggle active/inactive, delete.
 * File list rendered with AgGrid; component fills its parent height.
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import {
  FileText, UploadCloud, Trash2, Download,
  AlertCircle, X, Eye, EyeOff, RefreshCw, Check, ScanLine,
} from 'lucide-react';
import axios from 'axios';
import { AgGridReact } from 'ag-grid-react';
import type { ColDef, GetRowIdParams, RowClassParams } from 'ag-grid-community';
import { registerAgGridModules } from '../../lib/agGridModules';

registerAgGridModules();
interface ProjectFile {
  id:            string;
  original_name: string;
  file_type:     'PDF' | 'DXF';
  size_bytes:    number;
  uploaded_at:   string;
  is_active:     boolean;
}

interface Props {
  projectId: number;
  /** Called after any file list change (upload / replace / toggle / delete). No scan triggered. */
  onFilesUpdated?: () => void;
  /** Called when the user clicks "Parse Data". Receives active file IDs to scan. */
  onParseFiles?: (activeFileIds: string[]) => void;
}

interface ActionsCtx {
  confirmDeleteId:    string | null;
  setConfirmDeleteId: (id: string | null) => void;
  replacingId:        string | null;
  startReplace:       (id: string) => void;
  handleDelete:       (id: string) => Promise<void>;
  handleToggleActive: (file: ProjectFile) => Promise<void>;
  projectId:          number;
}

const API      = '/api/projects';
const ACCEPTED = '.pdf,.dxf';

function fmtSize(bytes: number): string {
  if (bytes < 1024)          return `${bytes} B`;
  if (bytes < 1024 * 1024)   return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function fmtDate(iso: string): string {
  try { return new Date(iso).toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' }); }
  catch { return iso; }
}

/* ── Cell renderers (defined outside component to stay stable) ── */

const FileNameRenderer = ({ data }: { data?: ProjectFile }) => {
  if (!data) return null;
  return (
    <div className="flex items-center gap-2 h-full">
      <FileText className={`h-4 w-4 shrink-0 ${
        data.is_active
          ? data.file_type === 'PDF' ? 'text-red-400' : 'text-blue-400'
          : 'text-gray-300'
      }`} />
      <span
        className={`font-medium truncate ${
          data.is_active ? 'text-gray-800' : 'text-gray-400 line-through decoration-gray-300'
        }`}
        title={data.original_name}
      >
        {data.original_name}
      </span>
    </div>
  );
};

const TypeBadgeRenderer = ({ data }: { data?: ProjectFile }) => {
  if (!data) return null;
  return (
    <div className="flex items-center h-full">
      <span className={`inline-block px-2 py-0.5 rounded text-xs font-semibold ${
        data.is_active
          ? data.file_type === 'PDF' ? 'bg-red-50 text-red-600' : 'bg-blue-50 text-blue-600'
          : 'bg-gray-100 text-gray-400'
      }`}>
        {data.file_type}
      </span>
    </div>
  );
};

const SizeRenderer = ({ data }: { data?: ProjectFile }) => {
  if (!data) return null;
  return <span className={data.is_active ? 'text-gray-600' : 'text-gray-400'}>{fmtSize(data.size_bytes)}</span>;
};

const DateRenderer = ({ data }: { data?: ProjectFile }) => {
  if (!data) return null;
  return <span className={data.is_active ? 'text-gray-600' : 'text-gray-400'}>{fmtDate(data.uploaded_at)}</span>;
};

const StatusRenderer = ({ data }: { data?: ProjectFile }) => {
  if (!data) return null;
  return (
    <div className="flex items-center h-full">
      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${
        data.is_active
          ? 'bg-green-50 text-green-700 border-green-200'
          : 'bg-gray-100 text-gray-500 border-gray-200'
      }`}>
        {data.is_active ? 'Active' : 'Inactive'}
      </span>
    </div>
  );
};

/** Reads latest state from the ref passed as grid context. */
const ActionsRenderer = (params: { data?: ProjectFile; context: React.MutableRefObject<ActionsCtx> }) => {
  const file = params.data;
  if (!file) return null;
  const ctx = params.context.current;

  if (ctx.confirmDeleteId === file.id) {
    return (
      <div className="flex items-center gap-1 h-full">
        <span className="text-xs text-red-600 mr-1 whitespace-nowrap">Delete?</span>
        <button
          onClick={() => ctx.handleDelete(file.id)}
          className="p-1 rounded bg-red-500 text-white hover:bg-red-600"
          title="Confirm"
        >
          <Check className="h-3 w-3" />
        </button>
        <button
          onClick={() => ctx.setConfirmDeleteId(null)}
          className="p-1 rounded bg-gray-200 text-gray-600 hover:bg-gray-300"
          title="Cancel"
        >
          <X className="h-3 w-3" />
        </button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-1 h-full">
      <button
        onClick={() => window.open(`${API}/${ctx.projectId}/files/${file.id}/download`, '_blank')}
        className="p-1.5 rounded hover:bg-blue-100 text-blue-500"
        title="Download"
      >
        <Download className="h-3.5 w-3.5" />
      </button>
      <button
        onClick={() => ctx.startReplace(file.id)}
        disabled={!!ctx.replacingId}
        className="p-1.5 rounded hover:bg-amber-100 text-amber-500 disabled:opacity-40"
        title="Replace with new version"
      >
        <RefreshCw className={`h-3.5 w-3.5 ${ctx.replacingId === file.id ? 'animate-spin' : ''}`} />
      </button>
      <button
        onClick={() => ctx.handleToggleActive(file)}
        className={`p-1.5 rounded ${
          file.is_active ? 'hover:bg-orange-100 text-orange-400' : 'hover:bg-green-100 text-green-500'
        }`}
        title={file.is_active ? 'Set inactive' : 'Set active'}
      >
        {file.is_active ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
      </button>
      <button
        onClick={() => ctx.setConfirmDeleteId(file.id)}
        className="p-1.5 rounded hover:bg-red-100 text-red-400"
        title="Delete"
      >
        <Trash2 className="h-3.5 w-3.5" />
      </button>
    </div>
  );
};

/* ── Column defs (stable reference) ── */
const COLUMN_DEFS: ColDef<ProjectFile>[] = [
  {
    field: 'original_name',
    headerName: 'File Name',
    flex: 1,
    minWidth: 180,
    cellRenderer: FileNameRenderer,
  },
  {
    field: 'file_type',
    headerName: 'Type',
    width: 80,
    cellRenderer: TypeBadgeRenderer,
  },
  {
    field: 'size_bytes',
    headerName: 'Size',
    width: 110,
    cellRenderer: SizeRenderer,
  },
  {
    field: 'uploaded_at',
    headerName: 'Uploaded',
    width: 140,
    cellRenderer: DateRenderer,
  },
  {
    field: 'is_active',
    headerName: 'Status',
    width: 100,
    cellRenderer: StatusRenderer,
  },
  {
    colId: 'actions',
    headerName: '',
    width: 156,
    sortable: false,
    filter: false,
    resizable: false,
    suppressHeaderMenuButton: true,
    cellRenderer: ActionsRenderer,
  },
];

export default function ProjectFiles({ projectId, onFilesUpdated, onParseFiles }: Props) {
  const { t } = useTranslation();

  const [files,           setFiles]           = useState<ProjectFile[]>([]);
  const [loading,         setLoading]         = useState(true);
  const [uploading,       setUploading]       = useState(false);
  const [progress,        setProgress]        = useState(0);
  const [error,           setError]           = useState<string | null>(null);
  const [dragOver,        setDragOver]        = useState(false);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [replacingId,     setReplacingId]     = useState<string | null>(null);

  const uploadRef  = useRef<HTMLInputElement>(null);
  const replaceRef = useRef<HTMLInputElement>(null);
  const gridRef    = useRef<AgGridReact<ProjectFile>>(null);

  /** Ref passed as AgGrid context — always holds the latest handlers/state */
  const ctxRef = useRef<ActionsCtx>({} as ActionsCtx);

  /* ── Load ── */
  const load = useCallback(async () => {
    try {
      setLoading(true);
      const res = await axios.get<ProjectFile[]>(`${API}/${projectId}/files`);
      setFiles(res.data.map(f => ({ ...f, is_active: f.is_active ?? true })));
    } catch {
      setError(t('project.files_load_error', 'Failed to load files'));
    } finally {
      setLoading(false);
    }
  }, [projectId, t]);

  useEffect(() => { load(); }, [load]);

  /* ── Upload ── */
  async function handleUpload(fileList: FileList | null) {
    if (!fileList?.length) return;
    setError(null);
    const invalid = Array.from(fileList).filter(f => {
      const ext = f.name.split('.').pop()?.toLowerCase();
      return ext !== 'pdf' && ext !== 'dxf';
    });
    if (invalid.length) {
      setError(t('project.files_invalid_type', 'Only PDF and DXF files are accepted.'));
      return;
    }
    const form = new FormData();
    Array.from(fileList).forEach(f => form.append('files', f));
    try {
      setUploading(true); setProgress(0);
      await axios.post<ProjectFile[]>(`${API}/${projectId}/files`, form, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: e => setProgress(Math.round((e.loaded * 100) / (e.total ?? 1))),
      });
      await load();
      onFilesUpdated?.();
    } catch (err: any) {
      setError(err?.response?.data?.detail || t('project.files_upload_error', 'Upload failed'));
    } finally {
      setUploading(false); setProgress(0);
      if (uploadRef.current) uploadRef.current.value = '';
    }
  }

  /* ── Replace ── */
  async function handleReplace(fileId: string, fileList: FileList | null) {
    if (!fileList?.length) return;
    const file = fileList[0];
    const ext  = file.name.split('.').pop()?.toLowerCase();
    if (ext !== 'pdf' && ext !== 'dxf') { setError('Only PDF and DXF files are accepted.'); return; }
    const form = new FormData();
    form.append('file', file);
    try {
      setReplacingId(fileId);
      const res = await axios.put<ProjectFile>(
        `${API}/${projectId}/files/${fileId}`, form,
        { headers: { 'Content-Type': 'multipart/form-data' } },
      );
      setFiles(prev => prev.map(f => f.id === fileId
        ? { ...res.data, is_active: res.data.is_active ?? true } : f));
      onFilesUpdated?.();
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Replace failed');
    } finally {
      setReplacingId(null);
      if (replaceRef.current) replaceRef.current.value = '';
    }
  }

  /* ── Toggle active ── */
  const handleToggleActive = useCallback(async (file: ProjectFile) => {
    const next = !file.is_active;
    try {
      const res = await axios.patch<ProjectFile>(
        `${API}/${projectId}/files/${file.id}`, { is_active: next });
      setFiles(prev => prev.map(f => f.id === file.id
        ? { ...res.data, is_active: res.data.is_active ?? next } : f));
      onFilesUpdated?.();
    } catch {
      setError('Failed to update file status');
    }
  }, [projectId, onFilesUpdated]);

  /* ── Delete ── */
  const handleDelete = useCallback(async (fileId: string) => {
    try {
      await axios.delete(`${API}/${projectId}/files/${fileId}`);
      setFiles(prev => prev.filter(f => f.id !== fileId));
      setConfirmDeleteId(null);
      onFilesUpdated?.();
    } catch {
      setError(t('project.files_delete_error', 'Failed to delete file'));
    }
  }, [projectId, onFilesUpdated, t]);

  /* ── Keep context ref current every render ── */
  ctxRef.current = {
    confirmDeleteId,
    setConfirmDeleteId,
    replacingId,
    startReplace: (id: string) => { setReplacingId(id); replaceRef.current?.click(); },
    handleDelete,
    handleToggleActive,
    projectId,
  };

  /* ── Force-refresh action column when confirm/replace state changes ── */
  useEffect(() => {
    gridRef.current?.api?.refreshCells({ force: true, columns: ['actions'] });
  }, [confirmDeleteId, replacingId]);

  /* ── Drag & drop ── */
  const onDragOver  = (e: React.DragEvent) => { e.preventDefault(); setDragOver(true); };
  const onDragLeave = () => setDragOver(false);
  const onDrop      = (e: React.DragEvent) => { e.preventDefault(); setDragOver(false); handleUpload(e.dataTransfer.files); };

  /* ── Derived ── */
  const activeCount   = files.filter(f => f.is_active).length;
  const inactiveCount = files.filter(f => !f.is_active).length;

  return (
    <div
      className={`flex flex-col h-full gap-3 transition-colors ${dragOver ? 'ring-2 ring-blue-400 ring-offset-2 rounded-lg' : ''}`}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
    >
      {/* Error banner */}
      {error && (
        <div className="flex items-center gap-2 bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-2.5 text-sm shrink-0">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span className="flex-1">{error}</span>
          <button onClick={() => setError(null)}><X className="h-4 w-4" /></button>
        </div>
      )}

      {/* Toolbar row */}
      <div className="flex items-center gap-2 shrink-0">
        <button
          onClick={() => uploadRef.current?.click()}
          disabled={uploading}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
        >
          <UploadCloud className="h-4 w-4" />
          {t('project.files_upload_btn', 'Upload Files')}
        </button>

        {/* Parse Data — only enabled when at least one active file exists */}
        {(() => {
          const activeFiles = files.filter(f => f.is_active);
          const disabled = activeFiles.length === 0;
          return (
            <button
              onClick={() => onParseFiles?.(activeFiles.map(f => f.id))}
              disabled={disabled}
              title={disabled ? 'Upload a design file first' : `Parse ${activeFiles.length} active file(s)`}
              className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg border transition-colors
                ${disabled
                  ? 'border-gray-200 bg-gray-50 text-gray-300 cursor-not-allowed'
                  : 'border-emerald-500 bg-emerald-50 text-emerald-700 hover:bg-emerald-100'
                }`}
            >
              <ScanLine className="h-4 w-4" />
              Parse Data
            </button>
          );
        })()}

        <input ref={uploadRef} type="file" accept={ACCEPTED} multiple className="hidden"
          onChange={e => handleUpload(e.target.files)} />
        <input ref={replaceRef} type="file" accept={ACCEPTED} className="hidden"
          onChange={e => replacingId && handleReplace(replacingId, e.target.files)} />

        {uploading && (
          <div className="flex items-center gap-3 flex-1 min-w-0">
            <div className="flex-1 bg-gray-200 rounded-full h-1.5">
              <div className="bg-blue-500 h-1.5 rounded-full transition-all" style={{ width: `${progress}%` }} />
            </div>
            <span className="text-xs text-gray-500 shrink-0">{progress}%</span>
          </div>
        )}

        {files.length > 0 && !uploading && (
          <p className="text-xs text-gray-400 ms-auto whitespace-nowrap">
            {activeCount} active{inactiveCount > 0 && <>, {inactiveCount} inactive</>}
            {' · '}{fmtSize(files.reduce((s, f) => s + f.size_bytes, 0))} total
          </p>
        )}
      </div>

      {/* AgGrid */}
      <div className="flex-1 min-h-0 ag-theme-quartz rounded-xl overflow-hidden border border-gray-200">
        <AgGridReact<ProjectFile>
          ref={gridRef}
          rowData={files}
          columnDefs={COLUMN_DEFS}
          context={ctxRef}
          getRowId={(params: GetRowIdParams<ProjectFile>) => params.data.id}
          rowHeight={40}
          headerHeight={36}
          loading={loading}
          suppressCellFocus
          getRowStyle={(params: RowClassParams<ProjectFile>) =>
            params.data?.is_active === false ? { background: '#f9fafb' } : undefined
          }
        />
      </div>
    </div>
  );
}
