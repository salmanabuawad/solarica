import { MapPin, Grid3x3, Cpu, Layers, Copy, AlertTriangle, Map, Flag } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { StructuredParseReport } from '../../lib/api';

function statusPill(finalStatus: string | undefined, t: (k: string, d: string) => string) {
  if (!finalStatus) return null;
  const lower = finalStatus.toLowerCase();
  const cls =
    lower.includes('ok') && !lower.includes('cleanup')
      ? 'bg-emerald-100 text-emerald-800 border-emerald-200'
      : lower.includes('pending')
        ? 'bg-slate-100 text-slate-700 border-slate-200'
        : lower.includes('cleanup') || lower.includes('fail') || lower.includes('error')
          ? 'bg-amber-100 text-amber-900 border-amber-300'
          : 'bg-gray-100 text-gray-800 border-gray-200';
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${cls}`}>
      <Flag className="h-3 w-3" />
      {t('parse_report.final_status', 'Final status')}: {finalStatus}
    </span>
  );
}

export default function StructuredParseReportPanel({ report }: { report: StructuredParseReport }) {
  const { t } = useTranslation();
  const site = report.site;
  const dupExact = report.duplicates?.exact ?? {};
  const dupEntries = Object.entries(dupExact);
  const missingEntries = Object.entries(report.missing ?? {});
  const inv = report.inverters;
  const str = report.strings;
  const patt = report.patterns;
  const spatial = report.spatial_validation;

  return (
    <div className="rounded-xl border border-indigo-200 bg-gradient-to-b from-indigo-50/80 to-white p-5 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-semibold text-gray-900 flex items-center gap-2 text-sm">
          <Grid3x3 className="h-4 w-4 text-indigo-600" />
          {t('parse_report.title', 'Parse summary')}
        </h3>
        {statusPill(report.final_status, t)}
      </div>

      {site && (
        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-1">
            <MapPin className="h-3 w-3" /> {t('parse_report.site', 'Site')}
          </p>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
            {[
              [t('parse_report.name', 'Name'), site.name],
              [t('parse_report.installation', 'Installation'), site.installation_type],
              [t('parse_report.country', 'Country'), site.country],
              [t('parse_report.region', 'Region'), site.region],
            ].map(
              ([label, val]) =>
                val != null &&
                String(val).length > 0 && (
                  <div key={String(label)}>
                    <p className="text-xs text-gray-500">{label}</p>
                    <p className="font-medium text-gray-900">{String(val)}</p>
                  </div>
                ),
            )}
            {site.coordinates != null &&
              (site.coordinates.lat != null || site.coordinates.lon != null) && (
                <div className="col-span-2 md:col-span-1">
                  <p className="text-xs text-gray-500">{t('parse_report.coordinates', 'Coordinates')}</p>
                  <p className="font-mono text-xs text-gray-800">
                    {site.coordinates.lat ?? '—'}°, {site.coordinates.lon ?? '—'}°
                  </p>
                </div>
              )}
          </div>
        </div>
      )}

      {patt && (
        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-wide mb-2">
            {t('parse_report.patterns', 'Patterns')}
          </p>
          <dl className="space-y-1.5 text-sm">
            {patt.valid_string_pattern != null && (
              <div className="flex flex-wrap gap-2">
                <dt className="text-gray-500 shrink-0">{t('parse_report.string_pattern', 'String pattern')}:</dt>
                <dd className="font-mono text-xs text-gray-900">{patt.valid_string_pattern}</dd>
              </div>
            )}
            {patt.valid_inverter_pattern != null && (
              <div className="flex flex-wrap gap-2">
                <dt className="text-gray-500 shrink-0">{t('parse_report.inverter_pattern', 'Inverter pattern')}:</dt>
                <dd className="font-mono text-xs text-gray-900">{patt.valid_inverter_pattern}</dd>
              </div>
            )}
            {patt.mode != null && (
              <div className="flex flex-wrap gap-2">
                <dt className="text-gray-500 shrink-0">{t('parse_report.mode', 'Mode')}:</dt>
                <dd className="font-medium text-gray-800">{patt.mode}</dd>
              </div>
            )}
          </dl>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {inv && (
          <div className="rounded-lg border border-gray-200 bg-white p-4 md:col-span-1">
            <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-1">
              <Cpu className="h-3 w-3" /> {t('parse_report.inverters', 'Inverters')}
            </p>
            <p className="text-2xl font-bold text-gray-900">{inv.total ?? inv.present?.length ?? '—'}</p>
            {inv.status != null && (
              <p className="text-xs text-gray-600 mt-1">
                {t('parse_report.status', 'Status')}: <span className="font-medium">{inv.status}</span>
              </p>
            )}
            {inv.present != null && inv.present.length > 0 && (
              <div className="mt-2 max-h-28 overflow-y-auto rounded border border-gray-100 bg-gray-50 p-2">
                <p className="text-[10px] text-gray-500 mb-1">{t('parse_report.present', 'Present')}</p>
                <p className="font-mono text-[10px] text-gray-800 leading-relaxed break-all">
                  {inv.present.join(', ')}
                </p>
              </div>
            )}
          </div>
        )}

        {str && (
          <div className="rounded-lg border border-gray-200 bg-white p-4">
            <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-1">
              <Layers className="h-3 w-3" /> {t('parse_report.strings', 'Strings')}
            </p>
            <div className="flex gap-4 text-sm">
              <div>
                <p className="text-xs text-gray-500">{t('parse_report.valid', 'Valid')}</p>
                <p className="text-xl font-bold text-emerald-700">{str.valid_total ?? '—'}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">{t('parse_report.invalid', 'Invalid')}</p>
                <p className="text-xl font-bold text-red-600">{str.invalid_total ?? '—'}</p>
              </div>
            </div>
            {str.invalid_examples != null && str.invalid_examples.length > 0 && (
              <div className="mt-2">
                <p className="text-[10px] text-gray-500 mb-1">{t('parse_report.invalid_examples', 'Invalid examples')}</p>
                <div className="flex flex-wrap gap-1">
                  {str.invalid_examples.map((ex) => (
                    <span key={ex} className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-red-50 text-red-800 border border-red-100">
                      {ex}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {spatial && (
          <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50/80 p-4">
            <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-1">
              <Map className="h-3 w-3" /> {t('parse_report.spatial', 'Spatial validation')}
            </p>
            <p className="text-sm font-medium text-gray-800">{spatial.status ?? '—'}</p>
            {spatial.reason != null && <p className="text-xs text-gray-600 mt-1">{spatial.reason}</p>}
          </div>
        )}
      </div>

      {(dupEntries.length > 0 || missingEntries.length > 0) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {dupEntries.length > 0 && (
            <div className="rounded-lg border border-orange-200 bg-orange-50/50 p-4">
              <p className="text-[11px] font-semibold text-orange-800 uppercase tracking-wide mb-2 flex items-center gap-1">
                <Copy className="h-3 w-3" /> {t('parse_report.duplicates_exact', 'Exact duplicates')}
              </p>
              <ul className="space-y-1 text-sm font-mono text-xs">
                {dupEntries.map(([code, count]) => (
                  <li key={code} className="flex justify-between gap-2 text-orange-900">
                    <span>{code}</span>
                    <span className="text-orange-700">×{count}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {missingEntries.length > 0 && (
            <div className="rounded-lg border border-amber-200 bg-amber-50/50 p-4">
              <p className="text-[11px] font-semibold text-amber-900 uppercase tracking-wide mb-2 flex items-center gap-1">
                <AlertTriangle className="h-3 w-3" /> {t('parse_report.missing', 'Missing string numbers')}
              </p>
              <ul className="space-y-1 text-xs">
                {missingEntries.map(([key, nos]) => (
                  <li key={key} className="font-mono text-amber-900">
                    <span className="font-semibold">{key}</span>: [{nos.join(', ')}]
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
