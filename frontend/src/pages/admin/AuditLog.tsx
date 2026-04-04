import { useState, useEffect, useMemo, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { AgGridReact } from 'ag-grid-react';
import type { ColDef } from 'ag-grid-community';
import { ScrollText, RefreshCw } from 'lucide-react';
import * as api from '../../lib/api';
import DataPageShell from '../../components/layout/DataPageShell';
import { registerAgGridModules } from '../../lib/agGridModules';


registerAgGridModules();
interface AuditEntry {
  id:number; actor_username:string; actor_role:string; action:string;
  entity_type:string|null; entity_id:number|null; detail:string|null; created_at:string;
}

const ACTION_COLORS: Record<string,{bg:string;color:string}> = {
  login:            { bg:'#dbeafe', color:'#1d4ed8' },
  create_project:   { bg:'#dcfce7', color:'#15803d' },
  update_phase:     { bg:'#ccfbf1', color:'#0f766e' },
  validate_design:  { bg:'#fef3c7', color:'#b45309' },
  create_task:      { bg:'#ede9fe', color:'#6d28d9' },
  approve_task:     { bg:'#e0e7ff', color:'#4338ca' },
  issue_material:   { bg:'#ffedd5', color:'#c2410c' },
  register_user:    { bg:'#ffe4e6', color:'#be123c' },
  create_material:  { bg:'#ecfccb', color:'#4d7c0f' },
  create_warehouse: { bg:'#cffafe', color:'#0e7490' },
  receive_stock:    { bg:'#d1fae5', color:'#065f46' },
};

const inp: React.CSSProperties = { padding:'4px 8px', fontSize:12, borderRadius:5, border:'1px solid #d1d5db', background:'#fff', color:'#111827', height:26, outline:'none' };

export default function AuditLog() {
  const { t } = useTranslation();
  const [entries, setEntries]       = useState<AuditEntry[]>([]);
  const [loading, setLoading]       = useState(true);
  const [search, setSearch]         = useState('');
  const [filterAction, setFilter]   = useState('');

  const load = useCallback(() => {
    setLoading(true);
    api.listAuditLog().then(setEntries).catch(console.error).finally(()=>setLoading(false));
  }, []);
  useEffect(() => { load(); }, [load]);

  const uniqueActions = useMemo(()=>[...new Set(entries.map(e=>e.action))].sort(), [entries]);

  const rowData = useMemo(() => entries.filter(e => {
    const q = search.toLowerCase();
    return (!q || e.actor_username.toLowerCase().includes(q) || e.action.includes(q) || (e.detail||'').toLowerCase().includes(q))
        && (!filterAction || e.action === filterAction);
  }).map(e => ({
    ...e,
    _time: new Date(e.created_at).toLocaleString(undefined,{month:'short',day:'2-digit',hour:'2-digit',minute:'2-digit'}),
    _entity: e.entity_type ? `${e.entity_type} #${e.entity_id||'—'}` : '—',
  })), [entries, search, filterAction]);

  const columnDefs = useMemo<ColDef[]>(() => [
    { field:'_time',          headerName:t('audit.time','Time'),     width:140, cellStyle:{color:'#6b7280',fontSize:12} },
    {
      field:'actor_username', headerName:t('audit.user','User'),     width:160,
      cellRenderer:(p:{value:string;data:AuditEntry&{_time:string;_entity:string}}) => (
        <div>
          <div style={{ fontWeight:600, color:'#111827', fontSize:12 }}>{p.value}</div>
          <div style={{ fontSize:10, color:'#9ca3af', textTransform:'capitalize' }}>{p.data.actor_role}</div>
        </div>
      ),
    },
    {
      field:'action', headerName:t('audit.action','Action'), width:180,
      cellRenderer:(p:{value:string}) => {
        const c = ACTION_COLORS[p.value] ?? { bg:'#f3f4f6', color:'#6b7280' };
        return <span style={{ padding:'2px 8px', borderRadius:4, fontSize:11, fontWeight:600, background:c.bg, color:c.color }}>{p.value.replace(/_/g,' ')}</span>;
      },
    },
    { field:'_entity', headerName:t('audit.entity','Entity'), width:140, cellStyle:{color:'#6b7280',fontSize:12} },
    { field:'detail',  headerName:t('audit.detail','Detail'), flex:1, cellStyle:{color:'#6b7280',fontSize:12}, valueFormatter:(p:{value:string|null})=>p.value||'—' },
  ], [t]);

  const actions = [
    { icon:<RefreshCw size={16}/>, label:t('common.refresh','Refresh'), onClick:load },
  ];

  return (
    <DataPageShell
      title={t('audit.title','Audit Log')}
      icon={<ScrollText size={17}/>}
      count={rowData.length}
      actions={actions}
    >
      {/* Filters toolbar */}
      <div className="shrink-0" style={{ display:'flex', gap:8, padding:'4px 8px', borderBottom:'1px solid #e2e8f0', background:'#f8fafc', alignItems:'center' }}>
        <input type="text" placeholder={t('audit.search','Search user, action, detail…')} value={search}
          onChange={e=>setSearch(e.target.value)} style={{ ...inp, width:220, cursor:'text' }}/>
        <select style={inp} value={filterAction} onChange={e=>setFilter(e.target.value)}>
          <option value="">{t('audit.all_actions','All Actions')}</option>
          {uniqueActions.map(a=><option key={a} value={a}>{a.replace(/_/g,' ')}</option>)}
        </select>
        <span style={{ fontSize:11, color:'#9ca3af', marginLeft:'auto' }}>{rowData.length} {t('audit.entries','entries')}</span>
      </div>

      {/* Grid */}
      {loading ? (
        <div style={{ flex:1, display:'flex', alignItems:'center', justifyContent:'center', color:'#9ca3af', fontSize:13 }}>Loading…</div>
      ) : (
        <div className="ag-theme-quartz flex-1 min-h-0" style={{ width:'100%' }}>
          <AgGridReact
            rowData={rowData}
            columnDefs={columnDefs}
            defaultColDef={{ resizable:true, sortable:true, suppressHeaderMenuButton:true }}
            domLayout="normal"
            rowHeight={42}
            headerHeight={36}
            suppressCellFocus
          />
        </div>
      )}
    </DataPageShell>
  );
}
