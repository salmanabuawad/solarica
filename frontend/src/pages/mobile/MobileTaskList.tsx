import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { ClipboardList, CheckCircle, Clock, AlertTriangle, ChevronRight, RefreshCw } from 'lucide-react';
import * as api from '../../lib/api';
import type { MaintenanceTask } from '../../lib/types';

interface Props {
  onSelectTask: (taskId: number) => void;
}

const priorityColor: Record<string, string> = {
  critical: 'bg-red-100 text-red-700',
  high:     'bg-orange-100 text-orange-700',
  medium:   'bg-yellow-100 text-yellow-700',
  low:      'bg-gray-100 text-gray-600',
};

const statusIcon: Record<string, React.ReactNode> = {
  open:        <Clock className="h-4 w-4 text-blue-500" />,
  in_progress: <RefreshCw className="h-4 w-4 text-yellow-500" />,
  approved:    <CheckCircle className="h-4 w-4 text-green-500" />,
  rejected:    <AlertTriangle className="h-4 w-4 text-red-500" />,
};

export default function MobileTaskList({ onSelectTask }: Props) {
  const { t } = useTranslation();
  const [tasks, setTasks] = useState<MaintenanceTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<'all' | 'open' | 'in_progress' | 'approved'>('all');

  useEffect(() => {
    api.listTasks().then(setTasks).catch(console.error).finally(() => setLoading(false));
  }, []);

  const filtered = tasks.filter(task => filter === 'all' || task.status === filter);

  return (
    <div className="flex flex-col h-full bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-4 py-3 safe-area-top">
        <div className="flex items-center gap-2 mb-3">
          <ClipboardList className="h-5 w-5 text-blue-600" />
          <h1 className="text-lg font-bold text-gray-900">{t('mobile.my_tasks', 'My Tasks')}</h1>
          <span className="ml-auto text-sm text-gray-500">{filtered.length} {t('mobile.tasks', 'tasks')}</span>
        </div>
        {/* Filter pills */}
        <div className="flex gap-2 overflow-x-auto pb-1">
          {(['all', 'open', 'in_progress', 'approved'] as const).map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1 rounded-full text-xs font-medium whitespace-nowrap transition-colors ${
                filter === f ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {f === 'all' ? t('mobile.all', 'All') :
               f === 'open' ? t('mobile.open', 'Open') :
               f === 'in_progress' ? t('mobile.in_progress', 'In Progress') :
               t('mobile.done', 'Done')}
            </button>
          ))}
        </div>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-2">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-gray-400">
            <ClipboardList className="h-12 w-12 mb-3 opacity-30" />
            <p className="text-sm">{t('mobile.no_tasks', 'No tasks found')}</p>
          </div>
        ) : (
          filtered.map(task => (
            <button
              key={task.id}
              onClick={() => onSelectTask(task.id)}
              className="w-full bg-white rounded-xl border border-gray-200 p-4 text-left hover:border-blue-300 hover:shadow-sm transition-all active:scale-[0.98]"
            >
              <div className="flex items-start gap-3">
                <div className="mt-0.5">{statusIcon[task.status] || <Clock className="h-4 w-4 text-gray-400" />}</div>
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-gray-900 text-sm truncate">{task.title}</p>
                  <p className="text-xs text-gray-500 mt-0.5">{task.site_name} · {task.asset_type} {task.asset_ref || ''}</p>
                  <div className="flex items-center gap-2 mt-2">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium capitalize ${priorityColor[task.priority ?? 'medium'] || 'bg-gray-100 text-gray-600'}`}>
                      {task.priority}
                    </span>
                    <span className="text-xs text-gray-400 capitalize">{task.task_type}</span>
                  </div>
                </div>
                <ChevronRight className="h-4 w-4 text-gray-400 mt-0.5 shrink-0" />
              </div>
            </button>
          ))
        )}
      </div>
    </div>
  );
}
