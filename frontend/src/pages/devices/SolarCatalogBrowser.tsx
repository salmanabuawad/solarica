/**
 * SolarCatalogBrowser — edge-to-edge AG Grid with infinite virtual scrolling.
 * Loads rows on-demand as user scrolls. No pagination controls.
 * Double-click → spec modal.
 */
import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { AgGridReact } from 'ag-grid-react';
import type { RowDoubleClickedEvent, IDatasource, IGetRowsParams, GridReadyEvent, SortChangedEvent } from 'ag-grid-community';
import type { ColDef } from 'ag-grid-community';
import { RefreshCw, X, Zap, Download, Upload, FileDown } from 'lucide-react';
import * as api from '../../lib/api';
import type { SolarCatalogDevice, SolarCatalogStatus, SolarCatalogSpec } from '../../lib/types';
import { registerAgGridModules } from '../../lib/agGridModules';


registerAgGridModules();
const BLOCK = 100; // rows per fetch — matches default paginationPageSize

/* ── Catalog Device Modal ───────────────────────────────────────── */
function CatalogModal({ device, onClose }: { device: SolarCatalogDevice; onClose: () => void }) {
  const [detail, setDetail] = useState<SolarCatalogDevice | null>(null);
  const [busy, setBusy] = useState(true);

  useEffect(() => {
    setBusy(true);
    api.getSolarCatalogDevice(device.id)
      .then(d => setDetail(d))
      .catch(() => setDetail(device))
      .finally(() => setBusy(false));
  }, [device]);

  const groupedSpecs = useMemo(() => {
    if (!detail?.specs) return {} as Record<string, SolarCatalogSpec[]>;
    return detail.specs.reduce<Record<string, SolarCatalogSpec[]>>((acc, s) => {
      const g = s.spec_group ?? 'other';
      if (!acc[g]) acc[g] = [];
      acc[g].push(s);
      return acc;
    }, {});
  }, [detail]);

  const dev = detail ?? device;

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-[300]" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-3xl mx-4 overflow-hidden" onClick={e => e.stopPropagation()}>
        <div style={{ background:'#1e293b', padding:'16px 20px', display:'flex', alignItems:'center', justifyContent:'space-between' }}>
          <div>
            <div style={{ fontSize:16, fontWeight:700, color:'#fff' }}>{dev.model_name}</div>
            <div style={{ fontSize:12, color:'rgba(255,255,255,0.6)', marginTop:2 }}>
              {dev.manufacturer_name} · {dev.category_name}{dev.technology ? ` · ${dev.technology}` : ''}
            </div>
          </div>
          <button onClick={onClose} style={{ color:'rgba(255,255,255,0.7)', background:'none', border:'none', cursor:'pointer', padding:4 }}><X size={18}/></button>
        </div>
        <div style={{ padding:'20px', maxHeight:'72vh', overflowY:'auto' }}>
          <div style={{ display:'flex', flexWrap:'wrap', gap:8, marginBottom:16 }}>
            {[
              { label:'Brand',    value: dev.brand_name },
              { label:'Source',   value: dev.source_code },
              { label:'Hybrid',   value: dev.is_hybrid === true ? 'Yes' : dev.is_hybrid === false ? 'No' : null },
            ].filter(f => f.value).map(f => (
              <div key={f.label} style={{ background:'#f1f5f9', borderRadius:8, padding:'4px 12px' }}>
                <span style={{ fontSize:10, color:'#6b7280', fontWeight:600, textTransform:'uppercase', marginRight:6 }}>{f.label}</span>
                <span style={{ fontSize:12, color:'#111827', fontWeight:500 }}>{f.value}</span>
              </div>
            ))}
          </div>
          {busy ? (
            <div style={{ color:'#9ca3af', fontSize:13, textAlign:'center', padding:20 }}>Loading specs…</div>
          ) : Object.keys(groupedSpecs).length > 0 ? (
            Object.entries(groupedSpecs).map(([group, specs]) => (
              <div key={group} style={{ marginBottom:14 }}>
                <div style={{ display:'flex', alignItems:'center', gap:6, marginBottom:6 }}>
                  <Zap size={12} style={{ color:'#2563eb' }} />
                  <span style={{ fontSize:11, fontWeight:700, color:'#2563eb', textTransform:'uppercase', letterSpacing:'0.06em' }}>{group}</span>
                </div>
                <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(200px,1fr))', gap:'6px 16px' }}>
                  {specs.map(s => {
                    const val = s.spec_value_text != null ? s.spec_value_text
                      : s.spec_value_num != null ? `${s.spec_value_num}${s.unit ? ' ' + s.unit : ''}` : '—';
                    return (
                      <div key={s.id} style={{ background:'#f8fafc', borderRadius:6, padding:'4px 10px' }}>
                        <div style={{ fontSize:9, fontWeight:600, color:'#9ca3af', textTransform:'uppercase', letterSpacing:'0.04em' }}>{s.spec_key}</div>
                        <div style={{ fontSize:12, color:'#111827', fontWeight:500 }}>{val}</div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))
          ) : (
            <div style={{ color:'#9ca3af', fontSize:13, textAlign:'center', padding:10 }}>No specs available.</div>
          )}
        </div>
        <div style={{ padding:'12px 20px', borderTop:'1px solid #e2e8f0', display:'flex', justifyContent:'flex-end' }}>
          <button onClick={onClose} style={{ padding:'7px 20px', background:'#1e293b', color:'#fff', border:'none', borderRadius:8, fontSize:13, cursor:'pointer' }}>Close</button>
        </div>
      </div>
    </div>
  );
}

/* ── Main Page ─────────────────────────────────────────────────── */
export default function SolarCatalogBrowser() {
  const gridRef = useRef<AgGridReact<SolarCatalogDevice>>(null);

  const [status,        setStatus]        = useState<SolarCatalogStatus | null>(null);
  const [categories,    setCategories]    = useState<{category_code:string; category_name:string}[]>([]);
  const [total,         setTotal]         = useState<number | null>(null);
  const [selected,      setSelected]      = useState<SolarCatalogDevice | null>(null);
  const [importing,     setImporting]     = useState(false);
  const [importMsg,     setImportMsg]     = useState<string | null>(null);

  // Filter state — kept in refs so the datasource closure always reads fresh values
  const searchRef  = useRef('');
  const catRef     = useRef('');
  const mfrRef     = useRef('');
  const sortByRef  = useRef('');
  const sortDirRef = useRef('asc');

  const [searchVal,  setSearchVal]  = useState('');
  const [catVal,     setCatVal]     = useState('');
  const [mfrVal,     setMfrVal]     = useState('');

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    api.getSolarCatalogStatus().then(setStatus).catch(() => {/**/});
    api.listSolarCatalogCategories().then(setCategories).catch(() => {/**/});
  }, []);

  /* Build and apply a fresh datasource — call whenever filters change */
  const applyDatasource = useCallback(() => {
    const ds: IDatasource = {
      getRows: async (params: IGetRowsParams) => {
        try {
          const res = await api.searchSolarCatalog({
            q:            searchRef.current    || undefined,
            category:     catRef.current       || undefined,
            manufacturer: mfrRef.current       || undefined,
            sort_by:      sortByRef.current    || undefined,
            sort_dir:     sortDirRef.current   || undefined,
            limit:  BLOCK,
            offset: params.startRow,
          });
          setTotal(res.total);
          params.successCallback(res.items, res.total);
        } catch {
          params.failCallback();
        }
      },
    };
    gridRef.current?.api?.setGridOption('datasource', ds);
  }, []);

  const onGridReady = useCallback((e: GridReadyEvent) => {
    void e; // api is accessed via ref
    applyDatasource();
  }, [applyDatasource]);

  const onSortChanged = useCallback((e: SortChangedEvent) => {
    const col = e.api.getColumnState().find(c => c.sort);
    sortByRef.current  = col?.colId ?? '';
    sortDirRef.current = col?.sort ?? 'asc';
    applyDatasource();
  }, [applyDatasource]);

  function setFilter(ref: React.MutableRefObject<string>, setter: (v:string)=>void, val: string) {
    ref.current = val;
    setter(val);
    applyDatasource();
  }

  function handleSearchInput(val: string) {
    setSearchVal(val);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      searchRef.current = val;
      applyDatasource();
    }, 350);
  }

  const onRowDoubleClicked = useCallback((e: RowDoubleClickedEvent<SolarCatalogDevice>) => {
    if (e.data) setSelected(e.data);
  }, []);

  // ── Export CSV (uses current filters) ──
  const handleExportCsv = useCallback(() => {
    const params = new URLSearchParams();
    if (searchRef.current) params.set('q', searchRef.current);
    if (catRef.current)    params.set('category', catRef.current);
    if (mfrRef.current)    params.set('manufacturer', mfrRef.current);
    const url = `/api/solar-catalog/devices/export/csv?${params.toString()}`;
    const a = document.createElement('a');
    a.href = url; a.download = 'solar_catalog.csv'; a.click();
  }, []);

  // ── Template ──
  const handleDownloadTemplate = useCallback(() => {
    const headers = ['manufacturer_name','model_name','brand_name','category_code','technology','description','is_hybrid'];
    const example = ['SMA','Sunny Tripower 10.0','SMA','solar_inverter','String','10kW 3-phase string inverter','0'];
    const csv = [headers, example].map(r => r.map(v => `"${v}"`).join(',')).join('\r\n');
    const blob = new Blob([csv], { type:'text/csv;charset=utf-8;' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a'); a.href = url; a.download = 'solar_catalog_template.csv'; a.click();
    URL.revokeObjectURL(url);
  }, []);

  // ── Import CSV ──
  const handleImportCsv = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true); setImportMsg(null);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res  = await fetch('/api/solar-catalog/devices/import/csv', { method:'POST', body:fd });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? 'Import failed');
      setImportMsg(`✓ Added ${data.created} device${data.created !== 1 ? 's' : ''}${data.errors?.length ? ` — ${data.errors.length} error(s)` : ''}`);
      applyDatasource();
    } catch (err: unknown) {
      setImportMsg(`✗ ${err instanceof Error ? err.message : 'Import failed'}`);
    } finally {
      setImporting(false);
      e.target.value = '';
    }
  }, [applyDatasource]);

  const columnDefs = useMemo<ColDef<SolarCatalogDevice>[]>(() => [
    { field:'manufacturer_name', headerName:'Manufacturer', width:220, sortable:true },
    { field:'model_name',        headerName:'Model',        width:320, sortable:true },
    { field:'brand_name',        headerName:'Brand',        width:150, sortable:true },
    { field:'category_name',     headerName:'Category',     width:170, sortable:true },
    { field:'technology',        headerName:'Technology',   width:160, sortable:true },
    { field:'source_code',       headerName:'Source',       width:160, sortable:true },
    {
      field:'is_hybrid', headerName:'Hybrid', width:90, sortable:false,
      cellRenderer:(p:{value:boolean|null}) =>
        p.value === true  ? <span style={{color:'#2563eb',fontWeight:600}}>Yes</span>
        : p.value === false ? <span style={{color:'#9ca3af'}}>No</span>
        : <span style={{color:'#d1d5db'}}>—</span>,
    },
    { field:'spec_count', headerName:'Specs', width:80, type:'numericColumn', sortable:false },
  ], []);

  const inp: React.CSSProperties = {
    padding:'3px 8px', fontSize:12, borderRadius:5, border:'1px solid #d1d5db',
    background:'#fff', color:'#111827', height:26, outline:'none',
  };

  return (
    <div style={{ display:'flex', flexDirection:'column', flex:1, minHeight:0, overflow:'hidden' }}>

      {/* ── Slim toolbar ── */}
      <div style={{ display:'flex', alignItems:'center', gap:8, padding:'4px 8px', borderBottom:'1px solid #e2e8f0', background:'#f8fafc', flexShrink:0, flexWrap:'wrap' }}>
        <button onClick={applyDatasource}
          style={{ display:'flex', alignItems:'center', gap:4, padding:'3px 10px', fontSize:12, borderRadius:5, border:'1px solid #d1d5db', background:'#fff', cursor:'pointer', color:'#374151', height:26 }}>
          <RefreshCw size={12}/> Refresh
        </button>

        {/* Export CSV */}
        <button onClick={handleExportCsv}
          style={{ display:'flex', alignItems:'center', gap:4, padding:'3px 10px', fontSize:12, borderRadius:5, border:'1px solid #d1d5db', background:'#fff', cursor:'pointer', color:'#374151', height:26 }}>
          <Download size={12}/> Export CSV
        </button>

        {/* Download Template */}
        <button onClick={handleDownloadTemplate}
          style={{ display:'flex', alignItems:'center', gap:4, padding:'3px 10px', fontSize:12, borderRadius:5, border:'1px solid #d1d5db', background:'#fff', cursor:'pointer', color:'#374151', height:26 }}>
          <FileDown size={12}/> Template
        </button>

        {/* Import CSV */}
        <label style={{ display:'flex', alignItems:'center', gap:4, padding:'3px 10px', fontSize:12, borderRadius:5, border:'1px solid #2563eb', background:importing?'#e0e7ff':'#eff6ff', cursor:'pointer', color:'#2563eb', height:26, fontWeight:500 }}>
          <Upload size={12}/> {importing ? 'Importing…' : 'Import CSV'}
          <input type="file" accept=".csv" onChange={handleImportCsv} style={{ display:'none' }} disabled={importing}/>
        </label>

        {importMsg && (
          <span style={{ fontSize:11, color:importMsg.startsWith('✓')?'#16a34a':'#dc2626', fontWeight:500 }}>{importMsg}</span>
        )}

        <select style={inp} value={catVal} onChange={e => setFilter(catRef, setCatVal, e.target.value)}>
          <option value="">All Categories</option>
          {categories.map(c => <option key={c.category_code} value={c.category_code}>{c.category_name}</option>)}
        </select>

        <input type="text" placeholder="Manufacturer…" value={mfrVal}
          onChange={e => setFilter(mfrRef, setMfrVal, e.target.value)}
          style={{ ...inp, width:140 }} />

        <input type="text" placeholder="Search model…" value={searchVal}
          onChange={e => handleSearchInput(e.target.value)}
          style={{ ...inp, width:160 }} />

        {status && (
          <span style={{ fontSize:11, color:'#6b7280' }}>
            {(total ?? status.device_count).toLocaleString()} devices · {status.manufacturer_count.toLocaleString()} manufacturers
          </span>
        )}

        <span style={{ fontSize:11, color:'#9ca3af', marginLeft:'auto' }}>Double-click a row to view specs</span>
      </div>

      {/* ── Grid — fills all remaining height, virtual infinite scroll ── */}
      <div className="ag-theme-quartz" style={{ flex:1, minHeight:0, width:'100%', paddingBottom:12 }}>
        <AgGridReact<SolarCatalogDevice>
          ref={gridRef}
          rowModelType="infinite"
          columnDefs={columnDefs}
          defaultColDef={{ resizable:true, sortable:false, suppressHeaderMenuButton:true }}
          domLayout="normal"
          rowHeight={34}
          headerHeight={36}
          cacheBlockSize={BLOCK}
          maxBlocksInCache={20}
          infiniteInitialRowCount={100}
          pagination
          paginationPageSize={100}
          paginationPageSizeSelector={[50, 100, 250, 500]}
          suppressCellFocus
          onGridReady={onGridReady}
          onSortChanged={onSortChanged}
          onRowDoubleClicked={onRowDoubleClicked}
        />
      </div>

      {selected && <CatalogModal device={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
