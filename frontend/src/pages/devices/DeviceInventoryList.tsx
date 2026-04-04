/**
 * DeviceInventoryList — edge-to-edge AG Grid, full content height.
 * Slim single-row toolbar. Double-click row → detail modal.
 */
import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { AgGridReact } from 'ag-grid-react';
import type { RowDoubleClickedEvent, SelectionChangedEvent } from 'ag-grid-community';
import type { ColDef } from 'ag-grid-community';
import { AlertTriangle, CheckCircle, RefreshCw, MapPin, X, Shield, Download, Upload, FileDown, Trash2 } from 'lucide-react';
import * as api from '../../lib/api';
import type { DeviceInventoryItem, DeviceSite, DeviceInventorySummary } from '../../lib/types';
import { registerAgGridModules } from '../../lib/agGridModules';


registerAgGridModules();
const SEVERITY_COLORS: Record<string, string> = {
  Critical: '#dc2626', High: '#ea580c', Medium: '#ca8a04', Low: '#16a34a',
};

function SeverityBadge({ label }: { label: string }) {
  const color = SEVERITY_COLORS[label] ?? '#6b7280';
  return (
    <span style={{ display:'inline-block', padding:'2px 10px', borderRadius:9999, fontSize:11, fontWeight:600, background:color+'20', color }}>
      {label}
    </span>
  );
}

function DeviceModal({ device, onClose }: { device: DeviceInventoryItem; onClose: () => void }) {
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-[300]" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl mx-4 overflow-hidden" onClick={e => e.stopPropagation()}>
        <div style={{ background:'#1e293b', padding:'16px 20px', display:'flex', alignItems:'center', justifyContent:'space-between' }}>
          <div>
            <div style={{ fontSize:16, fontWeight:700, color:'#fff' }}>{device.model_normalized ?? device.model_raw ?? '—'}</div>
            <div style={{ fontSize:12, color:'rgba(255,255,255,0.6)', marginTop:2 }}>{device.manufacturer ?? ''} · {device.category}</div>
          </div>
          <button onClick={onClose} style={{ color:'rgba(255,255,255,0.7)', background:'none', border:'none', cursor:'pointer', padding:4 }}><X size={18}/></button>
        </div>
        <div style={{ padding:'20px', maxHeight:'70vh', overflowY:'auto' }}>
          <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'10px 24px', marginBottom:20 }}>
            {[
              { label:'Site',         value: device.site_name },
              { label:'Area',         value: device.area },
              { label:'Category',     value: device.category },
              { label:'Manufacturer', value: device.manufacturer },
              { label:'Model (raw)',  value: device.model_raw },
              { label:'Quantity',     value: device.quantity != null ? `${device.quantity} ${device.unit}` : null },
              { label:'Role',         value: device.role },
              { label:'Confirmed',    value: device.is_exact_model_confirmed ? 'Yes ✓' : 'Unconfirmed' },
            ].map(f => f.value ? (
              <div key={f.label}>
                <div style={{ fontSize:10, fontWeight:600, color:'#9ca3af', textTransform:'uppercase', letterSpacing:'0.05em' }}>{f.label}</div>
                <div style={{ fontSize:13, color:'#111827', marginTop:2 }}>{f.value}</div>
              </div>
            ) : null)}
          </div>
          {device.source_notes && (
            <div style={{ background:'#f8fafc', borderRadius:8, padding:'10px 14px', marginBottom:16 }}>
              <div style={{ fontSize:10, fontWeight:600, color:'#9ca3af', textTransform:'uppercase', marginBottom:4 }}>Notes</div>
              <div style={{ fontSize:12, color:'#374151' }}>{device.source_notes}</div>
            </div>
          )}
          {device.vuln_count > 0 && (
            <div>
              <div style={{ display:'flex', alignItems:'center', gap:6, marginBottom:10 }}>
                <Shield size={14} style={{ color:'#ea580c' }} />
                <span style={{ fontSize:13, fontWeight:600, color:'#ea580c' }}>{device.vuln_count} CVE{device.vuln_count > 1 ? 's' : ''} associated</span>
              </div>
              {device.vulnerabilities?.map(v => (
                <div key={v.id} style={{ border:'1px solid #fee2e2', borderRadius:8, padding:'10px 14px', marginBottom:8, background:'#fff5f5' }}>
                  <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:4 }}>
                    {v.severity && <SeverityBadge label={v.severity} />}
                    <span style={{ fontSize:12, fontWeight:600, color:'#111827' }}>{v.cve_id ?? 'Advisory'}</span>
                  </div>
                  <div style={{ fontSize:13, color:'#374151' }}>{v.title}</div>
                  {v.affected_versions && <div style={{ fontSize:11, color:'#6b7280', marginTop:4 }}>Affected: {v.affected_versions}</div>}
                  {v.fixed_versions && <div style={{ fontSize:11, color:'#16a34a', marginTop:2 }}>Fixed: {v.fixed_versions}</div>}
                </div>
              ))}
            </div>
          )}
        </div>
        <div style={{ padding:'12px 20px', borderTop:'1px solid #e2e8f0', display:'flex', justifyContent:'flex-end' }}>
          <button onClick={onClose} style={{ padding:'7px 20px', background:'#1e293b', color:'#fff', border:'none', borderRadius:8, fontSize:13, cursor:'pointer' }}>Close</button>
        </div>
      </div>
    </div>
  );
}

