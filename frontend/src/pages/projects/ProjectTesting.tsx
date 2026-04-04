import { useState, useEffect, useMemo, useCallback } from 'react';
import { AgGridReact } from 'ag-grid-react';
import type { ColDef } from 'ag-grid-community';
import {
  Zap, CheckCircle2, XCircle, AlertTriangle, Plus, Trash2,
  FlaskConical, Shield, Activity, Gauge, ChevronUp,
} from 'lucide-react';
import * as api from '../../lib/api';
import type { TestType, TestRecord, CommissioningStatus } from '../../lib/api';
import { registerAgGridModules } from '../../lib/agGridModules';


registerAgGridModules();
interface Props { projectId:number; recordedBy?:string; }

const STATUS_COLORS: Record<string,string> = {
  pass:'bg-green-100 text-green-700 border-green-200',
  fail:'bg-red-100 text-red-700 border-red-200',
  inconclusive:'bg-yellow-100 text-yellow-700 border-yellow-200',
};
const TEST_ICON: Record<string,React.ReactNode> = {
  megger:      <Shield className="h-4 w-4"/>,
  isolation:   <Zap className="h-4 w-4"/>,
  continuity:  <Activity className="h-4 w-4"/>,
  polarity:    <CheckCircle2 className="h-4 w-4"/>,
  iv_curve:    <Gauge className="h-4 w-4"/>,
  earth_fault: <AlertTriangle className="h-4 w-4"/>,
  voc_check:   <FlaskConical className="h-4 w-4"/>,
  isc_check:   <FlaskConical className="h-4 w-4"/>,
};
const TEST_FIELDS: Record<string,{key:string;label:string;unit:string}[]> = {
  megger:      [{ key:'resistance_mohm',label:'Insulation Resistance',unit:'MΩ'},{key:'test_voltage_v',label:'Test Voltage',unit:'V'},{key:'leakage_current_ua',label:'Leakage Current',unit:'µA'}],
  isolation:   [{ key:'resistance_mohm',label:'DC Isolation Resistance',unit:'MΩ'},{key:'test_voltage_v',label:'Test Voltage',unit:'V'}],
  continuity:  [{ key:'resistance_ohm',label:'Loop Resistance',unit:'Ω'}],
  earth_fault: [{ key:'leakage_current_ma',label:'Leakage Current',unit:'mA'},{key:'earth_resistance_ohm',label:'Earth Resistance',unit:'Ω'}],
  voc_check:   [{ key:'voc_measured_v',label:'Measured Voc',unit:'V'},{key:'voc_expected_v',label:'Expected Voc',unit:'V'},{key:'irradiance_wm2',label:'Irradiance',unit:'W/m²'}],
  isc_check:   [{ key:'isc_measured_a',label:'Measured Isc',unit:'A'},{key:'isc_expected_a',label:'Expected Isc',unit:'A'},{key:'irradiance_wm2',label:'Irradiance',unit:'W/m²'}],
  iv_curve:    [{ key:'pmax_w',label:'Pmax',unit:'W'},{key:'voc_v',label:'Voc',unit:'V'},{key:'isc_a',label:'Isc',unit:'A'},{key:'fill_factor',label:'Fill Factor',unit:''},{key:'irradiance_wm2',label:'Irradiance',unit:'W/m²'},{key:'t_mod_c',label:'Module Temp',unit:'°C'}],
  polarity:    [],
};
const ENTITY_TYPES = ['string','inverter','section','array','panel','cable'];

