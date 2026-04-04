import type { StructuredParseReport } from './api';

/** Payload shape from compact / next-gen parsers (may be nested or full body). */
export function extractStructuredParseReport(data: unknown): StructuredParseReport | null {
  if (!data || typeof data !== 'object') return null;
  const o = data as Record<string, unknown>;

  if (o.parse_report && typeof o.parse_report === 'object') {
    return o.parse_report as StructuredParseReport;
  }

  const site = o.site;
  const strBlk = o.strings;
  const looksLikeStringSummary =
    strBlk &&
    typeof strBlk === 'object' &&
    !Array.isArray(strBlk) &&
    ('valid_total' in strBlk || 'invalid_total' in strBlk || 'invalid_examples' in strBlk);
  if (
    site &&
    typeof site === 'object' &&
    ('final_status' in o || 'patterns' in o || 'spatial_validation' in o || looksLikeStringSummary)
  ) {
    return {
      site: site as StructuredParseReport['site'],
      patterns: o.patterns as StructuredParseReport['patterns'],
      inverters: o.inverters as StructuredParseReport['inverters'],
      strings: o.strings as StructuredParseReport['strings'],
      duplicates: o.duplicates as StructuredParseReport['duplicates'],
      missing: o.missing as StructuredParseReport['missing'],
      spatial_validation: o.spatial_validation as StructuredParseReport['spatial_validation'],
      final_status: o.final_status as string | undefined,
    };
  }

  return null;
}

export function isLegacyStringsBySection(strings: unknown): strings is Record<string, string[]> {
  if (!strings || typeof strings !== 'object' || Array.isArray(strings)) return false;
  const rec = strings as Record<string, unknown>;
  if ('valid_total' in rec || 'invalid_total' in rec || 'invalid_examples' in rec) return false;
  return Object.values(rec).every((v) => Array.isArray(v));
}
