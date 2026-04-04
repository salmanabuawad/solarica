import { useState, useEffect, useMemo, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { AgGridReact } from 'ag-grid-react';
import type { ColDef } from 'ag-grid-community';
import { Warehouse, Plus, AlertTriangle, Send, RefreshCcw, Trash2 } from 'lucide-react';
import * as api from '../../lib/api';
import DataPageShell from '../../components/layout/DataPageShell';
import { registerAgGridModules } from '../../lib/agGridModules';


registerAgGridModules();
interface IssueItem {
  material_name: string; quantity_issued: number; quantity_returned: number;
  quantity_consumed: number; quantity_missing: number; unit: string;
}

const inp: React.CSSProperties = {
  width:'100%', padding:'7px 10px', fontSize:13, color:'#111827',
  background:'#fff', border:'1px solid #d1d5db', borderRadius:6, outline:'none', boxSizing:'border-box',
};
const lbl: React.CSSProperties = { display:'block', fontSize:12, fontWeight:500, color:'#6b7280', marginBottom:4 };

const EMPTY_FORM = {
  project_id:'', warehouse_name:'', issued_to_user:'', issued_by_user:'',
  site_name:'', asset_type:'inverter', asset_ref:'', expected_usage_days:7, notes:'',
};
const EMPTY_ITEM: IssueItem = { material_name:'', quantity_issued:0, quantity_returned:0, quantity_consumed:0, quantity_missing:0, unit:'pcs' };

export default function WarehouseView() {
  const { t } = useTranslation();
  const [issues, setIssues]               = useState<any[]>([]);
  const [loading, setLoading]             = useState(true);
  const [showForm, setShowForm]           = useState(false);
  const [redFlagResult, setRedFlagResult] = useState<string | null>(null);
  const [form, setForm]                   = useState({ ...EMPTY_FORM });
  const [items, setItems]                 = useState<IssueItem[]>([{ ...EMPTY_ITEM }]);
  const [submitting, setSubmitting]       = useState(false);

  const fetchIssues = useCallback(() => {
    setLoading(true);
    api.listIssues().then(d => setIssues(d || [])).catch(console.error).finally(() => setLoading(false));
  }, []);
  useEffect(() => { fetchIssues(); }, [fetchIssues]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault(); setSubmitting(true);
    try {
      await api.issueMaterial({ ...form, items });
      setShowForm(false); setForm({ ...EMPTY_FORM }); setItems([{ ...EMPTY_ITEM }]); fetchIssues();
    } catch (err) { console.error(err); } finally { setSubmitting(false); }
  };

  const handleRunRedFlags = async () => {
    try {
      const result = await api.runRedFlags();
      const flagged = Array.isArray(result) ? result.length : 0;
      setRedFlagResult(`Red flag check complete. ${flagged} issue(s) flagged.`);
      fetchIssues();
    } catch (err) { console.error(err); }
  };

  const addItem    = () => setItems(p => [...p, { ...EMPTY_ITEM }]);
  const removeItem = (i: number) => setItems(p => p.filter((_, idx) => idx !== i));
  const updateItem = (i: number, f: keyof IssueItem, v: string | number) =>
    setItems(p => p.map((item, idx) => idx === i ? { ...item, [f]: v } : item));

  const columnDefs = useMemo<ColDef[]>(() => [
    { field:'warehouse_name', headerName:t('inventory.warehouse'),  width:160 },
    { field:'project_id',     headerName:t('nav.projects'),         width:110 },
    { field:'issued_to_user', headerName:t('inventory.issued_to'),  width:150 },
    {
      field:'status', headerName:t('common.status'), width:110,
      cellRenderer:(p: {value:string}) => {
        const flagged = p.value === 'flagged';
        return <span style={{ display:'inline-block', padding:'2px 8px', borderRadius:12, fontSize:11, fontWeight:600, background:flagged?'#fee2e2':'#dcfce7', color:flagged?'#dc2626':'#16a34a' }}>{String(t('statuses.'+p.value, p.value))}</span>;
      },
    },
    {
      field:'items', headerName:t('common.items'), width:90, type:'numericColumn',
      valueGetter:(p: {data:any}) => p.data?.items?.length ?? 0,
      valueFormatter:(p: {value:number}) => `${p.value} ${t('common.items')}`,
    },
    { field:'notes', headerName:t('common.notes'), flex:1, valueFormatter:(p:{value:string|null}) => p.value || '—' },
  ], [t]);

  const actions = [
    { icon:<Plus size={18}/>,          label:t('inventory.issue'),     variant:'primary' as const, onClick:() => setShowForm(v=>!v) },
    { icon:<AlertTriangle size={18}/>, label:t('inventory.red_flags'), variant:'danger'  as const, onClick:handleRunRedFlags },
    { icon:<RefreshCcw size={18}/>,    label:t('common.refresh'),                                  onClick:fetchIssues },
  ];

  return (
    <DataPageShell
      title={t('inventory.warehouse')}
      icon={<Warehouse size={17}/>}
      count={issues.length}
      actions={actions}
    >
      {/* Red-flag banner */}
      {redFlagResult && (
        <div className="shrink-0" style={{ margin:'8px 12px 0', padding:'8px 14px', borderRadius:6, background:'#fffbeb', border:'1px solid #fcd34d', color:'#92400e', fontSize:13 }}>
          {redFlagResult}
        </div>
      )}

      {/* Issue form */}
      {showForm && (
        <div className="shrink-0" style={{ margin:'8px 12px 0', padding:'16px', background:'#f9fafb', border:'1px solid #e5e7eb', borderRadius:8 }}>
          <div style={{ fontSize:14, fontWeight:600, color:'#111827', marginBottom:12 }}>{t('inventory.issue_materials')}</div>
          <form onSubmit={handleSubmit}>
            <div style={{ display:'grid', gridTemplateColumns:'repeat(3,1fr)', gap:10, marginBottom:12 }}>
              {([
                [t('inventory.project_id')+' *',        'project_id',         'text',   true],
                [t('inventory.warehouse')+' *',          'warehouse_name',      'text',   true],
                [t('inventory.issued_to')+' *',          'issued_to_user',      'text',   true],
                [t('inventory.issued_by')+' *',          'issued_by_user',      'text',   true],
                [t('inventory.site'),                    'site_name',           'text',   false],
                [t('inventory.expected_usage_days'),     'expected_usage_days', 'number', false],
              ] as [string,string,string,boolean][]).map(([label, key, type, required]) => (
                <div key={key}>
                  <label style={lbl}>{label}</label>
                  <input style={inp} type={type} required={!!required}
                    value={(form as any)[key]}
                    onChange={e => setForm(f => ({ ...f, [key]: type==='number' ? Number(e.target.value) : e.target.value }))} />
                </div>
              ))}
            </div>
            <div style={{ marginBottom:12 }}>
              <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:8 }}>
                <span style={{ fontSize:13, fontWeight:600, color:'#374151' }}>{t('common.items')}</span>
                <button type="button" onClick={addItem} style={{ background:'none', border:'none', color:'#2563eb', fontSize:13, cursor:'pointer', fontWeight:500 }}>{t('inventory.add_item')}</button>
              </div>
              {items.map((item, i) => (
                <div key={i} style={{ display:'flex', gap:8, marginBottom:6, alignItems:'center' }}>
                  <input style={{ ...inp, flex:2 }} placeholder={t('common.name')} value={item.material_name} onChange={e => updateItem(i,'material_name',e.target.value)} />
                  <input style={{ ...inp, width:80 }} type="number" placeholder={t('inventory.qty')} value={item.quantity_issued||''} onChange={e => updateItem(i,'quantity_issued',Number(e.target.value))} />
                  <input style={{ ...inp, width:70 }} placeholder={t('inventory.unit')} value={item.unit} onChange={e => updateItem(i,'unit',e.target.value)} />
                  {items.length > 1 && <button type="button" onClick={() => removeItem(i)} style={{ background:'none', border:'none', cursor:'pointer', color:'#ef4444', padding:'4px 6px', borderRadius:4 }}><Trash2 size={15}/></button>}
                </div>
              ))}
            </div>
            <div style={{ marginBottom:12 }}>
              <label style={lbl}>{t('common.notes')}</label>
              <textarea style={{ ...inp, resize:'none' }} rows={2} value={form.notes} onChange={e => setForm(f => ({ ...f, notes:e.target.value }))} />
            </div>
            <div style={{ display:'flex', justifyContent:'flex-end', gap:8 }}>
              <button type="button" onClick={() => setShowForm(false)} style={{ padding:'7px 14px', background:'none', border:'1px solid #d1d5db', borderRadius:6, fontSize:13, cursor:'pointer', color:'#374151' }}>{t('common.cancel')}</button>
              <button type="submit" disabled={submitting} style={{ display:'flex', alignItems:'center', gap:6, padding:'7px 16px', background:submitting?'#6b7280':'#2563eb', color:'#fff', border:'none', borderRadius:6, fontSize:13, fontWeight:600, cursor:submitting?'not-allowed':'pointer' }}>
                <Send size={14}/>{submitting ? t('common.loading') : t('inventory.issue')}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Grid */}
      {loading ? (
        <div style={{ flex:1, display:'flex', alignItems:'center', justifyContent:'center', color:'#9ca3af', fontSize:13 }}>Loading…</div>
      ) : (
        <div className="ag-theme-quartz flex-1 min-h-0" style={{ width:'100%', marginTop:8 }}>
          <AgGridReact
            rowData={issues}
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
  );
}
