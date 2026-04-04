import { useState, useEffect, useCallback, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { AgGridReact } from 'ag-grid-react';
import type { ColDef, ICellRendererParams } from 'ag-grid-community';
import { Plus, RefreshCcw, Download, ClipboardCheck } from 'lucide-react';
import * as api from '../../lib/api';
import type { MaintenanceTask } from '../../lib/types';
import { useTabs } from '../../contexts/AppContext';
import TaskCreate from './TaskCreate';
import DataPageShell from '../../components/layout/DataPageShell';
import { registerAgGridModules } from '../../lib/agGridModules';


registerAgGridModules();
const PRIORITY_C: Record<string, { bg:string; color:string }> = {
  low:      { bg:'#f3f4f6', color:'#6b7280' },
  medium:   { bg:'#dbeafe', color:'#2563eb' },
  high:     { bg:'#ffedd5', color:'#ea580c' },
  critical: { bg:'#fee2e2', color:'#dc2626' },
};
const STATUS_C: Record<string, { bg:string; color:string }> = {
  open:        { bg:'#fef3c7', color:'#d97706' },
  in_progress: { bg:'#dbeafe', color:'#2563eb' },
  closed:      { bg:'#dcfce7', color:'#16a34a' },
};

function Badge({ value, map }: { value: string; map: Record<string, { bg:string; color:string }> }) {
  const c = map[value] ?? { bg:'#f3f4f6', color:'#6b7280' };
  return <span style={{ display:'inline-block', padding:'2px 8px', borderRadius:12, fontSize:11, fontWeight:600, background:c.bg, color:c.color }}>{value}</span>;
}

function BoolCell({ value }: { value: boolean }) {
  return value ? <span style={{ color:'#16a34a', fontWeight:700, fontSize:13 }}>✓</span> : <span style={{ color:'#d1d5db' }}>—</span>;
}

const STATUS_OPTIONS  = ['all','open','in_progress','closed'];
const PRIORITY_OPTIONS = ['all','low','medium','high','critical'];

export default function TaskList() {
  const { t } = useTranslation();
  const { openTab } = useTabs();
  const [tasks, setTasks]           = useState<MaintenanceTask[]>([]);
  const [loading, setLoading]       = useState(true);
  const [search, setSearch]         = useState('');
  const [statusF, setStatusF]       = useState('all');
  const [priorityF, setPriorityF]   = useState('all');
  const [showCreate, setShowCreate] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try { setTasks(await api.listTasks()); }
    catch(e) { console.error(e); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const columnDefs = useMemo<ColDef<MaintenanceTask>[]>(() => [
    { width:40, maxWidth:40, resizable:false, suppressHeaderMenuButton:true },
    { field:'id',               headerName:'ID',                              width:70 },
    { field:'title',            headerName: t('tasks.fields.title'),          flex:2,   filter:true },
    { field:'project_id',       headerName: t('nav.projects'),                width:90 },
    { field:'priority',         headerName: t('tasks.fields.priority'),       flex:1,
      cellRenderer:(p:ICellRendererParams) => p.value ? <Badge value={p.value} map={PRIORITY_C}/> : null },
    { field:'status',           headerName: t('tasks.fields.status'),         flex:1,
      cellRenderer:(p:ICellRendererParams) => p.value ? <Badge value={p.value} map={STATUS_C}/> : null },
    { field:'task_type',        headerName: t('tasks.fields.type'),           flex:1 },
    { field:'asset_type',       headerName:'Asset',                           flex:1 },
    { field:'asset_ref',        headerName:'Ref',                             width:90 },
    { field:'assigned_to',      headerName: t('tasks.fields.assigned_to'),   flex:1 },
    { field:'requires_approval',headerName: t('tasks.fields.approvals'),     width:90,
      cellRenderer:(p:ICellRendererParams) => <BoolCell value={p.value}/> },
    { field:'requires_test_result',headerName: t('tasks.fields.test_results'), width:70,
      cellRenderer:(p:ICellRendererParams) => <BoolCell value={p.value}/> },
  ], [t]);

  const filtered = useMemo(() => {
    let r = tasks;
    if (statusF   !== 'all') r = r.filter(t => t.status   === statusF);
    if (priorityF !== 'all') r = r.filter(t => t.priority === priorityF);
    if (search) {
      const q = search.toLowerCase();
      r = r.filter(t => t.title.toLowerCase().includes(q) || t.assigned_to?.toLowerCase().includes(q));
    }
    return r;
  }, [tasks, statusF, priorityF, search]);

  /* Filter selects rendered inside toolbar */
  const toolbarExtra = (
    <>
      <select value={statusF} onChange={e=>setStatusF(e.target.value)}
        style={{ padding:'5px 8px', fontSize:12, border:'1px solid #d1d5db', borderRadius:6, background:'#f9fafb', color:'#374151', cursor:'pointer' }}>
        {STATUS_OPTIONS.map(s => (
          <option key={s} value={s}>
            {s === 'all' ? t('common.all_statuses') : t('statuses.' + s, s.replace('_', ' '))}
          </option>
        ))}
      </select>
      <select value={priorityF} onChange={e=>setPriorityF(e.target.value)}
        style={{ padding:'5px 8px', fontSize:12, border:'1px solid #d1d5db', borderRadius:6, background:'#f9fafb', color:'#374151', cursor:'pointer' }}>
        {PRIORITY_OPTIONS.map(p => (
          <option key={p} value={p}>
            {p === 'all' ? t('common.all_priorities') : t('priorities.' + p, p)}
          </option>
        ))}
      </select>
    </>
  );

  const actions = [
    { icon:<Plus size={18}/>,       label: t('tasks.create'),  variant:'primary' as const, onClick:()=>setShowCreate(true) },
    { icon:<RefreshCcw size={18}/>, label: t('common.refresh'), onClick:load },
    { icon:<Download size={18}/>,   label: t('common.export'),  onClick:()=>{} },
  ];

  return (
    <>
      <DataPageShell
        title={t('tasks.list_title')}
        icon={<ClipboardCheck size={17}/>}
        count={tasks.length}
        actions={actions}
        toolbarExtra={toolbarExtra}
        searchValue={search}
        searchPlaceholder={t('common.search') + '...'}
        onSearchChange={setSearch}
      >
        {loading ? (
          <div style={{ display:'flex', alignItems:'center', justifyContent:'center', height:200 }}>
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"/>
          </div>
        ) : (
          <div className="ag-theme-quartz" style={{ height:'100%', width:'100%' }}>
            <AgGridReact<MaintenanceTask>
              rowData={filtered}
              columnDefs={columnDefs}
              onRowClicked={p => p.data && openTab({ id:`task-${p.data.id}`, type:'task', label:p.data.title })}
              rowSelection={{ mode:'multiRow', checkboxes:true, headerCheckbox:true }}
              animateRows
              pagination
              paginationPageSize={20}
              paginationPageSizeSelector={[20, 50, 100]}
            />
          </div>
        )}
      </DataPageShell>

      {showCreate && <TaskCreate onClose={() => { setShowCreate(false); load(); }}/>}
    </>
  );
}
