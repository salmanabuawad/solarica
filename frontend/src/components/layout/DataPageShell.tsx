/**
 * DataPageShell — standard 3-zone layout for all list/grid pages.
 *   1. Page-header strip  (title + count)
 *   2. Action bar         (icon-above-label buttons + search)
 *   3. Full-height content (AG Grid or any child)
 */
import type { ReactNode } from 'react';
import { Search } from 'lucide-react';

export interface ToolbarAction {
  icon:      ReactNode;
  label:     string;
  onClick:   () => void;
  variant?:  'default' | 'primary' | 'danger';
  disabled?: boolean;
}

interface DataPageShellProps {
  title:              string;
  icon?:              ReactNode;
  count?:             number;
  actions?:           ToolbarAction[];
  searchValue?:       string;
  searchPlaceholder?: string;
  onSearchChange?:    (value: string) => void;
  toolbarExtra?:      ReactNode;
  children:           ReactNode;
}

const COLOR: Record<string, string> = {
  default: '#374151',
  primary: '#2563eb',
  danger:  '#dc2626',
};

export default function DataPageShell({
  title, icon, count, actions = [],
  searchValue, searchPlaceholder = 'Search…', onSearchChange,
  toolbarExtra, children,
}: DataPageShellProps) {
  return (
    <div style={{ display:'flex', flexDirection:'column', flex:1, minHeight:0, overflow:'hidden' }}>

      {/* 1. Page header */}
      <div className="page-header px-4 py-2 flex items-center gap-2.5 shrink-0">
        {icon && (
          <div className="page-header-icon">{icon}</div>
        )}
        <span className="page-header-title">{title}</span>
        {count !== undefined && (
          <span className="page-header-badge page-header-badge-default ml-1">
            {count}
          </span>
        )}
      </div>

      {/* 2. Action bar */}
      <div className="action-bar mx-3 mt-2 mb-1 shrink-0">
        {actions.map((action, i) => (
          <button
            key={i}
            onClick={action.onClick}
            disabled={action.disabled}
            className="btn-action"
            style={{
              color:   action.disabled ? '#9ca3af' : COLOR[action.variant ?? 'default'],
              opacity: action.disabled ? 0.5 : 1,
              cursor:  action.disabled ? 'not-allowed' : 'pointer',
            }}
          >
            <span style={{ display:'flex', alignItems:'center', justifyContent:'center' }}>
              {action.icon}
            </span>
            <span style={{ fontSize: 11, fontWeight: 500, whiteSpace:'nowrap' }}>
              {action.label}
            </span>
          </button>
        ))}

        {toolbarExtra && (
          <div style={{ display:'flex', alignItems:'center', gap:8, marginLeft:4 }}>
            {toolbarExtra}
          </div>
        )}

        <div style={{ flex:1 }} />

        {onSearchChange !== undefined && (
          <div style={{ position:'relative' }}>
            <Search size={13} style={{ position:'absolute', left:8, top:'50%', transform:'translateY(-50%)', color:'#9ca3af', pointerEvents:'none' }} />
            <input
              type="text"
              value={searchValue ?? ''}
              onChange={e => onSearchChange(e.target.value)}
              placeholder={searchPlaceholder}
              className="input-base"
              style={{ paddingLeft:28, paddingRight:10, paddingTop:5, paddingBottom:5, width:200, fontSize:12 }}
            />
          </div>
        )}
      </div>

      {/* 3. Content — flex-1 min-h-0 flex flex-col so children can use flex-1 to fill */}
      <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
        {children}
      </div>
    </div>
  );
}