function CveModal({ device, onClose }: { device: DeviceInventoryItem; onClose: () => void }) {
  const vulns = device.vulnerabilities ?? [];
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-[310]" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-xl mx-4 overflow-hidden" onClick={e => e.stopPropagation()}>
        <div style={{ background:'#7f1d1d', padding:'16px 20px', display:'flex', alignItems:'center', justifyContent:'space-between' }}>
          <div>
            <div style={{ fontSize:15, fontWeight:700, color:'#fff', display:'flex', alignItems:'center', gap:8 }}>
              <Shield size={16}/> CVE Details
            </div>
            <div style={{ fontSize:12, color:'rgba(255,255,255,0.7)', marginTop:2 }}>
              {device.model_normalized ?? device.model_raw ?? '—'} · {device.manufacturer ?? ''}
            </div>
          </div>
          <button onClick={onClose} style={{ color:'rgba(255,255,255,0.7)', background:'none', border:'none', cursor:'pointer', padding:4 }}><X size={18}/></button>
        </div>
        <div style={{ padding:'20px', maxHeight:'70vh', overflowY:'auto' }}>
          {vulns.length === 0 ? (
            <div style={{ textAlign:'center', color:'#9ca3af', padding:'24px 0', fontSize:13 }}>No CVEs associated with this device.</div>
          ) : vulns.map(v => (
            <div key={v.id} style={{ border:'1px solid #fee2e2', borderRadius:10, padding:'14px 16px', marginBottom:10, background:'#fff5f5' }}>
              <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:6 }}>
                {v.severity && <SeverityBadge label={v.severity} />}
                <span style={{ fontSize:13, fontWeight:700, color:'#111827' }}>{v.cve_id ?? 'Advisory'}</span>
              </div>
              <div style={{ fontSize:13, color:'#374151', marginBottom:6 }}>{v.title}</div>
              {v.notes && <div style={{ fontSize:12, color:'#6b7280', marginBottom:6 }}>{v.notes}</div>}
              {v.affected_versions && (
                <div style={{ fontSize:11, color:'#dc2626', display:'flex', gap:4 }}>
                  <span style={{ fontWeight:600 }}>Affected:</span> {v.affected_versions}
                </div>
              )}
              {v.fixed_versions && (
                <div style={{ fontSize:11, color:'#16a34a', display:'flex', gap:4, marginTop:2 }}>
                  <span style={{ fontWeight:600 }}>Fixed:</span> {v.fixed_versions}
                </div>
              )}
              {v.advisory_source && (
                <div style={{ fontSize:11, color:'#6b7280', marginTop:4 }}>
                  <span style={{ fontWeight:600 }}>Source:</span> {v.advisory_source}
                </div>
              )}
              {v.applicability && (
                <div style={{ fontSize:11, color:'#6b7280', marginTop:2 }}>
                  <span style={{ fontWeight:600 }}>Applicability:</span> {v.applicability}
                </div>
              )}
            </div>
          ))}
        </div>
        <div style={{ padding:'12px 20px', borderTop:'1px solid #e2e8f0', display:'flex', justifyContent:'flex-end' }}>
          <button onClick={onClose} style={{ padding:'7px 20px', background:'#7f1d1d', color:'#fff', border:'none', borderRadius:8, fontSize:13, cursor:'pointer' }}>Close</button>
        </div>
      </div>
    </div>
  );
}

