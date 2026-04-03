import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Loader2, X } from 'lucide-react';
import * as api from '../../lib/api';
import type { TaskCreate as TaskCreatePayload } from '../../lib/types';

interface TaskCreateProps { onClose: () => void; projectId?: string; }

const TASK_TYPES   = ['corrective','preventive','inspection','cleaning'];
const PRIORITIES   = ['low','medium','high','critical'];
const ASSET_TYPES  = ['inverter','string','panel','combiner_box','transformer','meter','other'];

interface FormState {
  title: string; description: string; task_type: string; priority: string;
  assigned_to: string; project_id: string; site_name: string;
  asset_type: string; asset_ref: string;
  requires_approval: boolean; requires_test_result: boolean;
}
const INIT: FormState = {
  title:'', description:'', task_type:'corrective', priority:'medium',
  assigned_to:'', project_id:'', site_name:'', asset_type:'inverter', asset_ref:'',
  requires_approval: false, requires_test_result: false,
};

/* ── Shared style tokens ────────────────────────────────────── */
const inp: React.CSSProperties = { width:'100%', padding:'9px 12px', fontSize:14, color:'#111827', background:'#fff', border:'1px solid #d1d5db', borderRadius:8, outline:'none', boxSizing:'border-box' };
const inpF: React.CSSProperties = { borderColor:'#2563eb', boxShadow:'0 0 0 3px rgba(37,99,235,0.12)' };
const lbl: React.CSSProperties = { display:'block', fontSize:13, fontWeight:500, color:'#374151', marginBottom:5 };
const grid2: React.CSSProperties = { display:'grid', gridTemplateColumns:'1fr 1fr', gap:16 };

function F({ as:Tag='input', style, ...p }: { as?:'input'|'select'|'textarea' } & any) {
  const [f,setF] = useState(false);
  const s = { ...inp, ...(f ? inpF : {}), ...style };
  if (Tag==='select') return <select {...p} style={s} onFocus={()=>setF(true)} onBlur={()=>setF(false)} />;
  if (Tag==='textarea') return <textarea {...p} style={{...s,resize:'none'}} onFocus={()=>setF(true)} onBlur={()=>setF(false)} />;
  return <input {...p} style={s} onFocus={()=>setF(true)} onBlur={()=>setF(false)} />;
}

