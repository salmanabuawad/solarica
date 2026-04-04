import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { AgGridReact } from 'ag-grid-react';
import type { ColDef } from 'ag-grid-community';
import { Upload, FileUp, RefreshCcw, CheckCircle2, XCircle, FolderOpen, X, FileText } from 'lucide-react';
import * as api from '../../lib/api';
import type { Measurement } from '../../lib/types';
import type { SuiImportResult } from '../../lib/api';
import DataPageShell from '../../components/layout/DataPageShell';
import { registerAgGridModules } from '../../lib/agGridModules';


registerAgGridModules();
function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes/1024).toFixed(1)} KB`;
  return `${(bytes/(1024*1024)).toFixed(1)} MB`;
}

function ImportModal({ onClose, onImported }: { onClose:()=>void; onImported:()=>void }) {
  const [uploading, setUploading]         = useState(false);
  const [error, setError]                 = useState<string|null>(null);
  const [importResult, setImportResult]   = useState<SuiImportResult|null>(null);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const fileRef   = useRef<HTMLInputElement>(null);
  const folderRef = useRef<HTMLInputElement>(null);

  function addFiles(newFiles: File[]) {
    setSelectedFiles(prev => { const ex=new Set(prev.map(f=>f.name+f.size)); return [...prev,...newFiles.filter(f=>!ex.has(f.name+f.size))]; });
    setImportResult(null); setError(null);
  }
  function removeFile(i:number) { setSelectedFiles(p=>p.filter((_,idx)=>idx!==i)); }
  function clearAll() { setSelectedFiles([]); setImportResult(null); setError(null); if(fileRef.current) fileRef.current.value=''; if(folderRef.current) folderRef.current.value=''; }

  async function handleImport() {
    if (!selectedFiles.length) { setError('Add at least one .SUI or .ZIP file.'); return; }
    setUploading(true); setError(null); setImportResult(null);
    try {
      const result = await api.uploadSui(selectedFiles);
      setImportResult(result); setSelectedFiles([]);
      if (result.imported > 0) onImported();
    } catch (err:any) { setError(err?.response?.data?.detail || err?.message || 'Upload failed.'); }
    finally { setUploading(false); }
  }

  useEffect(() => { const h=(e:KeyboardEvent)=>{ if(e.key==='Escape') onClose(); }; document.addEventListener('keydown',h); return ()=>document.removeEventListener('keydown',h); }, [onClose]);
  const done = importResult && selectedFiles.length===0;

  return (
    <div onClick={e=>{ if(e.target===e.currentTarget) onClose(); }} style={{ position:'fixed', inset:0, zIndex:1000, background:'rgba(0,0,0,0.45)', display:'flex', alignItems:'center', justifyContent:'center', padding:24 }}>
      <div style={{ background:'#fff', borderRadius:12, width:'100%', maxWidth:620, boxShadow:'0 20px 60px rgba(0,0,0,0.25)', display:'flex', flexDirection:'column', maxHeight:'90vh', overflow:'hidden' }}>
        <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', padding:'18px 20px', borderBottom:'1px solid #e5e7eb' }}>
          <div style={{ display:'flex', alignItems:'center', gap:8 }}>
            <Upload size={18} style={{ color:'#2563eb' }} />
            <span style={{ fontWeight:700, fontSize:16, color:'#111827' }}>Import PVPM Measurements</span>
          </div>
          <button onClick={onClose} style={{ background:'none', border:'none', cursor:'pointer', color:'#9ca3af', padding:4, borderRadius:6, display:'flex', alignItems:'center' }}><X size={20}/></button>
        </div>
        <div style={{ padding:'20px', overflowY:'auto', flex:1 }}>
          <p style={{ fontSize:13, color:'#6b7280', marginBottom:16, lineHeight:1.5 }}>Add <strong>.SUI</strong> files exported from PVPM 1540X, or a <strong>.ZIP</strong> archive containing SUI files.</p>
          <div style={{ display:'flex', gap:8, marginBottom:16, flexWrap:'wrap' }}>
            <label style={{ display:'flex', alignItems:'center', gap:6, padding:'8px 14px', background:'#f9fafb', border:'1px solid #e5e7eb', borderRadius:8, fontSize:13, color:'#374151', cursor:'pointer', fontWeight:500 }}>
              <FileText size={14} style={{ color:'#2563eb' }}/> Add Files
              <input ref={fileRef} type="file" accept=".sui,.SUI,.zip,.ZIP" multiple style={{ display:'none' }} onChange={e=>{ addFiles(Array.from(e.target.files||[])); e.target.value=''; }}/>
            </label>
            <label style={{ display:'flex', alignItems:'center', gap:6, padding:'8px 14px', background:'#f9fafb', border:'1px solid #e5e7eb', borderRadius:8, fontSize:13, color:'#374151', cursor:'pointer', fontWeight:500 }}>
              <FolderOpen size={14} style={{ color:'#f59e0b' }}/> Add Folder
              <input ref={folderRef} type="file" {...({'webkitdirectory':''}as any)} multiple style={{ display:'none' }} onChange={e=>{ addFiles(Array.from(e.target.files||[]).filter(f=>f.name.toLowerCase().endsWith('.sui')||f.name.toLowerCase().endsWith('.zip'))); e.target.value=''; }}/>
            </label>
            {selectedFiles.length>0 && <button onClick={clearAll} style={{ padding:'8px 12px', background:'transparent', border:'1px solid #e5e7eb', borderRadius:8, fontSize:13, color:'#6b7280', cursor:'pointer' }}>Clear all</button>}
            <span style={{ marginLeft:'auto', fontSize:13, color:selectedFiles.length>0?'#2563eb':'#9ca3af', fontWeight:600, alignSelf:'center' }}>{selectedFiles.length>0?`${selectedFiles.length} file${selectedFiles.length>1?'s':''} queued`:'No files added yet'}</span>
          </div>
          {selectedFiles.length>0 && (
            <div style={{ border:'1px solid #e5e7eb', borderRadius:8, maxHeight:220, overflowY:'auto', marginBottom:16 }}>
              {selectedFiles.map((f,i)=>(
                <div key={i} style={{ display:'flex', alignItems:'center', gap:8, padding:'8px 12px', borderBottom:i<selectedFiles.length-1?'1px solid #f3f4f6':undefined, background:i%2===0?'#fff':'#fafafa' }}>
                  <FileText size={13} style={{ color:'#6b7280', flexShrink:0 }}/>
                  <span style={{ fontSize:13, color:'#111827', flex:1, minWidth:0, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{f.name}</span>
                  <span style={{ fontSize:12, color:'#9ca3af', flexShrink:0, marginRight:4 }}>{formatSize(f.size)}</span>
                  <button onClick={()=>removeFile(i)} style={{ background:'none', border:'none', cursor:'pointer', color:'#d1d5db', padding:2, display:'flex', alignItems:'center', flexShrink:0 }}><X size={14}/></button>
                </div>
              ))}
            </div>
          )}
          {importResult && (
            <div style={{ background:'#f9fafb', border:'1px solid #e5e7eb', borderRadius:8, padding:'14px 16px' }}>
              <div style={{ display:'flex', gap:10, marginBottom:importResult.errors.length?10:0 }}>
                {importResult.imported>0 && <span style={{ display:'flex', alignItems:'center', gap:5, padding:'4px 12px', background:'#f0fdf4', border:'1px solid #bbf7d0', borderRadius:20, fontSize:13, color:'#15803d', fontWeight:600 }}><CheckCircle2 size={13}/>{importResult.imported} imported</span>}
                {importResult.failed>0 && <span style={{ display:'flex', alignItems:'center', gap:5, padding:'4px 12px', background:'#fef2f2', border:'1px solid #fecaca', borderRadius:20, fontSize:13, color:'#dc2626', fontWeight:600 }}><XCircle size={13}/>{importResult.failed} failed</span>}
              </div>
              {importResult.errors.length>0 && <div style={{ fontSize:12, color:'#dc2626', marginTop:8 }}>{importResult.errors.map((e,i)=><div key={i}><strong>{e.file}</strong>: {e.error}</div>)}</div>}
            </div>
          )}
          {error && <div style={{ padding:'10px 14px', borderRadius:8, background:'#fef2f2', border:'1px solid #fecaca', color:'#dc2626', fontSize:13, marginTop:12 }}>{error}</div>}
        </div>
        <div style={{ display:'flex', justifyContent:'flex-end', gap:10, padding:'16px 20px', borderTop:'1px solid #e5e7eb', background:'#f9fafb' }}>
          <button onClick={onClose} style={{ padding:'9px 18px', background:'#fff', border:'1px solid #d1d5db', borderRadius:8, fontSize:13, color:'#374151', fontWeight:500, cursor:'pointer' }}>{done?'Close':'Cancel'}</button>
          {!done && <button onClick={handleImport} disabled={uploading||selectedFiles.length===0} style={{ display:'flex', alignItems:'center', gap:6, padding:'9px 20px', background:uploading||selectedFiles.length===0?'#93c5fd':'#2563eb', color:'#fff', border:'none', borderRadius:8, fontSize:13, fontWeight:600, cursor:uploading||selectedFiles.length===0?'not-allowed':'pointer' }}>
            {uploading && <span style={{ width:14, height:14, border:'2px solid rgba(255,255,255,0.4)', borderTopColor:'#fff', borderRadius:'50%', display:'inline-block', animation:'spin 0.7s linear infinite' }}/>}
            {uploading?'Importing…':`Import${selectedFiles.length>0?` (${selectedFiles.length})`:''}`}
          </button>}
        </div>
      </div>
    </div>
  );
}

export default function MeasurementList() {
  const { t } = useTranslation();
  const [measurements, setMeasurements] = useState<Measurement[]>([]);
  const [loading, setLoading]           = useState(true);
  const [showModal, setShowModal]       = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try { setMeasurements(await api.listMeasurements()); } catch(e) { console.error(e); } finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const rowData = useMemo(() => measurements.map(m => {
    const first = m.records[0] as Record<string,unknown>|undefined;
    return {
      ...m,
      _device_model: String(first?.device_model||'—'),
      _sensor:       String(first?.sensor||'—'),
      _site:         String(first?.site||'—'),
      _string:       String(first?.string||'—'),
      _count:        m.records.length,
    };
  }), [measurements]);

  const columnDefs = useMemo<ColDef[]>(() => [
    { field:'file_name',     headerName:t('measurements.filename'),         flex:2 },
    { field:'_device_model', headerName:t('measurements.device_model_col'), width:160 },
    { field:'_sensor',       headerName:t('measurements.sensor'),           width:130 },
    { field:'_site',         headerName:t('inventory.site'),                width:130 },
    { field:'_string',       headerName:t('measurements.string_col'),       width:100 },
    { field:'uploaded_at',   headerName:t('measurements.uploaded_col'),     width:170 },
    { field:'_count',        headerName:t('measurements.records_col'),      width:90, type:'numericColumn' },
  ], [t]);

  const actions = [
    { icon:<Upload size={18}/>,     label:t('measurements.upload_sui'), variant:'primary' as const, onClick:()=>setShowModal(true) },
    { icon:<RefreshCcw size={18}/>, label:t('common.refresh'),                                      onClick:load },
  ];

  return (
    <>
      {showModal && <ImportModal onClose={()=>setShowModal(false)} onImported={load}/>}
      <DataPageShell
        title={t('measurements.title')}
        icon={<FileUp size={17}/>}
        count={measurements.length}
        actions={actions}
      >
        {loading ? (
          <div style={{ flex:1, display:'flex', alignItems:'center', justifyContent:'center', color:'#9ca3af', fontSize:13 }}>Loading…</div>
        ) : (
          <div className="ag-theme-quartz flex-1 min-h-0" style={{ width:'100%' }}>
            <AgGridReact
              rowData={rowData}
              columnDefs={columnDefs}
              defaultColDef={{ resizable:true, sortable:true, suppressHeaderMenuButton:true }}
              domLayout="normal"
              rowHeight={36}
              headerHeight={36}
              suppressCellFocus
            />
          </div>
        )}
      </DataPageShell>
    </>
  );
}