export default function ProjectTesting({ projectId, recordedBy }: Props) {
  const [testTypes, setTestTypes]       = useState<TestType[]>([]);
  const [records, setRecords]           = useState<TestRecord[]>([]);
  const [commission, setCommission]     = useState<CommissioningStatus|null>(null);
  const [loading, setLoading]           = useState(true);
  const [showForm, setShowForm]         = useState(false);
  const [submitting, setSubmitting]     = useState(false);
  const [error, setError]               = useState<string|null>(null);
  const [activeFilter, setActiveFilter] = useState('all');
  const [form, setForm]                 = useState({ test_code:'', entity_type:'string', entity_ref:'', result_status:'pass', test_date:new Date().toISOString().slice(0,10), notes:'' });
  const [measuredValues, setMeasuredValues] = useState<Record<string,string>>({});

  useEffect(() => {
    Promise.all([api.listTestTypes(projectId), api.listTestRecords(projectId), api.getCommissioningStatus(projectId)])
      .then(([types,recs,comm]) => { setTestTypes(types); setRecords(recs); setCommission(comm); })
      .catch(console.error).finally(()=>setLoading(false));
  }, [projectId]);

  async function handleSubmit(e:React.FormEvent) {
    e.preventDefault(); if(!form.test_code){ setError('Select a test type.'); return; }
    setSubmitting(true); setError(null);
    try {
      const mv: Record<string,number|string> = {};
      for(const [k,v] of Object.entries(measuredValues)){ if(v==='') continue; const n=parseFloat(v); mv[k]=isNaN(n)?v:n; }
      const rec = await api.createTestRecord(projectId, { test_code:form.test_code, entity_type:form.entity_type, entity_ref:form.entity_ref||undefined, result_status:form.result_status, measured_values:Object.keys(mv).length?mv:undefined, test_date:form.test_date||undefined, notes:form.notes||undefined, recorded_by:recordedBy||undefined });
      setRecords(prev=>[rec,...prev]);
      api.getCommissioningStatus(projectId).then(setCommission).catch(()=>{});
      setShowForm(false); setMeasuredValues({}); setForm(f=>({ ...f, entity_ref:'', notes:'', test_code:'' }));
    } catch(err:any) { setError(err?.response?.data?.detail||err?.message||'Failed to save test record.'); }
    finally { setSubmitting(false); }
  }

  const handleDelete = useCallback(async (recordId:number) => {
    await api.deleteTestRecord(projectId, recordId);
    setRecords(prev=>prev.filter(r=>r.id!==recordId));
    api.getCommissioningStatus(projectId).then(setCommission).catch(()=>{});
  }, [projectId]);

  const filtered = activeFilter==='all' ? records : records.filter(r=>r.test_code===activeFilter);
  const selectedFields = form.test_code ? (TEST_FIELDS[form.test_code]??[]) : [];

  const columnDefs = useMemo<ColDef<TestRecord>[]>(() => [
    {
      field:'test_name', headerName:'Test', width:160,
      cellRenderer:(p:{value:string;data:TestRecord}) => (
        <div style={{ display:'flex', alignItems:'center', gap:6 }}>
          {TEST_ICON[p.data.test_code]}
          <span style={{ fontWeight:600, color:'#111827', fontSize:12 }}>{p.value}</span>
        </div>
      ),
    },
    {
      field:'entity_type', headerName:'Entity', width:140,
      cellRenderer:(p:{value:string;data:TestRecord}) => (
        <span>
          <span style={{ textTransform:'capitalize', color:'#6b7280' }}>{p.value}</span>
          {p.data.entity_ref && <span style={{ marginLeft:4, fontFamily:'monospace', fontSize:11, color:'#2563eb' }}>{p.data.entity_ref}</span>}
        </span>
      ),
    },
    {
      field:'result_status', headerName:'Result', width:110,
      cellRenderer:(p:{value:string}) => (
        <span className={`px-2 py-0.5 rounded-full text-xs font-semibold border capitalize ${STATUS_COLORS[p.value]??'bg-gray-100 text-gray-600'}`}>{p.value}</span>
      ),
    },
    {
      field:'measured_values', headerName:'Values', flex:1,
      cellRenderer:(p:{value:Record<string,unknown>|null}) =>
        p.value ? (
          <span style={{ fontFamily:'monospace', fontSize:11, color:'#6b7280' }}>
            {Object.entries(p.value).map(([k,v])=>`${k.replace(/_/g,' ')}: ${v}`).join(' · ')}
          </span>
        ) : <span style={{ color:'#d1d5db' }}>—</span>,
    },
    { field:'test_date', headerName:'Date',  width:100, cellStyle:{color:'#6b7280',fontSize:12} },
    { field:'notes',     headerName:'Notes', width:160, valueFormatter:(p:{value:string|null})=>p.value||'—', cellStyle:{color:'#6b7280',fontSize:12} },
    {
      headerName:'', width:44, sortable:false, resizable:false,
      cellRenderer:(p:{data:TestRecord}) => (
        <button onClick={()=>handleDelete(p.data.id)} style={{ background:'none', border:'none', cursor:'pointer', color:'#d1d5db', padding:4, display:'flex', alignItems:'center' }}
          onMouseEnter={e=>(e.currentTarget.style.color='#ef4444')} onMouseLeave={e=>(e.currentTarget.style.color='#d1d5db')}>
          <Trash2 size={14}/>
        </button>
      ),
    },
  ], [handleDelete]);

  if (loading) return <div className="flex items-center justify-center py-16"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"/></div>;

  return (
    <div className="space-y-4">
      {/* Commissioning banner */}
      {commission && (
        <div className={`rounded-xl border p-4 flex items-center gap-3 ${commission.ready?'bg-green-50 border-green-200':'bg-yellow-50 border-yellow-200'}`}>
          {commission.ready ? <CheckCircle2 className="h-5 w-5 text-green-600 shrink-0"/> : <AlertTriangle className="h-5 w-5 text-yellow-600 shrink-0"/>}
          <div className="flex-1">
            <p className={`font-semibold text-sm ${commission.ready?'text-green-800':'text-yellow-800'}`}>{commission.ready?'Ready for Commissioning':'Pre-commissioning tests incomplete'}</p>
            {!commission.ready && <p className="text-xs text-yellow-700 mt-0.5">Missing: {commission.missing.map(c=>c.replace('_',' ')).join(', ')}</p>}
          </div>
          <div className="flex gap-1.5 flex-wrap">
            {commission.required.map(code=>(
              <span key={code} className={`text-xs px-2 py-0.5 rounded-full font-medium border ${commission.passed.includes(code)?'bg-green-100 text-green-700 border-green-200':'bg-gray-100 text-gray-500 border-gray-200'}`}>
                {code.replace('_',' ')}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-gray-800 flex items-center gap-2">
          <FlaskConical className="h-4 w-4 text-blue-600"/> Field Test Records
          <span className="text-xs font-normal text-gray-400">{records.length} total</span>
        </h3>
        <button onClick={()=>setShowForm(v=>!v)} className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700">
          {showForm?<ChevronUp className="h-4 w-4"/>:<Plus className="h-4 w-4"/>}
          {showForm?'Cancel':'Record Test'}
        </button>
      </div>

      {/* Form */}
      {showForm && (
        <form onSubmit={handleSubmit} className="bg-white rounded-xl border border-gray-200 p-5 space-y-4">
          <h4 className="font-semibold text-gray-800">New Test Record</h4>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Test Type *</label>
              <select value={form.test_code} onChange={e=>{ setForm(f=>({...f,test_code:e.target.value})); setMeasuredValues({}); }} className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" required>
                <option value="">— Select —</option>
                {testTypes.map(tt=><option key={tt.test_code} value={tt.test_code}>{tt.test_name}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Entity Type *</label>
              <select value={form.entity_type} onChange={e=>setForm(f=>({...f,entity_type:e.target.value}))} className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                {ENTITY_TYPES.map(t=><option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Reference (e.g. S.1.2.3)</label>
              <input type="text" value={form.entity_ref} onChange={e=>setForm(f=>({...f,entity_ref:e.target.value}))} placeholder="S.1.2.3 / INV-1 / ..." className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"/>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Result *</label>
              <div className="flex gap-2">
                {['pass','fail','inconclusive'].map(s=>(
                  <button key={s} type="button" onClick={()=>setForm(f=>({...f,result_status:s}))} className={`flex-1 py-2 rounded-lg text-xs font-semibold border capitalize transition-colors ${form.result_status===s?STATUS_COLORS[s]:'bg-gray-50 text-gray-500 border-gray-200 hover:border-gray-300'}`}>{s}</button>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Test Date</label>
              <input type="date" value={form.test_date} onChange={e=>setForm(f=>({...f,test_date:e.target.value}))} className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"/>
            </div>
          </div>
          {selectedFields.length>0 && (
            <div>
              <p className="text-xs font-medium text-gray-600 mb-2">Measured Values</p>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {selectedFields.map(field=>(
                  <div key={field.key}>
                    <label className="block text-xs text-gray-500 mb-1">{field.label}{field.unit&&<span className="text-gray-400"> ({field.unit})</span>}</label>
                    <input type="number" step="any" value={measuredValues[field.key]??''} onChange={e=>setMeasuredValues(mv=>({...mv,[field.key]:e.target.value}))} className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" placeholder="—"/>
                  </div>
                ))}
              </div>
            </div>
          )}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Notes</label>
            <textarea value={form.notes} onChange={e=>setForm(f=>({...f,notes:e.target.value}))} rows={2} className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none" placeholder="Optional observations..."/>
          </div>
          {error && <div className="flex items-center gap-2 text-red-600 text-sm bg-red-50 rounded-lg p-3"><XCircle className="h-4 w-4 shrink-0"/>{error}</div>}
          <div className="flex justify-end gap-2">
            <button type="button" onClick={()=>setShowForm(false)} className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50">Cancel</button>
            <button type="submit" disabled={submitting} className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2">
              {submitting&&<span className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"/>}
              Save Test Record
            </button>
          </div>
        </form>
      )}

      {/* Filter pills */}
      <div className="flex gap-2 flex-wrap">
        <button onClick={()=>setActiveFilter('all')} className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${activeFilter==='all'?'bg-blue-600 text-white':'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}>
          All ({records.length})
        </button>
        {testTypes.filter(tt=>records.some(r=>r.test_code===tt.test_code)).map(tt=>(
          <button key={tt.test_code} onClick={()=>setActiveFilter(tt.test_code)} className={`px-3 py-1 rounded-full text-xs font-medium transition-colors flex items-center gap-1 ${activeFilter===tt.test_code?'bg-blue-600 text-white':'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}>
            {TEST_ICON[tt.test_code]}{tt.test_name} ({records.filter(r=>r.test_code===tt.test_code).length})
          </button>
        ))}
      </div>

      {/* AG Grid */}
      {filtered.length===0 ? (
        <div className="p-10 text-center text-gray-400 bg-white rounded-xl border border-gray-200">
          <FlaskConical className="h-10 w-10 mx-auto mb-3 opacity-30"/>
          <p className="text-sm">No test records yet. Click "Record Test" to add one.</p>
        </div>
      ) : (
        <div className="ag-theme-quartz" style={{ width:'100%', height:Math.min(filtered.length*37+37+2, 400) }}>
          <AgGridReact
            rowData={filtered}
            columnDefs={columnDefs}
            defaultColDef={{ resizable:true, sortable:true, suppressHeaderMenuButton:true }}
            domLayout="normal"
            rowHeight={36}
            headerHeight={36}
            suppressCellFocus
          />
        </div>
      )}
    </div>
  );
}
