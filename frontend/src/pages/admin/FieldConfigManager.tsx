import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { AgGridReact } from 'ag-grid-react';
import type { ColDef, ICellRendererParams, RowDragEndEvent, CellValueChangedEvent } from 'ag-grid-community';
import { Eye, EyeOff, Save, RotateCcw, CheckCircle2, Loader2 } from 'lucide-react';
import * as api from '../../lib/api';
import type { FieldConfigItem } from '../../lib/api';
import { GRID_DEFAULTS } from '../../lib/fieldConfigDefaults';
import { useFieldConfigContext } from '../../lib/FieldConfigContext';
import DataPageShell from '../../components/layout/DataPageShell';
import { registerAgGridModules } from '../../lib/agGridModules';

registerAgGridModules();
interface Row {
  field_name: string;
  header:     string;
  visible:    boolean;
  width:      number | null;
}

const GRID_OPTIONS = GRID_DEFAULTS.map(g => ({ value: g.grid_name, label: g.label }));

function mergeWithDefaults(gridName: string, configs: FieldConfigItem[]): Row[] {
  const defaults = GRID_DEFAULTS.find(g => g.grid_name === gridName)?.columns ?? [];
  const configMap = new Map(configs.map(c => [c.field_name, c]));

  // If we have saved configs, order by column_order; otherwise use defaults order
  if (configs.length > 0) {
    const sorted = [...configs].sort((a, b) => (a.column_order ?? 999) - (b.column_order ?? 999));
    const configured: Row[] = sorted.map(c => {
      const def = defaults.find(d => d.field_name === c.field_name);
      return {
        field_name: c.field_name,
        header:     def?.header ?? c.field_name,
        visible:    c.visible,
        width:      c.width ?? null,
      };
    });
    const configuredNames = new Set(configs.map(c => c.field_name));
    const extra: Row[] = defaults
      .filter(d => !configuredNames.has(d.field_name))
      .map(d => ({ field_name: d.field_name, header: d.header, visible: d.visible, width: d.width ?? null }));
    return [...configured, ...extra];
  }

  return defaults.map(d => ({
    field_name: d.field_name,
    header:     d.header,
    visible:    d.visible,
    width:      configMap.get(d.field_name)?.width ?? d.width ?? null,
  }));
}

