import type React from 'react';
import { useTranslation } from 'react-i18next';
import { useState, useEffect, useMemo } from 'react';
import { FolderKanban, ClipboardCheck, ShieldCheck, AlertTriangle, Plus, Upload } from 'lucide-react';
import { AgGridReact } from 'ag-grid-react';
import { AllCommunityModule, ModuleRegistry } from 'ag-grid-community';
import type { ColDef } from 'ag-grid-community';
import * as api from '../lib/api';
import type { Project, MaintenanceTask } from '../lib/types';
import { useTabs } from '../contexts/AppContext';

ModuleRegistry.registerModules([AllCommunityModule]);

interface StatsCard {
  label: string;
  count: number;
  icon: React.ReactNode;
  color: string;
}

const PHASE_COLORS: Record<string,{bg:string;color:string}> = {
  design:         { bg:'#ede9fe', color:'#6d28d9' },
  validation:     { bg:'#fef3c7', color:'#b45309' },
  implementation: { bg:'#dbeafe', color:'#1d4ed8' },
  testing:        { bg:'#ffedd5', color:'#c2410c' },
  commissioning:  { bg:'#ccfbf1', color:'#0f766e' },
  maintenance:    { bg:'#dcfce7', color:'#15803d' },
  closed:         { bg:'#f3f4f6', color:'#6b7280' },
};

const STATUS_COLORS: Record<string,{bg:string;color:string}> = {
  open:        { bg:'#fef3c7', color:'#b45309' },
  in_progress: { bg:'#dbeafe', color:'#1d4ed8' },
};