export default function TaskCreate({ onClose, projectId }: TaskCreateProps) {
  const { t } = useTranslation();
  const [form, setForm]       = useState<FormState>({ ...INIT, project_id: projectId || '' });
  const [submitting, setSub]  = useState(false);
  const [error, setError]     = useState<string | null>(null);

  const up = <K extends keyof FormState>(k: K, v: FormState[K]) => setForm(p => ({ ...p, [k]: v }));

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.title.trim()) { setError('Title is required'); return; }
    if (!form.project_id)   { setError('Project ID is required'); return; }
    setSub(true); setError(null);
    try {
      const payload: TaskCreatePayload = {
        title: form.title.trim(), description: form.description.trim() || undefined,
        task_type: form.task_type, priority: form.priority,
        assigned_to: form.assigned_to.trim() || null,
        project_id: Number(form.project_id),
        site_name: form.site_name.trim() || 'Default Site',
        asset_type: form.asset_type, asset_ref: form.asset_ref.trim() || null,
        requires_approval: form.requires_approval, requires_test_result: form.requires_test_result,
      };
      await api.createTask(payload);
      onClose();
    } catch { setError('Failed to create task. Please try again.'); }
    finally { setSub(false); }
  }

  return (
    <div style={{ position:'fixed', inset:0, zIndex:9500, display:'flex', alignItems:'center', justifyContent:'center', background:'rgba(0,0,0,0.55)', backdropFilter:'blur(3px)', padding:16 }}>
      <div style={{ background:'#fff', borderRadius:16, width:'100%', maxWidth:560, boxShadow:'0 20px 60px rgba(0,0,0,0.2)', display:'flex', flexDirection:'column', maxHeight:'90vh', overflow:'hidden' }}>

        {/* Header */}
        <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', padding:'18px 24px 16px', borderBottom:'1px solid #e5e7eb' }}>
          <h2 style={{ fontSize:17, fontWeight:700, color:'#111827', margin:0 }}>{t('tasks.newTask','New Task')}</h2>
          <button onClick={onClose} style={{ background:'none', border:'none', cursor:'pointer', padding:4, color:'#9ca3af', display:'flex', borderRadius:6 }}><X size={18}/></button>
        </div>

        {/* Body */}
        <form onSubmit={handleSubmit} style={{ flex:1, overflowY:'auto', padding:'20px 24px', display:'flex', flexDirection:'column', gap:16 }}>
          {error && <div style={{ padding:'10px 14px', borderRadius:8, background:'#fef2f2', border:'1px solid #fecaca', color:'#dc2626', fontSize:13 }}>{error}</div>}

          <div><label style={lbl}>{t('tasks.title','Title')} <span style={{color:'#ef4444'}}>*</span></label>
            <F type="text" value={form.title} onChange={(e:any)=>up('title',e.target.value)} placeholder="Task title" autoFocus /></div>

          <div><label style={lbl}>{t('tasks.description','Description')}</label>
            <F as="textarea" value={form.description} onChange={(e:any)=>up('description',e.target.value)} rows={3} placeholder="Optional description…" /></div>

          <div style={grid2}>
            <div><label style={lbl}>{t('tasks.type','Task Type')}</label>
              <F as="select" value={form.task_type} onChange={(e:any)=>up('task_type',e.target.value)}>
                {TASK_TYPES.map(tt=><option key={tt} value={tt}>{tt.charAt(0).toUpperCase()+tt.slice(1)}</option>)}</F></div>
            <div><label style={lbl}>{t('tasks.priority','Priority')}</label>
              <F as="select" value={form.priority} onChange={(e:any)=>up('priority',e.target.value)}>
                {PRIORITIES.map(p=><option key={p} value={p}>{p.charAt(0).toUpperCase()+p.slice(1)}</option>)}</F></div>
          </div>

          <div style={grid2}>
            <div><label style={lbl}>{t('tasks.assignedTo','Assigned To')}</label>
              <F type="text" value={form.assigned_to} onChange={(e:any)=>up('assigned_to',e.target.value)} placeholder="Username" /></div>
            <div><label style={lbl}>Project ID <span style={{color:'#ef4444'}}>*</span></label>
              <F type="number" value={form.project_id} onChange={(e:any)=>up('project_id',e.target.value)} placeholder="1" /></div>
          </div>

          <div style={grid2}>
            <div><label style={lbl}>Site Name</label>
              <F type="text" value={form.site_name} onChange={(e:any)=>up('site_name',e.target.value)} placeholder="Site name" /></div>
            <div><label style={lbl}>Asset Type</label>
              <F as="select" value={form.asset_type} onChange={(e:any)=>up('asset_type',e.target.value)}>
                {ASSET_TYPES.map(at=><option key={at} value={at}>{at.replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase())}</option>)}</F></div>
          </div>

          <div><label style={lbl}>Asset Reference</label>
            <F type="text" value={form.asset_ref} onChange={(e:any)=>up('asset_ref',e.target.value)} placeholder="e.g. INV-01" /></div>

          {/* Checkboxes */}
          <div style={{ display:'flex', gap:24 }}>
            {([['requires_approval','Requires Approval'],['requires_test_result','Requires Test Result']] as const).map(([k,label])=>(
              <label key={k} style={{ display:'flex', alignItems:'center', gap:8, fontSize:13, color:'#374151', cursor:'pointer' }}>
                <input type="checkbox" checked={form[k]} onChange={e=>up(k,e.target.checked)}
                  style={{ width:16, height:16, accentColor:'#2563eb', cursor:'pointer' }} />
                {label}
              </label>
            ))}
          </div>

          {/* Footer */}
          <div style={{ display:'flex', alignItems:'center', justifyContent:'flex-end', gap:10, paddingTop:12, borderTop:'1px solid #e5e7eb', marginTop:4 }}>
            <button type="button" onClick={onClose} style={{ background:'none', border:'none', cursor:'pointer', fontSize:14, color:'#6b7280', padding:'8px 12px' }}>
              {t('common.cancel','Cancel')}
            </button>
            <button type="submit" disabled={submitting}
              style={{ display:'flex', alignItems:'center', gap:6, padding:'9px 24px', background: submitting?'#6b7280':'#2563eb', color:'#fff', border:'none', borderRadius:8, fontSize:14, fontWeight:600, cursor:submitting?'not-allowed':'pointer', opacity:submitting?0.7:1 }}>
              {submitting && <Loader2 size={15} className="animate-spin"/>}
              {t('tasks.create','Create Task')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