function ConfirmDialog({ message, onConfirm, onCancel }: { message: string; onConfirm: () => void; onCancel: () => void }) {
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-[320]" onClick={onCancel}>
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-sm mx-4 overflow-hidden" onClick={e => e.stopPropagation()}>
        <div style={{ padding:'20px 24px' }}>
          <div style={{ fontSize:14, fontWeight:600, color:'#111827', marginBottom:8 }}>Confirm Delete</div>
          <div style={{ fontSize:13, color:'#374151' }}>{message}</div>
        </div>
        <div style={{ padding:'12px 24px', borderTop:'1px solid #e2e8f0', display:'flex', justifyContent:'flex-end', gap:8 }}>
          <button onClick={onCancel} style={{ padding:'6px 16px', fontSize:12, borderRadius:6, border:'1px solid #d1d5db', background:'#fff', color:'#374151', cursor:'pointer' }}>Cancel</button>
          <button onClick={onConfirm} style={{ padding:'6px 16px', fontSize:12, borderRadius:6, border:'none', background:'#dc2626', color:'#fff', cursor:'pointer', fontWeight:600 }}>Delete</button>
        </div>
      </div>
    </div>
  );
}

/* ── CSV helpers ───────────────────────────────────────────────── */
const TEMPLATE_HEADERS = ['site_name','area','category','manufacturer','model_raw','model_normalized','quantity','unit','role','source_notes'];
const EXPORT_HEADERS   = [...TEMPLATE_HEADERS, 'is_exact_model_confirmed','vuln_count'];

