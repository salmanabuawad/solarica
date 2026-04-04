import { useEffect, useMemo, useState } from 'react';
import type { ApprovedStringPattern, StringPatternDetectionResult } from '../../lib/api';

interface Props {
  open: boolean;
  detection: StringPatternDetectionResult | null;
  busy?: boolean;
  onCancel: () => void;
  onConfirm: (pattern: ApprovedStringPattern) => void;
}

export default function StringPatternConfirmModal({
  open,
  detection,
  busy = false,
  onCancel,
  onConfirm,
}: Props) {
  const defaultName = detection?.selected_pattern_name ?? detection?.detected_pattern_name ?? detection?.patterns[0]?.pattern_name ?? '';
  const [selectedName, setSelectedName] = useState(defaultName);

  useEffect(() => {
    if (open) {
      setSelectedName(defaultName);
    }
  }, [defaultName, open]);

  const selectedPattern = useMemo(
    () => detection?.patterns.find((item) => item.pattern_name === selectedName) ?? detection?.patterns[0] ?? null,
    [detection, selectedName],
  );

  if (!open || !detection) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="w-full max-w-lg mx-4 rounded-2xl bg-white shadow-2xl overflow-hidden">
        <div className="px-6 py-5 border-b border-gray-100">
          <h3 className="text-lg font-semibold text-gray-900">Confirm string pattern</h3>
          <p className="mt-1 text-sm text-gray-500">
            Approve the pattern before parsing so validation uses the right naming rule.
          </p>
        </div>

        <div className="px-6 py-5 space-y-4">
          <div className="rounded-xl border border-blue-100 bg-blue-50 px-4 py-3">
            <div className="text-xs font-medium uppercase tracking-wide text-blue-700">Detected pattern</div>
            <div className="mt-1 text-sm text-blue-900">
              {detection.detected_pattern_name ?? 'No strong match detected'}
            </div>
            {detection.saved_pattern_name && (
              <div className="mt-1 text-xs text-blue-700">
                Saved on project: <span className="font-semibold">{detection.saved_pattern_name}</span>
              </div>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Use this pattern</label>
            <select
              value={selectedName}
              onChange={(e) => setSelectedName(e.target.value)}
              className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
            >
              {detection.patterns.map((pattern) => (
                <option key={pattern.pattern_name} value={pattern.pattern_name}>
                  {pattern.pattern_name}
                  {pattern.match_count > 0 ? ` (${pattern.match_count} matches)` : ''}
                </option>
              ))}
            </select>
          </div>

          {selectedPattern && (
            <div className="rounded-xl border border-gray-200 bg-gray-50 px-4 py-3">
              <div className="text-xs font-medium uppercase tracking-wide text-gray-500">Regex</div>
              <div className="mt-1 break-all font-mono text-xs text-gray-700">{selectedPattern.pattern_regex}</div>
            </div>
          )}
        </div>

        <div className="px-6 pb-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-60"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={!selectedPattern || busy}
            onClick={() => selectedPattern && onConfirm({ pattern_name: selectedPattern.pattern_name, pattern_regex: selectedPattern.pattern_regex })}
            className="px-4 py-2 text-sm font-medium bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-60"
          >
            {busy ? 'Starting parse...' : 'Approve and continue'}
          </button>
        </div>
      </div>
    </div>
  );
}