export default function FieldConfigManager() {
  const { t } = useTranslation();
  const { bump } = useFieldConfigContext();

  const [selectedGrid, setSelectedGrid] = useState(GRID_OPTIONS[0].value);
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const gridRef = useRef<AgGridReact<Row>>(null);

  // Load configs whenever selected grid changes
  useEffect(() => {
    setLoading(true);
    setSaved(false);
    setError(null);
    api.getFieldConfigs(selectedGrid)
      .then(configs => {
        setRows(mergeWithDefaults(selectedGrid, configs));
      })
      .catch(() => {
        const defaults = GRID_DEFAULTS.find(g => g.grid_name === selectedGrid)?.columns ?? [];
        setRows(defaults.map(d => ({ field_name: d.field_name, header: d.header, visible: d.visible, width: d.width ?? null })));
      })
      .finally(() => setLoading(false));
  }, [selectedGrid]);

  const resetToDefaults = useCallback(() => {
    const defaults = GRID_DEFAULTS.find(g => g.grid_name === selectedGrid)?.columns ?? [];
    setRows(defaults.map(d => ({ field_name: d.field_name, header: d.header, visible: d.visible, width: d.width ?? null })));
    setSaved(false);
  }, [selectedGrid]);

  const handleSave = useCallback(async () => {
    // Read current row order from the grid (respects drag-reorder)
    const currentRows: Row[] = [];
    gridRef.current?.api?.forEachNode(n => { if (n.data) currentRows.push(n.data); });
    const source = currentRows.length > 0 ? currentRows : rows;

    setSaving(true);
    setError(null);
    const items: FieldConfigItem[] = source.map((r, i) => ({
      grid_name:    selectedGrid,
      field_name:   r.field_name,
      visible:      r.visible,
      width:        r.width,
      column_order: i,
    }));
    try {
      await api.saveFieldConfigs(items);
      setSaved(true);
      bump();
    } catch {
      setError('Save failed');
    } finally {
      setSaving(false);
    }
  }, [selectedGrid, rows, bump]);

  const onRowDragEnd = useCallback((_e: RowDragEndEvent<Row>) => {
    setSaved(false);
  }, []);

  const onCellValueChanged = useCallback((_e: CellValueChangedEvent<Row>) => {
    setSaved(false);
  }, []);

  const columnDefs = useMemo((): ColDef<Row>[] => [
    {
      rowDrag: true,
      width: 40,
      maxWidth: 40,
      resizable: false,
      sortable: false,
      suppressHeaderMenuButton: true,
      headerName: '',
      field: 'field_name' as const,
      cellRenderer: () => null,
    },
    {
      field: 'header' as const,
      headerName: 'Column',
      flex: 1,
      sortable: false,
      editable: false,
      suppressHeaderMenuButton: true,
      cellStyle: { fontWeight: 500 },
    },
    {
      field: 'field_name' as const,
      headerName: 'Field',
      width: 180,
      sortable: false,
      editable: false,
      suppressHeaderMenuButton: true,
      cellStyle: { fontFamily: 'monospace', fontSize: 12, color: '#6b7280' },
    },
    {
      field: 'width' as const,
      headerName: 'Width (px)',
      width: 110,
      sortable: false,
      editable: true,
      suppressHeaderMenuButton: true,
      cellEditor: 'agNumberCellEditor',
      valueFormatter: (p: { value: number | null }) => p.value != null ? String(p.value) : '—',
      cellStyle: { color: '#374151' },
    },
    {
      field: 'visible' as const,
      headerName: 'Visible',
      width: 80,
      sortable: false,
      editable: false,
      suppressHeaderMenuButton: true,
      cellRenderer: (params: ICellRendererParams<Row>) => {
        const visible = params.value as boolean;
        return (
          <button
            onClick={() => {
              if (params.node.data) {
                params.node.setDataValue('visible', !visible);
              }
            }}
            className={`p-1 rounded transition-colors ${visible ? 'text-blue-600 hover:text-blue-700' : 'text-gray-300 hover:text-gray-500'}`}
            title={visible ? 'Click to hide' : 'Click to show'}
          >
            {visible ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
          </button>
        );
      },
    },
  ], []);

  return (
    <DataPageShell title={t('admin.field_config', 'Field Configuration')}>
      <div className="flex flex-col h-full gap-0">
        {/* Toolbar */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-gray-200 bg-white">
          <select
            value={selectedGrid}
            onChange={e => setSelectedGrid(e.target.value)}
            className="text-sm border border-gray-300 rounded-lg px-3 py-1.5 bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {GRID_OPTIONS.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>

          <div className="flex-1" />

          {error && <span className="text-xs text-red-500">{error}</span>}
          {saved && (
            <span className="flex items-center gap-1 text-xs text-green-600">
              <CheckCircle2 className="h-3.5 w-3.5" /> Saved
            </span>
          )}
          <button
            onClick={resetToDefaults}
            title="Reset to defaults"
            className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500"
          >
            <RotateCcw className="h-4 w-4" />
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-1.5 px-4 py-1.5 text-sm font-medium bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-60"
          >
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
            Save
          </button>
        </div>

        {/* Grid */}
        <div className="flex-1 min-h-0 ag-theme-quartz">
          {loading ? (
            <div className="flex items-center justify-center h-full">
              <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
            </div>
          ) : (
            <AgGridReact
              ref={gridRef}
              rowData={rows}
              columnDefs={columnDefs}
              rowDragManaged
              animateRows
              onRowDragEnd={onRowDragEnd}
              onCellValueChanged={onCellValueChanged}
              rowHeight={44}
              headerHeight={40}
              suppressMovableColumns
              getRowId={(p: { data: Row }) => p.data.field_name}
            />
          )}
        </div>

        <p className="px-4 py-2 text-xs text-gray-400 border-t border-gray-100 bg-white">
          Drag rows to reorder · Click the eye to toggle visibility · Click a width cell to edit · Save to apply
        </p>
      </div>
    </DataPageShell>
  );
}
