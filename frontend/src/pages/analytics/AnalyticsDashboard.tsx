import { useState, useEffect, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { AgGridReact } from 'ag-grid-react';
import { AllCommunityModule, ModuleRegistry } from 'ag-grid-community';
import type { ColDef } from 'ag-grid-community';
import type React from 'react';
import { BarChart2, TrendingUp, ClipboardList, Package, CheckCircle, Clock, AlertTriangle, Activity } from 'lucide-react';
import * as api from '../../lib/api';
import type { Project, MaintenanceTask, Material } from '../../lib/types';

ModuleRegistry.registerModules([AllCommunityModule]);

interface StatCard { label:string; value:string|number; icon:React.ReactNode; color:string; sub?:string; }

function KpiCard({ label, value, icon, color, sub }: StatCard) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 flex items-center gap-4">
      <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${color}`}>{icon}</div>
      <div>
        <p className="text-2xl font-bold text-gray-900">{value}</p>
        <p className="text-sm text-gray-500">{label}</p>
        {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

function PhaseBar({ phase, count, total }: { phase:string; count:number; total:number }) {
  const pct = total>0 ? Math.round((count/total)*100) : 0;
  const colors: Record<string,string> = { design:'bg-purple-500', validation:'bg-yellow-500', implementation:'bg-blue-500', testing:'bg-orange-500', commissioning:'bg-teal-500', maintenance:'bg-green-500', closed:'bg-gray-400' };
  return (
    <div className="flex items-center gap-3">
      <span className="w-28 text-sm text-gray-600 capitalize shrink-0">{phase}</span>
      <div className="flex-1 bg-gray-100 rounded-full h-3 overflow-hidden">
        <div className={`h-full rounded-full transition-all ${colors[phase]||'bg-blue-500'}`} style={{ width:`${pct}%` }}/>
      </div>
      <span className="text-sm font-semibold text-gray-700 w-8 text-right">{count}</span>
    </div>
  );
}

export default function AnalyticsDashboard() {
  const { t } = useTranslation();
  const [projects, setProjects]   = useState<Project[]>([]);
  const [tasks, setTasks]         = useState<MaintenanceTask[]>([]);
  const [materials, setMaterials] = useState<Material[]>([]);
  const [loading, setLoading]     = useState(true);

  useEffect(() => {
    Promise.all([api.listProjects(), api.listTasks(), api.listMaterials()])
      .then(([p,t,m])=>{ setProjects(p); setTasks(t); setMaterials(m); })
      .catch(console.error).finally(()=>setLoading(false));
  }, []);

  const phaseCounts: Record<string,number> = {};
  projects.forEach(p=>{ phaseCounts[p.phase]=(phaseCounts[p.phase]||0)+1; });
  const taskStatusCounts: Record<string,number> = {};
  tasks.forEach(t=>{ taskStatusCounts[t.status]=(taskStatusCounts[t.status]||0)+1; });
  const priorityCounts: Record<string,number> = {};
  tasks.forEach(t=>{ priorityCounts[t.priority||'medium']=(priorityCounts[t.priority||'medium']||0)+1; });

  const avgProgress = projects.length>0 ? Math.round(projects.reduce((s,p)=>s+p.progress_percent,0)/projects.length) : 0;
  const openTasks = tasks.filter(t=>t.status==='open'||t.status==='in_progress').length;
  const completedTasks = tasks.filter(t=>t.status==='approved').length;

  const kpis: StatCard[] = [
    { label:t('analytics.total_projects','Total Projects'),    value:projects.length,   icon:<Activity className="h-6 w-6 text-blue-600"/>,   color:'bg-blue-50',   sub:`avg ${avgProgress}% progress` },
    { label:t('analytics.open_tasks','Open Tasks'),            value:openTasks,          icon:<Clock className="h-6 w-6 text-yellow-600"/>,     color:'bg-yellow-50' },
    { label:t('analytics.completed_tasks','Completed Tasks'), value:completedTasks,     icon:<CheckCircle className="h-6 w-6 text-green-600"/>, color:'bg-green-50' },
    { label:t('analytics.materials','Material Types'),         value:materials.length,  icon:<Package className="h-6 w-6 text-purple-600"/>,   color:'bg-purple-50' },
  ];

  const phases = ['design','validation','implementation','testing','commissioning','maintenance','closed'];

  // AG Grid col defs for project progress
  const colDefs = useMemo<ColDef<Project>[]>(() => ([
    { field:'name',             headerName:'Project',  flex:2, cellStyle:{fontWeight:500,color:'#111827'} as React.CSSProperties },
    { field:'phase',            headerName:'Phase',    width:130, cellStyle:{textTransform:'capitalize',color:'#6b7280'} as React.CSSProperties },
    {
      field:'progress_percent', headerName:'Progress', width:200,
      cellRenderer:(p:{value:number}) => (
        <div style={{ display:'flex', alignItems:'center', gap:8, width:'100%' }}>
          <div style={{ flex:1, background:'#e5e7eb', borderRadius:999, height:6, overflow:'hidden' }}>
            <div style={{ width:`${p.value}%`, background:'#3b82f6', height:'100%', borderRadius:999 }}/>
          </div>
        </div>
      ),
    },
    { field:'progress_percent', headerName:'%', width:60, type:'numericColumn', cellStyle:{fontWeight:600,color:'#374151'} as React.CSSProperties, valueFormatter:(p:{value:number})=>`${p.value}%` },
  ] as ColDef<Project>[]), []);

  if (loading) return <div className="flex items-center justify-center h-64"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"/></div>;

  return (
    <div className="p-6 space-y-6 overflow-y-auto h-full">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <BarChart2 className="h-6 w-6 text-blue-600"/>{t('analytics.title','Analytics Dashboard')}
        </h1>
        <p className="text-gray-500 text-sm mt-1">{t('analytics.subtitle','Live overview of all projects and operations')}</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {kpis.map((kpi,i)=><KpiCard key={i} {...kpi}/>)}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h2 className="font-semibold text-gray-800 mb-4 flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-blue-500"/>{t('analytics.projects_by_phase','Projects by Phase')}
          </h2>
          <div className="space-y-2.5">{phases.map(phase=><PhaseBar key={phase} phase={phase} count={phaseCounts[phase]||0} total={projects.length}/>)}</div>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h2 className="font-semibold text-gray-800 mb-4 flex items-center gap-2">
            <ClipboardList className="h-4 w-4 text-green-500"/>{t('analytics.tasks_by_status','Tasks by Status')}
          </h2>
          <div className="space-y-3">
            {['open','in_progress','approved','rejected'].map(status=>{
              const count=taskStatusCounts[status]||0;
              const pct=tasks.length>0?Math.round((count/tasks.length)*100):0;
              const colors: Record<string,string> = { open:'bg-blue-500', in_progress:'bg-yellow-500', approved:'bg-green-500', rejected:'bg-red-500' };
              return (
                <div key={status} className="flex items-center gap-3">
                  <span className="w-24 text-sm text-gray-600 capitalize">{status.replace('_',' ')}</span>
                  <div className="flex-1 bg-gray-100 rounded-full h-3 overflow-hidden"><div className={`h-full rounded-full ${colors[status]}`} style={{ width:`${pct}%` }}/></div>
                  <span className="text-sm font-semibold text-gray-700 w-8 text-right">{count}</span>
                </div>
              );
            })}
          </div>
          <h2 className="font-semibold text-gray-800 mb-3 mt-6 flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-orange-500"/>{t('analytics.tasks_by_priority','Tasks by Priority')}
          </h2>
          <div className="grid grid-cols-2 gap-2">
            {['critical','high','medium','low'].map(p=>{
              const c=priorityCounts[p]||0;
              const cls: Record<string,string> = { critical:'bg-red-50 text-red-700 border-red-200', high:'bg-orange-50 text-orange-700 border-orange-200', medium:'bg-yellow-50 text-yellow-700 border-yellow-200', low:'bg-gray-50 text-gray-600 border-gray-200' };
              return <div key={p} className={`rounded-lg border px-3 py-2 ${cls[p]}`}><p className="text-xl font-bold">{c}</p><p className="text-xs capitalize">{p}</p></div>;
            })}
          </div>
        </div>
      </div>

      {/* Project Progress — AG Grid */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="px-5 py-3 border-b border-gray-100">
          <h2 className="font-semibold text-gray-800">{t('analytics.project_progress','Project Progress')}</h2>
        </div>
        <div className="ag-theme-quartz" style={{ width:'100%', height:Math.min(projects.length*37+37+2, 360) }}>
          <AgGridReact
            rowData={projects}
            columnDefs={colDefs}
            defaultColDef={{ resizable:true, sortable:true, suppressHeaderMenuButton:true }}
            domLayout="normal"
            rowHeight={36}
            headerHeight={36}
            suppressCellFocus
          />
        </div>
      </div>
    </div>
  );
}
