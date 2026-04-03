import { useState, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { AgGridReact } from 'ag-grid-react';
import { AllCommunityModule, ModuleRegistry } from 'ag-grid-community';
import type { ColDef } from 'ag-grid-community';
import { Shield, Users, UserPlus } from 'lucide-react';
import DataPageShell from '../../components/layout/DataPageShell';

ModuleRegistry.registerModules([AllCommunityModule]);

interface MockUser { id:number; username:string; display_name:string; role:string; status:string; }

const MOCK_USERS: MockUser[] = [
  { id:1, username:'admin',     display_name:'Admin User',         role:'admin',       status:'Active' },
  { id:2, username:'manager',   display_name:'Project Manager',    role:'manager',     status:'Active' },
  { id:3, username:'tech',      display_name:'Field Technician',   role:'technician',  status:'Active' },
  { id:4, username:'warehouse', display_name:'Warehouse Operator', role:'warehouse',   status:'Active' },
  { id:5, username:'owner',     display_name:'System Owner',       role:'owner',       status:'Active' },
];

const ROLE_BADGE: Record<string, { bg:string; color:string }> = {
  admin:      { bg:'#fee2e2', color:'#dc2626' },
  manager:    { bg:'#dbeafe', color:'#2563eb' },
  technician: { bg:'#dcfce7', color:'#16a34a' },
  warehouse:  { bg:'#fef3c7', color:'#d97706' },
  owner:      { bg:'#ede9fe', color:'#7c3aed' },
};

export default function UserManagement() {
  const { t } = useTranslation();
  const [users] = useState<MockUser[]>(MOCK_USERS);

  const columnDefs = useMemo<ColDef<MockUser>[]>(() => [
    { field:'username',     headerName:t('users.username_col'),  width:160, cellStyle:{ fontWeight:600, color:'#111827' } },
    { field:'display_name', headerName:t('users.display_name'),  flex:1 },
    {
      field:'role', headerName:t('users.role_col'), width:160,
      cellRenderer:(p:{value:string}) => {
        const badge = ROLE_BADGE[p.value] ?? { bg:'#f3f4f6', color:'#6b7280' };
        return (
          <span style={{ display:'inline-flex', alignItems:'center', gap:5, padding:'2px 8px', borderRadius:12, fontSize:11, fontWeight:600, background:badge.bg, color:badge.color }}>
            <Shield size={11}/>{t('roles.'+p.value, p.value)}
          </span>
        );
      },
    },
    {
      field:'status', headerName:t('users.status_col'), width:120,
      cellRenderer:(p:{value:string}) => (
        <span style={{ display:'inline-block', padding:'2px 8px', borderRadius:12, fontSize:11, fontWeight:600, background:'#dcfce7', color:'#16a34a' }}>
          {p.value === 'Active' ? t('common.active') : p.value}
        </span>
      ),
    },
  ], [t]);

  const actions = [
    { icon:<UserPlus size={18}/>, label:t('users.add_user'), variant:'primary' as const, onClick:()=>{} },
  ];

  return (
    <DataPageShell
      title={t('users.title')}
      icon={<Users size={17}/>}
      count={users.length}
      actions={actions}
    >
      <div className="ag-theme-quartz flex-1 min-h-0" style={{ width:'100%' }}>
        <AgGridReact
          rowData={users}
          columnDefs={columnDefs}
          defaultColDef={{ resizable:true, sortable:true, suppressHeaderMenuButton:true }}
          domLayout="normal"
          rowHeight={38}
          headerHeight={36}
          suppressCellFocus
        />
      </div>
    </DataPageShell>
  );
}