function downloadCsv(filename: string, rows: string[][]) {
  const csv = rows.map(r => r.map(v => `"${String(v ?? '').replace(/"/g, '""')}"`).join(',')).join('\r\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

/* ── Main Page ─────────────────────────────────────────────────── */
export default function DeviceInventoryList() {
  const [devices,    setDevices]    = useState<DeviceInventoryItem[]>([]);
  const [sites,      setSites]      = useState<DeviceSite[]>([]);
  const [summary,    setSummary]    = useState<DeviceInventorySummary | null>(null);
  const [loading,    setLoading]    = useState(true);
  const [search,     setSearch]     = useState('');
  const [siteFilter, setSiteFilter] = useState('');
  const [catFilter,  setCatFilter]  = useState('');
  const [selected,   setSelected]   = useState<DeviceInventoryItem | null>(null);
  const [cveDevice,  setCveDevice]  = useState<DeviceInventoryItem | null>(null);
  const [importing,  setImporting]  = useState(false);
  const [importMsg,  setImportMsg]  = useState<string | null>(null);
  const [selectedRows, setSelectedRows] = useState<DeviceInventoryItem[]>([]);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting,   setDeleting]   = useState(false);
  const gridRef = useRef<AgGridReact<DeviceInventoryItem>>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [devs, siteList, sum] = await Promise.all([
        api.listDeviceInventory(), api.listDeviceSites(), api.getDeviceInventorySummary(),
      ]);
      setDevices(devs); setSites(siteList); setSummary(sum);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const categories = useMemo(() => [...new Set(devices.map(d => d.category))].sort(), [devices]);

  const filtered = useMemo(() => {
    let rows = devices;
    if (siteFilter) rows = rows.filter(d => String(d.site_id) === siteFilter);
    if (catFilter)  rows = rows.filter(d => d.category === catFilter);
    if (search) {
      const q = search.toLowerCase();
      rows = rows.filter(d =>
        d.model_normalized?.toLowerCase().includes(q) ||
        d.model_raw?.toLowerCase().includes(q) ||
        d.manufacturer?.toLowerCase().includes(q) ||
        d.category?.toLowerCase().includes(q) ||
        d.site_name?.toLowerCase().includes(q)
      );
    }
    return rows;
  }, [devices, siteFilter, catFilter, search]);

  const columnDefs = useMemo<ColDef<DeviceInventoryItem>[]>(() => [
    {
      headerCheckboxSelection: true,
      checkboxSelection: true,
      width: 44,
      maxWidth: 44,
      resizable: false,
      sortable: false,
      suppressHeaderMenuButton: true,
      pinned: 'left',
    },
    {
      field:'site_name', headerName:'Site', width:160,
      cellRenderer:(p:{value:string}) => (
        <span style={{ display:'flex', alignItems:'center', gap:4 }}>
          <MapPin size={11} style={{ color:'#9ca3af', flexShrink:0 }} />{p.value ?? '—'}
        </span>
      ),
    },
    { field:'area',         headerName:'Area',         width:120 },
    { field:'category',     headerName:'Category',     width:160 },
    { field:'manufacturer', headerName:'Manufacturer', width:200 },
    {
      field:'model_normalized', headerName:'Model', width:280,
      cellRenderer:(p:{value:string; data:DeviceInventoryItem}) => (
        <span title={p.data.model_raw ?? undefined}>{p.value ?? p.data.model_raw ?? '—'}</span>
      ),
    },
    {
      field:'quantity', headerName:'Qty', width:100, type:'numericColumn',
      valueFormatter: p => p.value != null ? `${p.value} ${p.data?.unit ?? ''}` : '—',
    },
    {
      field:'is_exact_model_confirmed', headerName:'Confirmed', width:110,
      cellRenderer:(p:{value:boolean}) =>
        p.value ? <CheckCircle size={14} style={{ color:'#16a34a' }} />
                : <span style={{ color:'#9ca3af', fontSize:11 }}>Unconfirmed</span>,
    },
    {
      field:'vuln_count', headerName:'CVEs', width:80, type:'numericColumn',
      cellRenderer:(p:{value:number; data:DeviceInventoryItem}) =>
        p.value > 0
          ? <span
              onClick={(e) => { e.stopPropagation(); setCveDevice(p.data); }}
              style={{ display:'flex', alignItems:'center', gap:3, color:'#ea580c', fontWeight:600, cursor:'pointer' }}
              title="Click to view CVE details"
            ><AlertTriangle size={11}/>{p.value}</span>
          : <span style={{ color:'#d1d5db' }}>—</span>,
    },
    { field:'role', headerName:'Role', width:160 },
    { field:'source_notes', headerName:'Notes', width:220 },
  ], []);

  const onRowDoubleClicked = useCallback((e: RowDoubleClickedEvent<DeviceInventoryItem>) => {
    if (e.data) setSelected(e.data);
  }, []);

  const onSelectionChanged = useCallback((e: SelectionChangedEvent<DeviceInventoryItem>) => {
    const rows = e.api.getSelectedRows();
    setSelectedRows(rows);
  }, []);

  const handleDeleteSelected = useCallback(async () => {
    const ids = selectedRows.map(r => r.id).filter(Boolean);
    if (!ids.length) return;
    setDeleting(true);
    try {
      await api.deleteDeviceInventoryBulk(ids);
      setSelectedRows([]);
      setConfirmDelete(false);
      await load();
    } catch (e) { console.error(e); }
    finally { setDeleting(false); }
  }, [selectedRows, load]);

  // ── Export ──
  const handleExportCsv = useCallback(() => {
    const rows: string[][] = [EXPORT_HEADERS];
    filtered.forEach(d => rows.push([
      d.site_name ?? '', d.area ?? '', d.category ?? '', d.manufacturer ?? '',
      d.model_raw ?? '', d.model_normalized ?? '',
      String(d.quantity ?? ''), d.unit ?? 'ea', d.role ?? '',
      d.source_notes ?? '',
      d.is_exact_model_confirmed ? '1' : '0',
      String(d.vuln_count ?? 0),
    ]));
    downloadCsv('device_inventory.csv', rows);
  }, [filtered]);

  // ── Template ──
  const handleDownloadTemplate = useCallback(() => {
    const example: string[] = [
      'Site Alpha', 'Array Block A', 'PV Module', 'SMA', 'SMA Sunny Tripower 10.0',
      'SMA-STP10.0-3AV-40', '12', 'ea', 'Grid Tie Inverter', 'Roof Section 3',
    ];
    downloadCsv('device_inventory_template.csv', [TEMPLATE_HEADERS, example]);
  }, []);

  // ── Import ──
  const handleImportCsv = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true); setImportMsg(null);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await fetch('/api/device-inventory/devices/import/csv', { method: 'POST', body: fd });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? 'Import failed');
      setImportMsg(`✓ Imported ${data.created} device${data.created !== 1 ? 's' : ''}${data.errors?.length ? ` — ${data.errors.length} error(s)` : ''}`);
      await load();
    } catch (err: unknown) {
      setImportMsg(`✗ ${err instanceof Error ? err.message : 'Import failed'}`);
    } finally {
      setImporting(false);
      e.target.value = '';
    }
  }, [load]);

  const inp: React.CSSProperties = {
    padding:'3px 8px', fontSize:12, borderRadius:5, border:'1px solid #d1d5db',
    background:'#fff', color:'#111827', height:26, outline:'none', cursor:'pointer',
  };

  return (
    <div style={{ display:'flex', flexDirection:'column', flex:1, minHeight:0, overflow:'hidden' }}>

      {/* ── Slim toolbar ── */}
      <div style={{ display:'flex', alignItems:'center', gap:8, padding:'4px 8px', borderBottom:'1px solid #e2e8f0', background:'#f8fafc', flexShrink:0, flexWrap:'wrap' }}>
        <button onClick={load}
          style={{ display:'flex', alignItems:'center', gap:4, padding:'3px 10px', fontSize:12, borderRadius:5, border:'1px solid #d1d5db', background:'#fff', cursor:'pointer', color:'#374151', height:26 }}>
          <RefreshCw size={12}/> Refresh
        </button>

        {selectedRows.length > 0 && (
          <button onClick={() => setConfirmDelete(true)} disabled={deleting}
            style={{ display:'flex', alignItems:'center', gap:4, padding:'3px 10px', fontSize:12, borderRadius:5, border:'1px solid #dc2626', background:'#fef2f2', cursor:'pointer', color:'#dc2626', height:26, fontWeight:600 }}>
            <Trash2 size={12}/> Delete Selected ({selectedRows.length})
          </button>
        )}

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
        <label style={{ display:'flex', alignItems:'center', gap:4, padding:'3px 10px', fontSize:12, borderRadius:5, border:'1px solid #2563eb', background: importing ? '#e0e7ff' : '#eff6ff', cursor:'pointer', color:'#2563eb', height:26, fontWeight:500 }}>
          <Upload size={12}/> {importing ? 'Importing…' : 'Import CSV'}
          <input type="file" accept=".csv" onChange={handleImportCsv} style={{ display:'none' }} disabled={importing}/>
        </label>

        {importMsg && (
          <span style={{ fontSize:11, color: importMsg.startsWith('✓') ? '#16a34a' : '#dc2626', fontWeight:500 }}>{importMsg}</span>
        )}

        <select style={inp} value={siteFilter} onChange={e => setSiteFilter(e.target.value)}>
          <option value="">All Sites</option>
          {sites.map(s => <option key={s.id} value={String(s.id)}>{s.site_name}</option>)}
        </select>

        <select style={inp} value={catFilter} onChange={e => setCatFilter(e.target.value)}>
          <option value="">All Categories</option>
          {categories.map(c => <option key={c} value={c}>{c}</option>)}
        </select>

        <input type="text" placeholder="Search…" value={search}
          onChange={e => setSearch(e.target.value)}
          style={{ ...inp, width:160, cursor:'text' }} />

        {/* Summary chips */}
        {summary && (
          <div style={{ display:'flex', gap:8, alignItems:'center' }}>
            {[
              { label:'Sites',   value: summary.site_count,        color:'#2563eb' },
              { label:'Devices', value: summary.device_type_count, color:'#7c3aed' },
              { label:'Units',   value: summary.total_units,       color:'#0891b2' },
              { label:'CVEs',    value: summary.cve_count,         color:'#dc2626' },
            ].map(s => (
              <span key={s.label} style={{ fontSize:12, fontWeight:700, color:s.color }}>
                {s.value} <span style={{ fontSize:10, fontWeight:400, color:'#6b7280' }}>{s.label}</span>
              </span>
            ))}
            {Object.entries(summary.severity_breakdown).filter(([,v]) => v > 0).map(([sev, cnt]) => (
              <span key={sev} style={{ display:'flex', alignItems:'center', gap:3 }}>
                <SeverityBadge label={sev.charAt(0).toUpperCase()+sev.slice(1)} />
                <span style={{ fontSize:11, fontWeight:600, color:'#374151' }}>{cnt}</span>
              </span>
            ))}
          </div>
        )}

        <span style={{ fontSize:11, color:'#9ca3af', marginLeft:'auto' }}>
          {filtered.length} rows · Double-click to view
        </span>
      </div>

      {/* ── Grid ── */}
      {loading ? (
        <div style={{ flex:1, display:'flex', alignItems:'center', justifyContent:'center', color:'#9ca3af', fontSize:13 }}>Loading…</div>
      ) : (
        <div className="ag-theme-quartz" style={{ flex:1, minHeight:0, width:'100%', paddingBottom:12 }}>
          <AgGridReact
            ref={gridRef}
            rowData={filtered}
            columnDefs={columnDefs}
            defaultColDef={{ resizable:true, sortable:true, suppressHeaderMenuButton:true }}
            domLayout="normal"
            rowHeight={36}
            headerHeight={36}
            suppressCellFocus
            rowSelection="multiple"
            suppressRowClickSelection
            onRowDoubleClicked={onRowDoubleClicked}
            onSelectionChanged={onSelectionChanged}
            gridOptions={{ rowBuffer:10, suppressScrollOnNewData:true }}
          />
        </div>
      )}

      {selected && <DeviceModal device={selected} onClose={() => setSelected(null)} />}
      {cveDevice && <CveModal device={cveDevice} onClose={() => setCveDevice(null)} />}
      {confirmDelete && (
        <ConfirmDialog
          message={`Delete ${selectedRows.length} selected device${selectedRows.length > 1 ? 's' : ''}? This action cannot be undone.`}
          onConfirm={handleDeleteSelected}
          onCancel={() => setConfirmDelete(false)}
        />
      )}
    </div>
  );
}
