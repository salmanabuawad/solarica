import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import * as api from '../../lib/api';
import type { ApprovedStringPattern } from '../../lib/api';
import type { NamingPattern } from '../../lib/types';

const AUTO_VALUE = '__auto__';

interface Props {
  open: boolean;
  projectId: number;
  defaultPatternName?: string | null;
  onCancel: () => void;
  onStartAuto: () => void | Promise<void>;
  onStartManual: (pattern: ApprovedStringPattern) => void;
}

export default function ParsePatternSelectModal({
  open,
  projectId,
  defaultPatternName,
  onCancel,
  onStartAuto,
  onStartManual,
}: Props) {
  const { t } = useTranslation();
  const [patterns, setPatterns] = useState<NamingPattern[]>([]);
  const [patternsLoading, setPatternsLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string>(AUTO_VALUE);

  useEffect(() => {
    if (!open) return;
    setLoadError(null);
    setPatternsLoading(true);
    setSelected(AUTO_VALUE);
    api
      .listProjectNamingPatterns(projectId, 'string')
      .then((list) => {
        const active = list.filter((p) => p.is_active !== false);
        setPatterns(active);
        if (defaultPatternName) {
          const match = active.find((p) => p.pattern_name === defaultPatternName);
          if (match) setSelected(String(match.id));
        }
      })
      .catch(() => setLoadError(t('project.parse_pattern.load_error')))
      .finally(() => setPatternsLoading(false));
  }, [open, projectId, defaultPatternName, t]);

  const selectedPattern = useMemo(() => {
    if (selected === AUTO_VALUE) return null;
    return patterns.find((p) => String(p.id) === selected) ?? null;
  }, [selected, patterns]);

  if (!open) return null;

  const onContinue = () => {
    if (selected === AUTO_VALUE) {
      void onStartAuto();
      return;
    }
    if (selectedPattern) {
      onStartManual({
        pattern_name: selectedPattern.pattern_name,
        pattern_regex: selectedPattern.pattern_regex,
      });
    }
  };

  const continueDisabled = selected !== AUTO_VALUE && !selectedPattern;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="w-full max-w-lg mx-4 rounded-2xl bg-white shadow-2xl overflow-hidden">
        <div className="px-6 py-5 border-b border-gray-100">
          <h3 className="text-lg font-semibold text-gray-900">{t('project.parse_pattern.title')}</h3>
          <p className="mt-1 text-sm text-gray-500">{t('project.parse_pattern.description')}</p>
        </div>

        <div className="px-6 py-5 space-y-4">
          {loadError && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
              {loadError}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              {t('project.parse_pattern.mode_label')}
            </label>
            <select
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
              disabled={patternsLoading}
              className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100 disabled:opacity-60"
            >
              <option value={AUTO_VALUE}>{t('project.parse_pattern.option_auto')}</option>
              {patterns.map((p) => (
                <option key={p.id} value={String(p.id)}>
                  {p.pattern_name}
                </option>
              ))}
            </select>
          </div>

          {patternsLoading && (
            <p className="text-xs text-gray-500">{t('project.parse_pattern.loading')}</p>
          )}
          {patterns.length === 0 && !patternsLoading && (
            <p className="text-xs text-gray-500">{t('project.parse_pattern.no_manual_patterns')}</p>
          )}

          {selectedPattern && (
            <div className="rounded-xl border border-gray-200 bg-gray-50 px-4 py-3">
              <div className="text-xs font-medium uppercase tracking-wide text-gray-500">
                {t('project.parse_pattern.regex_label')}
              </div>
              <div className="mt-1 break-all font-mono text-xs text-gray-700">{selectedPattern.pattern_regex}</div>
            </div>
          )}
        </div>

        <div className="px-6 pb-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50"
          >
            {t('project.parse_pattern.cancel')}
          </button>
          <button
            type="button"
            disabled={continueDisabled || (patternsLoading && selected !== AUTO_VALUE)}
            onClick={onContinue}
            className="px-4 py-2 text-sm font-medium bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-60"
          >
            {t('project.parse_pattern.continue')}
          </button>
        </div>
      </div>
    </div>
  );
}
