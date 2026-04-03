import { useState, useEffect, useMemo, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { AgGridReact } from 'ag-grid-react';
import { AllCommunityModule, ModuleRegistry } from 'ag-grid-community';
import type { ColDef } from 'ag-grid-community';
import type React from 'react';
import { Cpu, Plus, RefreshCcw, X } from 'lucide-react';
import * as api from '../../lib/api';
import DataPageShell from '../../components/layout/DataPageShell';

ModuleRegistry.registerModules([AllCommunityModule]);

interface Device {
  id:string; project_id:string; device_name:string; device_type:string; manufacturer:string; model:string;
  firmware_version:string|null; ip_address:string|null; mac_address:string|null; protocol:string|null;
  network_zone:string|null; location:string|null; notes:string|null; status:string;
  last_scan_date:string|null; vulnerability_count:number; risk_score:number|null; created_at:string;
}

const DEVICE_TYPES   = ['inverter','meter','gateway','scada','plc','rtu','sensor','camera','router','switch'];
const PROTOCOLS      = ['modbus','sunspec','mqtt','opcua','bacnet','dnp3','iec61850'];
const NETWORK_ZONES  = ['ot_field','ot_control','dmz','it_corporate'];
const WIRELESS_IFACES= ['wifi','bluetooth','zigbee','lora','cellular'];

const fi: React.CSSProperties = { width:'100%', padding:'7px 10px', fontSize:13, color:'#111827', background:'#fff', border:'1px solid #d1d5db', borderRadius:6, outline:'none', boxSizing:'border-box' };
const lb: React.CSSProperties = { display:'block', fontSize:12, fontWeight:500, color:'#374151', marginBottom:4 };

const emptyForm = { project_id:'', device_name:'', device_type:'inverter', manufacturer:'', model:'', firmware_version:'', ip_address:'', mac_address:'', protocol:'', network_zone:'', location:'', wireless_interfaces:'', notes:'' };

const riskColor = (score:number|null) => !score||score===0 ? '#16a34a' : score<4 ? '#d97706' : score<7 ? '#ea580c' : '#dc2626';
const STATUS_BADGE: Record<string,{bg:string;color:string}> = {
  active:         { bg:'#dcfce7', color:'#16a34a' },
  inactive:       { bg:'#f3f4f6', color:'#6b7280' },
  decommissioned: { bg:'#fee2e2', color:'#dc2626' },
};

export default function DeviceRegistry() {
  const { t } = useTranslation();
  const [devices, setDevices]   = useState<Device[]>([]);
  const [loading, setLoading]   = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm]         = useState({ ...emptyForm });
  const [submitting, setSub]    = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try { setDevices(await api.listSecurityDevices()); } catch(e) { console.error(e); } finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const up = (field:string, value:string) => setForm(p=>({ ...p, [field]:value }));

  const handleSubmit = async (e:React.FormEvent) => {
    e.preventDefault(); setSub(true);
    try {
      const wirelessArr = form.wireless_interfaces ? form.wireless_interfaces.split(',').map(s=>s.trim()).filter(Boolean) : null;
      await api.registerSecurityDevice({ ...form, firmware_version:form.firmware_version||null, ip_address:form.ip_address||null, mac_address:form.mac_address||null, protocol:form.protocol||null, network_zone:form.network_zone||null, location:form.location||null, wireless_interfaces:wirelessArr, notes:form.notes||null });
      setForm({ ...emptyForm }); setShowForm(false); await load();
    } catch(e) { console.error(e); } finally { setSub(false); }
  };

  const columnDefs = useMemo<ColDef<Device>[]>(() => ([
    { field:'device_name',        headerName:t('common.name'),            width:160, cellStyle:{fontWeight:600,color:'#111827'} as React.CSSProperties },
    { field:'device_type',        headerName:t('security.device_type'),   width:100, cellStyle:{textTransform:'uppercase',fontSize:11,fontWeight:600,color:'#6b7280'} as React.CSSProperties },
    { field:'manufacturer',       headerName:t('security.manufacturer'),  width:140 },
    { field:'model',              headerName:'Model',                      width:160 },
    { field:'firmware_version',   headerName:t('security.firmware'),      width:110, valueFormatter:(p:{value:string|null})=>p.value||'—', cellStyle:{color:'#6b7280'} as React.CSSProperties },
    { field:'ip_address',         headerName:t('security.ip_address'),    width:130, valueFormatter:(p:{value:string|null})=>p.value||'—', cellStyle:{fontFamily:'monospace',fontSize:12,color:'#6b7280'} as React.CSSProperties },
    { field:'network_zone',       headerName:t('security.network_zone'),  width:120, valueFormatter:(p:{value:string|null})=>p.value?p.value.replace('_',' ').toUpperCase():'—', cellStyle:{fontSize:12,color:'#6b7280'} as React.CSSProperties },
    {
      field:'risk_score', headerName:t('security.risk'), width:80, type:'numericColumn',
      cellRenderer:(p:{value:number|null}) => <span style={{ fontWeight:700, color:riskColor(p.value) }}>{p.value!=null?p.value.toFixed(1):'0.0'}</span>,
    },
    {
      field:'vulnerability_count', headerName:t('security.vulns_col'), width:80, type:'numericColumn',
      cellRenderer:(p:{value:number}) => <span style={{ display:'inline-block', padding:'2px 8px', borderRadius:12, fontSize:11, fontWeight:700, background:p.value>0?'#fee2e2':'#dcfce7', color:p.value>0?'#dc2626':'#16a34a' }}>{p.value}</span>,
    },
    {
      field:'status', headerName:t('common.status'), width:110,
      cellRenderer:(p:{value:string}) => { const c=STATUS_BADGE[p.value]??{bg:'#f3f4f6',color:'#6b7280'}; return <span style={{ display:'inline-block', padding:'2px 8px', borderRadius:12, fontSize:11, fontWeight:600, background:c.bg, color:c.color }}>{t('statuses.'+p.value, p.value)}</span>; },
    },
  ] as ColDef<Device>[]), [t]);

  const actions = [
    { icon:showForm?<X size={18}/>:<Plus size={18}/>, label:showForm?t('common.cancel'):t('security.register_device'), variant:'primary' as const, onClick:()=>setShowForm(v=>!v) },
    { icon:<RefreshCcw size={18}/>, label:t('common.refresh'), onClick:load },
  ];

  return (
    <DataPageShell
      title={t('security.devices')}
      icon={<Cpu size={17}/>}
      count={devices.length}
      actions={actions}
    >
      {/* Registration form */}
      {showForm && (
        <div className="shrink-0" style={{ margin:'0 0 0 0', padding:'12px 16px', background:'#f9fafb', borderBottom:'1px solid #e5e7eb' }}>
          <div style={{ fontSize:13, fontWeight:600, color:'#111827', marginBottom:10 }}>{t('security.register_new_device')}</div>
          <form onSubmit={handleSubmit}>
            <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:8, marginBottom:10 }}>
              <div><label style={lb}>{t('inventory.project_id')} *</label><input style={fi} required value={form.project_id} onChange={e=>up('project_id',e.target.value)} placeholder="PROJ-001"/></div>
              <div><label style={lb}>{t('common.name')} *</label><input style={fi} required value={form.device_name} onChange={e=>up('device_name',e.target.value)} placeholder="INV-A1"/></div>
              <div><label style={lb}>{t('security.device_type')} *</label>
                <select style={fi} required value={form.device_type} onChange={e=>up('device_type',e.target.value)}>
                  {DEVICE_TYPES.map(t=><option key={t} value={t}>{t.toUpperCase()}</option>)}
                </select></div>
              <div><label style={lb}>{t('security.manufacturer')} *</label><input style={fi} required value={form.manufacturer} onChange={e=>up('manufacturer',e.target.value)} placeholder="SMA"/></div>
              <div><label style={lb}>Model *</label><input style={fi} required value={form.model} onChange={e=>up('model',e.target.value)} placeholder="Sunny Tripower"/></div>
              <div><label style={lb}>{t('security.firmware')}</label><input style={fi} value={form.firmware_version} onChange={e=>up('firmware_version',e.target.value)} placeholder="v3.10.15"/></div>
              <div><label style={lb}>{t('security.ip_address')}</label><input style={fi} value={form.ip_address} onChange={e=>up('ip_address',e.target.value)} placeholder="192.168.1.100"/></div>
              <div><label style={lb}>{t('security.protocol')}</label>
                <select style={fi} value={form.protocol} onChange={e=>up('protocol',e.target.value)}>
                  <option value="">{t('common.none')}</option>
                  {PROTOCOLS.map(p=><option key={p} value={p}>{p.toUpperCase()}</option>)}
                </select></div>
              <div><label style={lb}>{t('security.network_zone')}</label>
                <select style={fi} value={form.network_zone} onChange={e=>up('network_zone',e.target.value)}>
                  <option value="">{t('common.none')}</option>
                  {NETWORK_ZONES.map(z=><option key={z} value={z}>{z.replace('_',' ').toUpperCase()}</option>)}
                </select></div>
              <div><label style={lb}>Location</label><input style={fi} value={form.location} onChange={e=>up('location',e.target.value)} placeholder="Array Block A"/></div>
              <div><label style={lb}>Wireless ({WIRELESS_IFACES.join(',')})</label><input style={fi} value={form.wireless_interfaces} onChange={e=>up('wireless_interfaces',e.target.value)}/></div>
              <div><label style={lb}>{t('common.notes')}</label><input style={fi} value={form.notes} onChange={e=>up('notes',e.target.value)}/></div>
            </div>
            <div style={{ display:'flex', justifyContent:'flex-end', gap:8 }}>
              <button type="button" onClick={()=>setShowForm(false)} style={{ padding:'6px 14px', background:'none', border:'1px solid #d1d5db', borderRadius:6, fontSize:13, cursor:'pointer', color:'#374151' }}>{t('common.cancel')}</button>
              <button type="submit" disabled={submitting} style={{ padding:'6px 20px', background:submitting?'#6b7280':'#2563eb', color:'#fff', border:'none', borderRadius:6, fontSize:13, fontWeight:600, cursor:submitting?'not-allowed':'pointer' }}>
                {submitting ? t('security.registering') : t('security.register_device')}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Grid */}
      {loading ? (
        <div style={{ flex:1, display:'flex', alignItems:'center', justifyContent:'center', color:'#9ca3af', fontSize:13 }}>Loading…</div>
      ) : (
        <div className="ag-theme-quartz flex-1 min-h-0" style={{ width:'100%' }}>
          <AgGridReact
            rowData={devices}
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
