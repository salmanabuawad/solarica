import { useState, useEffect, useMemo, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { AgGridReact } from 'ag-grid-react';
import { AllCommunityModule, ModuleRegistry } from 'ag-grid-community';
import type { ColDef } from 'ag-grid-community';
import { Loader2, Package, Plus, X } from 'lucide-react';
import * as api from '../../lib/api';
import type { Material, MaterialCreate } from '../../lib/types';
import DataPageShell from '../../components/layout/DataPageShell';
import { useFieldConfig } from '../../lib/useFieldConfig';

ModuleRegistry.registerModules([AllCommunityModule]);

const EMPTY: MaterialCreate = { name:'', category:'', unit:'pcs', sku:'', min_threshold:0, unit_cost:0 };

const inp: React.CSSProperties = { width:'100%', padding:'8px 10px', fontSize:13, color:'#111827', background:'#fff', border:'1px solid #d1d5db', borderRadius:6, outline:'none', boxSizing:'border-box' };

export default function MaterialList() {
  const { t } = useTranslation();
  const [materials, setMaterials] = useState<Material[]>([]);
  const [loading, setLoading]     = useState(true);
  const [showAdd, setShowAdd]     = useState(false);
  const [form, setForm]           = useState<MaterialCreate>({ ...EMPTY });
  const [saving, setSaving]       = useState(false);
  const [error, setError]         = useState<string | null>(null);
  const [search, setSearch]       = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try { setMaterials(await api.listMaterials()); }
    catch(e) { console.error(e); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function handleSave() {
    if (!form.name.trim()) { setError(t('common.name') + ' is required'); return; }
    setSaving(true); setError(null);
    try {
      await api.createMaterial({ name:form.name.trim(), category:form.category?.trim()||null, unit:form.unit, sku:form.sku?.trim()||null, min_threshold:form.min_threshold??0, unit_cost:form.unit_cost??null });
      setForm({ ...EMPTY }); setShowAdd(false); await load();
    } catch { setError('Failed to save material.'); }
    finally { setSaving(false); }
  }

  const defaultMaterialCols = useMemo<ColDef<Material>[]>(() => [
    { field:'name',          headerName: t('common.name'),             flex:2,  filter:true },
    { field:'category',      headerName: t('inventory.category'),      flex:1.5 },
    { field:'unit',          headerName: t('inventory.unit'),          width:80 },
    { field:'sku',           headerName: t('inventory.sku'),           flex:1 },
    { field:'min_threshold', headerName: t('inventory.min_threshold'), flex:1, type:'numericColumn' },
    { field:'unit_cost',     headerName: t('inventory.unit_cost'),     flex:1, type:'numericColumn',
      valueFormatter: p => p.value != null ? `$${Number(p.value).toFixed(2)}` : '—' },
  ], [t]);

  const columnDefs = useFieldConfig('materials', defaultMaterialCols);

  const filtered = useMemo(() => {
    if (!search) return materials;
    const q = search.toLowerCase();
    return materials.filter(m => m.name.toLowerCase().includes(q) || m.category?.toLowerCase().includes(q));
  }, [materials, search]);

  const actions = [
    { icon:<Plus size={18}/>,  label: t('inventory.add_material'), variant:'primary' as const, onClick:()=>setShowAdd(v=>!v) },
    { icon:<X size={18}/>,     label: t('common.cancel'),          onClick:()=>setShowAdd(false), disabled:!showAdd },
  ];

  return (
    <DataPageShell
      title={t('inventory.materials')}
      icon={<Package size={17}/>}
      count={materials.length}
      actions={actions}
      searchValue={search}
      searchPlaceholder={t('common.search') + '...'}
      onSearchChange={setSearch}
    >
      <div style={{ display:'flex', flexDirection:'column', height:'100%' }}>

        {/* Inline add form */}
        {showAdd && (
          <div style={{ padding:'12px 16px', background:'#f9fafb', borderBottom:'1px solid #e5e7eb' }}>
            {error && <div style={{ padding:'8px 12px', borderRadius:6, background:'#fef2f2', border:'1px solid #fecaca', color:'#dc2626', fontSize:13, marginBottom:10 }}>{error}</div>}
            <div style={{ display:'grid', gridTemplateColumns:'repeat(3,1fr)', gap:10, marginBottom:10 }}>
              <input style={inp} placeholder={t('common.name') + ' *'}       value={form.name}            onChange={e=>setForm(f=>({...f,name:e.target.value}))} />
              <input style={inp} placeholder={t('inventory.category')}       value={form.category||''}    onChange={e=>setForm(f=>({...f,category:e.target.value}))} />
              <input style={inp} placeholder={t('inventory.unit')}           value={form.unit}            onChange={e=>setForm(f=>({...f,unit:e.target.value}))} />
              <input style={inp} placeholder={t('inventory.sku')}            value={form.sku||''}         onChange={e=>setForm(f=>({...f,sku:e.target.value}))} />
              <input style={inp} placeholder={t('inventory.min_threshold')}  type="number" value={form.min_threshold??0} onChange={e=>setForm(f=>({...f,min_threshold:Number(e.target.value)}))} />
              <input style={inp} placeholder={t('inventory.unit_cost')}      type="number" step="0.01" value={form.unit_cost??''} onChange={e=>setForm(f=>({...f,unit_cost:e.target.value?Number(e.target.value):null}))} />
            </div>
            <div style={{ display:'flex', justifyContent:'flex-end', gap:8 }}>
              <button onClick={()=>setShowAdd(false)} style={{ padding:'7px 14px', background:'none', border:'1px solid #d1d5db', borderRadius:6, fontSize:13, cursor:'pointer', color:'#374151' }}>{t('common.cancel')}</button>
              <button onClick={handleSave} disabled={saving}
                style={{ padding:'7px 16px', background:saving?'#6b7280':'#16a34a', color:'#fff', border:'none', borderRadius:6, fontSize:13, fontWeight:600, cursor:saving?'not-allowed':'pointer', display:'flex', alignItems:'center', gap:6 }}>
                {saving && <Loader2 size={14} className="animate-spin"/>} {t('common.save')}
              </button>
            </div>
          </div>
        )}

        {/* Grid */}
        <div style={{ flex:1, minHeight:0 }}>
          {loading ? (
            <div style={{ display:'flex', alignItems:'center', justifyContent:'center', height:200 }}>
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"/>
            </div>
          ) : (
            <div className="ag-theme-quartz" style={{ height:'100%', width:'100%' }}>
              <AgGridReact<Material> rowData={filtered} columnDefs={columnDefs} animateRows pagination paginationPageSize={20} paginationPageSizeSelector={[20,50,100]} rowSelection={{ mode:'multiRow', checkboxes:true, headerCheckbox:true }} />
            </div>
          )}
        </div>
      </div>
    </DataPageShell>
  );
}
