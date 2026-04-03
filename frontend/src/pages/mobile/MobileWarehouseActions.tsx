import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Package, ArrowDownToLine, ArrowUpFromLine, BarChart3, Loader2, CheckCircle } from 'lucide-react';
import * as api from '../../lib/api';
import type { Material } from '../../lib/types';

type Action = 'view' | 'receive' | 'issue';

export default function MobileWarehouseActions() {
  const { t } = useTranslation();
  const [action, setAction] = useState<Action>('view');
  const [materials, setMaterials] = useState<Material[]>([]);
  const [loading, setLoading] = useState(true);
  const [success, setSuccess] = useState<string | null>(null);

  // Issue form
  const [issueMaterialId, setIssueMaterialId] = useState('');
  const [issueQty, setIssueQty] = useState('');
  const [issueTo, setIssueTo] = useState('');
  const [issueProjectId, setIssueProjectId] = useState('1');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api.listMaterials().then(setMaterials).catch(console.error).finally(() => setLoading(false));
  }, []);

  async function handleIssue() {
    if (!issueMaterialId || !issueQty || !issueTo) return;
    setSubmitting(true);
    try {
      const mat = materials.find(m => m.id === Number(issueMaterialId));
      if (!mat) throw new Error('Material not found');
      await api.issueMaterial({
        project_id: Number(issueProjectId),
        warehouse_name: 'Main Warehouse',
        issued_to_user: issueTo,
        issued_by_user: 'warehouse',
        expected_usage_days: 30,
        items: [{ material_name: mat.name, quantity_issued: Number(issueQty), unit: mat.unit }],
      });
      setSuccess(`Issued ${issueQty} ${mat.unit} of ${mat.name}`);
      setIssueMaterialId('');
      setIssueQty('');
      setIssueTo('');
      setTimeout(() => setSuccess(null), 3000);
    } catch (e) { console.error(e); }
    finally { setSubmitting(false); }
  }

  return (
    <div className="flex flex-col h-full bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-4 py-3">
        <div className="flex items-center gap-2 mb-3">
          <Package className="h-5 w-5 text-indigo-600" />
          <h1 className="text-lg font-bold text-gray-900">{t('mobile.warehouse', 'Warehouse')}</h1>
        </div>
        <div className="flex gap-1">
          {([
            { id: 'view',    label: t('mobile.stock', 'Stock'),   icon: <BarChart3 className="h-3.5 w-3.5" /> },
            { id: 'issue',   label: t('mobile.issue', 'Issue'),   icon: <ArrowUpFromLine className="h-3.5 w-3.5" /> },
            { id: 'receive', label: t('mobile.receive', 'Receive'), icon: <ArrowDownToLine className="h-3.5 w-3.5" /> },
          ] as { id: Action; label: string; icon: React.ReactNode }[]).map(btn => (
            <button
              key={btn.id}
              onClick={() => setAction(btn.id)}
              className={`flex-1 py-1.5 rounded text-xs font-medium flex items-center justify-center gap-1 transition-colors ${
                action === btn.id ? 'bg-indigo-600 text-white' : 'bg-gray-100 text-gray-600'
              }`}
            >
              {btn.icon} {btn.label}
            </button>
          ))}
        </div>
      </div>

      {/* Success toast */}
      {success && (
        <div className="mx-4 mt-3 bg-green-50 border border-green-200 rounded-xl p-3 flex items-center gap-2">
          <CheckCircle className="h-4 w-4 text-green-600 shrink-0" />
          <span className="text-sm text-green-700">{success}</span>
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-4 py-3">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600" />
          </div>
        ) : action === 'view' ? (
          <div className="space-y-2">
            <p className="text-xs text-gray-500 mb-3">{t('mobile.materials_catalog', 'Materials Catalog')}</p>
            {materials.map(mat => (
              <div key={mat.id} className="bg-white rounded-xl border border-gray-200 p-3">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="font-semibold text-gray-900 text-sm">{mat.name}</p>
                    <p className="text-xs text-gray-500 mt-0.5">
                      SKU: {mat.sku || '-'} · Unit: {mat.unit}
                    </p>
                  </div>
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                    mat.category === 'module' ? 'bg-blue-100 text-blue-700' :
                    mat.category === 'inverter' ? 'bg-purple-100 text-purple-700' :
                    mat.category === 'cable' ? 'bg-yellow-100 text-yellow-700' :
                    'bg-gray-100 text-gray-600'
                  } capitalize`}>
                    {mat.category || 'other'}
                  </span>
                </div>
                {mat.unit_cost && (
                  <p className="text-xs text-gray-400 mt-1.5">Unit cost: €{mat.unit_cost.toFixed(2)}</p>
                )}
              </div>
            ))}
          </div>
        ) : action === 'issue' ? (
          <div className="space-y-3">
            <div>
              <label className="text-xs font-medium text-gray-700 block mb-1">{t('mobile.material', 'Material')}</label>
              <select
                value={issueMaterialId}
                onChange={e => setIssueMaterialId(e.target.value)}
                className="w-full border border-gray-300 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="">{t('mobile.select_material', 'Select material…')}</option>
                {materials.map(m => (
                  <option key={m.id} value={m.id}>{m.name} ({m.unit})</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-gray-700 block mb-1">{t('mobile.quantity', 'Quantity')}</label>
              <input
                type="number"
                value={issueQty}
                onChange={e => setIssueQty(e.target.value)}
                placeholder="0"
                min="0"
                className="w-full border border-gray-300 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-gray-700 block mb-1">{t('mobile.issue_to', 'Issue to (username)')}</label>
              <input
                type="text"
                value={issueTo}
                onChange={e => setIssueTo(e.target.value)}
                placeholder="tech"
                className="w-full border border-gray-300 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-gray-700 block mb-1">{t('mobile.project_id', 'Project ID')}</label>
              <input
                type="number"
                value={issueProjectId}
                onChange={e => setIssueProjectId(e.target.value)}
                className="w-full border border-gray-300 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            <button
              onClick={handleIssue}
              disabled={submitting || !issueMaterialId || !issueQty || !issueTo}
              className="w-full py-3 bg-indigo-600 text-white rounded-xl text-sm font-medium disabled:opacity-50 hover:bg-indigo-700 transition-colors flex items-center justify-center gap-2"
            >
              {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowUpFromLine className="h-4 w-4" />}
              {t('mobile.confirm_issue', 'Confirm Issue')}
            </button>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center py-16 text-gray-400">
            <ArrowDownToLine className="h-12 w-12 mb-3 opacity-30" />
            <p className="text-sm text-center">{t('mobile.receive_info', 'Use the warehouse receive endpoint or scanner to receive stock')}</p>
          </div>
        )}
      </div>
    </div>
  );
}