export default function Dashboard() {
  const { t } = useTranslation();
  const { openTab } = useTabs();
  const [projects, setProjects] = useState<Project[]>([]);
  const [tasks, setTasks] = useState<MaintenanceTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchData() {
      try {
        setLoading(true);
        const [projectData, taskData] = await Promise.all([
          api.listProjects(),
          api.listTasks(),
        ]);
        setProjects(projectData);
        setTasks(taskData);
      } catch (err) {
        console.error('Failed to fetch dashboard data:', err);
        setError('Failed to load dashboard data');
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  const pendingApprovals = tasks.filter(
    (t) => t.requires_approval && t.status !== 'closed',
  ).length;

  const activeTasks = tasks.filter(
    (t) => t.status === 'open' || t.status === 'in_progress',
  ).length;

  const redFlags = 0;

  const stats: StatsCard[] = [
    { label: t('dashboard.total_projects'), count: projects.length || 0, icon: <FolderKanban className="h-6 w-6 text-blue-600" />, color: '#3b82f6' },
    { label: t('dashboard.active_tasks'),   count: activeTasks || 0,     icon: <ClipboardCheck className="h-6 w-6 text-green-600" />, color: '#22c55e' },
    { label: t('dashboard.pending_approvals'), count: pendingApprovals || 0, icon: <ShieldCheck className="h-6 w-6 text-amber-600" />, color: '#f59e0b' },
    { label: t('dashboard.red_flags'),      count: redFlags || 0,        icon: <AlertTriangle className="h-6 w-6 text-red-600" />, color: '#ef4444' },
  ];

  const recentProjects = useMemo(() => projects.slice(-5).reverse(), [projects]);
  const pendingTasks   = useMemo(() => tasks.filter(t => t.status === 'open' || t.status === 'in_progress').slice(0, 8), [tasks]);

  const projectColDefs = useMemo<ColDef<Project>[]>(() => ([
    {
      field: 'name', headerName: t('projects.fields.name'), flex: 2,
      cellStyle: { fontWeight: 600, color: '#111827', cursor: 'pointer' } as React.CSSProperties,
    },
    { field: 'customer_name', headerName: t('projects.fields.customer'), width: 140, cellStyle: { color: '#6b7280' } as React.CSSProperties, valueFormatter: (p:{value:string|null}) => p.value || '—' },
    {
      field: 'phase', headerName: t('projects.fields.phase'), width: 130,
      cellRenderer: (p:{value:string}) => {
        const c = PHASE_COLORS[p.value] ?? { bg:'#f3f4f6', color:'#6b7280' };
        return <span style={{ display:'inline-block', padding:'2px 8px', borderRadius:12, fontSize:11, fontWeight:600, background:c.bg, color:c.color, textTransform:'capitalize' }}>{p.value}</span>;
      },
    },
    {
      field: 'progress_percent', headerName: t('projects.fields.progress'), width: 130,
      cellRenderer: (p:{value:number}) => (
        <div style={{ display:'flex', alignItems:'center', gap:6, width:'100%' }}>
          <div style={{ flex:1, background:'#e5e7eb', borderRadius:999, height:6, overflow:'hidden' }}>
            <div style={{ width:`${p.value}%`, background:'#3b82f6', height:'100%', borderRadius:999 }}/>
          </div>
          <span style={{ fontSize:11, color:'#6b7280', width:30, textAlign:'right' }}>{p.value}%</span>
        </div>
      ),
    },
  ] as ColDef<Project>[]), [t]);

  const taskColDefs = useMemo<ColDef<MaintenanceTask>[]>(() => ([
    {
      field: 'title', headerName: t('tasks.title', 'Task'), flex: 2,
      cellStyle: { fontWeight: 600, color: '#111827', cursor: 'pointer' } as React.CSSProperties,
    },
    { field: 'asset_type', headerName: 'Type', width: 110, cellStyle: { color:'#6b7280', fontSize:12, textTransform:'capitalize' } as React.CSSProperties },
    { field: 'priority',   headerName: 'Priority', width: 90,  cellStyle: { color:'#6b7280', fontSize:12, textTransform:'capitalize' } as React.CSSProperties, valueFormatter: (p:{value:string|null}) => p.value || 'normal' },
    {
      field: 'status', headerName: t('common.status', 'Status'), width: 110,
      cellRenderer: (p:{value:string}) => {
        const c = STATUS_COLORS[p.value] ?? { bg:'#f3f4f6', color:'#6b7280' };
        return <span style={{ display:'inline-block', padding:'2px 8px', borderRadius:12, fontSize:11, fontWeight:600, background:c.bg, color:c.color }}>{p.value.replace('_',' ')}</span>;
      },
    },
  ] as ColDef<MaintenanceTask>[]), [t]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 text-center text-red-600">
        <AlertTriangle className="h-8 w-8 mx-auto mb-2" />
        <p>{error}</p>
      </div>
    );
  }

  return (
    <div className="p-4 sm:p-6 space-y-4 sm:space-y-6 h-full overflow-y-auto">
      {/* Stats Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        {stats.map((stat) => (
          <div
            key={stat.label}
            className="bg-white rounded-lg shadow-sm p-4 sm:p-4 flex items-center gap-3"
            style={{ borderInlineStart: `4px solid ${stat.color}` }}
          >
            <div className="flex-shrink-0">{stat.icon}</div>
            <div>
              <p className="text-2xl font-bold text-gray-900">{stat.count}</p>
              <p className="text-xs sm:text-sm text-gray-500">{stat.label}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Recent Projects & Pending Tasks */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Projects */}
        <div className="bg-white rounded-lg shadow-sm overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-100">
            <h2 className="text-sm font-semibold text-gray-800">{t('dashboard.recent_projects')}</h2>
          </div>
          {recentProjects.length === 0 ? (
            <p className="p-4 text-gray-500 text-sm">{t('dashboard.no_projects')}</p>
          ) : (
            <div className="ag-theme-quartz" style={{ width:'100%', height: Math.min(recentProjects.length*37+37+2, 260) }}>
              <AgGridReact<Project>
                rowData={recentProjects}
                columnDefs={projectColDefs}
                defaultColDef={{ resizable:true, sortable:true, suppressHeaderMenuButton:true }}
                domLayout="normal"
                rowHeight={36}
                headerHeight={36}
                suppressCellFocus
                onRowClicked={(e) => {
                  if (!e.data) return;
                  openTab({ id:`project-${e.data.id}`, type:'project', label:e.data.name, projectId:String(e.data.id) });
                }}
              />
            </div>
          )}
        </div>

        {/* Pending Tasks */}
        <div className="bg-white rounded-lg shadow-sm overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-100">
            <h2 className="text-sm font-semibold text-gray-800">{t('dashboard.pending_tasks')}</h2>
          </div>
          {pendingTasks.length === 0 ? (
            <p className="p-4 text-gray-500 text-sm">{t('dashboard.no_tasks')}</p>
          ) : (
            <div className="ag-theme-quartz" style={{ width:'100%', height: Math.min(pendingTasks.length*37+37+2, 260) }}>
              <AgGridReact<MaintenanceTask>
                rowData={pendingTasks}
                columnDefs={taskColDefs}
                defaultColDef={{ resizable:true, sortable:true, suppressHeaderMenuButton:true }}
                domLayout="normal"
                rowHeight={36}
                headerHeight={36}
                suppressCellFocus
                onRowClicked={(e) => {
                  if (!e.data) return;
                  openTab({ id:`task-${e.data.id}`, type:'task', label:e.data.title });
                }}
              />
            </div>
          )}
        </div>
      </div>

      {/* Quick Actions */}
      <div className="flex gap-3">
        <button
          onClick={() => openTab({ id:'new-project', type:'project-wizard', label:'New Project' })}
          className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium"
        >
          <Plus className="h-4 w-4" />
          {t('dashboard.new_project')}
        </button>
        <button
          onClick={() => openTab({ id:'measurements', type:'measurements', label:'Measurements' })}
          className="inline-flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors text-sm font-medium"
        >
          <Upload className="h-4 w-4" />
          {t('dashboard.upload_measurement')}
        </button>
      </div>
    </div>
  );
}
