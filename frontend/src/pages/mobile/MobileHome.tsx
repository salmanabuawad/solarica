import { useTranslation } from 'react-i18next';
import { useState, useEffect } from 'react';
import {
  AlertTriangle, Box, ClipboardCheck, FolderKanban,
  Gauge, Package, Settings, Wrench, CheckSquare,
} from 'lucide-react';
import * as api from '../../lib/api';
import type { MobileHomeResponse, MobileSummary } from '../../lib/types';

interface MobileHomeProps {
  role: string;
}

const CARD_ICONS: Record<string, React.ReactNode> = {
  'my tasks':          <ClipboardCheck className="h-8 w-8" />,
  'my projects':       <FolderKanban className="h-8 w-8" />,
  'daily report':      <Gauge className="h-8 w-8" />,
  'upload evidence':   <Gauge className="h-8 w-8" />,
  'materials':         <Package className="h-8 w-8" />,
  'dashboard':         <FolderKanban className="h-8 w-8" />,
  'approvals':         <CheckSquare className="h-8 w-8" />,
  'alerts':            <AlertTriangle className="h-8 w-8" />,
  'tasks':             <ClipboardCheck className="h-8 w-8" />,
  'inventory':         <Package className="h-8 w-8" />,
  'issue material':    <Box className="h-8 w-8" />,
  'receive return':    <Box className="h-8 w-8" />,
  'open transactions': <Box className="h-8 w-8" />,
  'low stock alerts':  <AlertTriangle className="h-8 w-8" />,
  'reports':           <Gauge className="h-8 w-8" />,
  'progress summary':  <Gauge className="h-8 w-8" />,
  'system status':     <Settings className="h-8 w-8" />,
  'projects':          <FolderKanban className="h-8 w-8" />,
  'users':             <Settings className="h-8 w-8" />,
  'integrations':      <Settings className="h-8 w-8" />,
  'maintenance':       <Wrench className="h-8 w-8" />,
  'warehouse':         <Box className="h-8 w-8" />,
};

const CARD_COLORS: Record<string, string> = {
  'my tasks':          'bg-green-500',
  'my projects':       'bg-blue-500',
  'approvals':         'bg-indigo-500',
  'alerts':            'bg-red-500',
  'tasks':             'bg-green-500',
  'inventory':         'bg-amber-500',
  'issue material':    'bg-teal-500',
  'open transactions': 'bg-teal-600',
  'low stock alerts':  'bg-red-500',
  'reports':           'bg-purple-500',
  'progress summary':  'bg-blue-500',
  'dashboard':         'bg-blue-600',
  'system status':     'bg-gray-600',
  'projects':          'bg-blue-500',
};

// Map card names → summary field keys
const CARD_COUNT_KEY: Record<string, keyof MobileSummary> = {
  'my tasks':          'open_tasks',
  'tasks':             'open_tasks',
  'approvals':         'pending_approvals',
  'alerts':            'open_flags',
  'low stock alerts':  'low_stock_items',
  'open transactions': 'open_issues',
  'inventory':         'low_stock_items',
  'my projects':       'active_projects',
  'projects':          'active_projects',
};

export default function MobileHome({ role }: MobileHomeProps) {
  const { t } = useTranslation();
  const [data, setData]         = useState<MobileHomeResponse | null>(null);
  const [summary, setSummary]   = useState<MobileSummary | null>(null);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        setLoading(true);
        const [home, sum] = await Promise.allSettled([
          api.getMobileHome(role),
          api.getMobileSummary(role),
        ]);
        if (home.status === 'fulfilled') setData(home.value);
        if (sum.status === 'fulfilled')  setSummary(sum.value);
      } catch (err) {
        console.error('Failed to load mobile home:', err);
        setError('Failed to load home screen');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [role]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-50">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-screen bg-gray-50 px-6">
        <AlertTriangle className="h-12 w-12 text-red-400 mb-3" />
        <p className="text-red-600 text-center">{error}</p>
      </div>
    );
  }

  const cards = data?.cards || [];

  // Summary badges
  const summaryBadges = summary ? [
    summary.open_tasks > 0        && { label: `${summary.open_tasks} open tasks`,               color: '#16a34a' },
    summary.pending_approvals > 0 && { label: `${summary.pending_approvals} pending approvals`, color: '#2563eb' },
    summary.open_flags > 0        && { label: `${summary.open_flags} open flags`,               color: '#dc2626' },
    summary.low_stock_items > 0   && { label: `${summary.low_stock_items} low stock`,           color: '#d97706' },
  ].filter(Boolean) : [];

  return (
    <div className="min-h-screen bg-gray-50 pb-8">
      {/* Header */}
      <div className="bg-blue-600 text-white px-6 pt-12 pb-8">
        <h1 className="text-2xl font-bold">Solarica</h1>
        <p className="text-blue-100 text-sm mt-1">
          {t('mobile.welcome', 'Welcome back')} · {role.charAt(0).toUpperCase() + role.slice(1)}
        </p>
        {/* Summary badges */}
        {summaryBadges.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {(summaryBadges as { label: string; color: string }[]).map((b, i) => (
              <span key={i} style={{
                display: 'inline-block', padding: '3px 10px', borderRadius: 20,
                fontSize: 12, fontWeight: 600,
                background: 'rgba(255,255,255,0.18)', color: '#fff',
                border: '1px solid rgba(255,255,255,0.3)',
              }}>
                {b.label}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Cards Grid */}
      <div className="px-4 -mt-4">
        <div className="grid grid-cols-2 gap-4">
          {cards.map((card) => {
            const cardKey = card.toLowerCase();
            const countKey = CARD_COUNT_KEY[cardKey];
            const count = countKey && summary ? summary[countKey] : undefined;
            return (
              <button
                key={card}
                className="bg-white rounded-xl shadow-sm p-5 text-left active:scale-95 transition-transform touch-manipulation relative"
              >
                {/* Count badge */}
                {count !== undefined && count > 0 && (
                  <span style={{
                    position: 'absolute', top: 10, right: 10,
                    background: '#dc2626', color: '#fff',
                    fontSize: 11, fontWeight: 700,
                    padding: '1px 7px', borderRadius: 10,
                    minWidth: 20, textAlign: 'center',
                  }}>
                    {count}
                  </span>
                )}
                <div className={`w-14 h-14 rounded-lg flex items-center justify-center text-white mb-3 ${CARD_COLORS[cardKey] || 'bg-gray-500'}`}>
                  {CARD_ICONS[cardKey] || <FolderKanban className="h-8 w-8" />}
                </div>
                <p className="font-semibold text-gray-900 text-base">
                  {card}
                </p>
                {count !== undefined && count > 0 && (
                  <p className="text-xs mt-0.5 font-medium" style={{ color: '#dc2626' }}>
                    {count} item{count !== 1 ? 's' : ''} need attention
                  </p>
                )}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
