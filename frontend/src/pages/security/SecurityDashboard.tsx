import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Shield, Monitor, AlertTriangle, CheckCircle, Play, Plus, Cpu, Wifi, RefreshCw } from 'lucide-react';
import * as api from '../../lib/api';
import DataPageShell from '../../components/layout/DataPageShell';

interface DashboardData {
  total_devices: number;
  total_vulnerabilities: number;
  critical_vulnerabilities: number;
  high_vulnerabilities: number;
  devices_at_risk: number;
  compliance_score: number;
  last_scan_date: string | null;
  top_risks: VulnItem[];
  vulnerability_by_category: Record<string, number>;
  vulnerability_by_severity: Record<string, number>;
}

interface VulnItem {
  id: string;
  device_id: string;
  device_name: string;
  severity: string;
  category: string;
  title: string;
  description: string;
  cve_id: string | null;
  cvss_score: number | null;
  affected_component: string;
  remediation: string;
  status: string;
  detected_date: string;
  due_date: string | null;
}

const SEV_BAR: Record<string, string> = {
  critical: '#dc2626', high: '#ea580c', medium: '#d97706', low: '#60a5fa', informational: '#9ca3af',
};
const CAT_BAR: Record<string, string> = {
  firmware: '#7c3aed', authentication: '#dc2626', encryption: '#4f46e5', protocol: '#0f766e',
  network: '#ea580c', configuration: '#d97706', physical: '#6b7280', supply_chain: '#db2777',
};
const SEV_BADGE: Record<string, { bg: string; color: string }> = {
  critical: { bg: '#dc2626', color: '#fff' }, high: { bg: '#ea580c', color: '#fff' },
  medium: { bg: '#d97706', color: '#fff' }, low: { bg: '#60a5fa', color: '#fff' }, informational: { bg: '#9ca3af', color: '#fff' },
};

const EMPTY: DashboardData = {
  total_devices: 0, total_vulnerabilities: 0, critical_vulnerabilities: 0,
  high_vulnerabilities: 0, devices_at_risk: 0, compliance_score: 100,
  last_scan_date: null, top_risks: [], vulnerability_by_category: {}, vulnerability_by_severity: {},
};

export default function SecurityDashboard() {
  const { t } = useTranslation();
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [loading, setLoading]     = useState(true);
  const [scanning, setScanning]   = useState(false);
  const [fwSummary, setFwSummary] = useState<any>(null);
  const [fwAlerts, setFwAlerts]   = useState<any[]>([]);
  const [checkingFw, setCheckingFw] = useState(false);

  const fetchFirmware = async () => {
    try {
      const [summary, alerts] = await Promise.all([api.getFirmwareSummary(), api.getFirmwareAlerts()]);
      setFwSummary(summary); setFwAlerts(alerts);
    } catch(e) { console.error(e); }
  };

  const fetchDashboard = async () => {
    setLoading(true);
    try { setDashboard(await api.getSecurityDashboard()); }
    catch(e) { console.error(e); }
    finally { setLoading(false); }
  };

  useEffect(() => { fetchDashboard(); fetchFirmware(); }, []);

  const handleRunScan = async () => {
    setScanning(true);
    try { await api.runSecurityScan({ project_id: 'all', scan_type: 'full' }); await fetchDashboard(); }
    catch(e) { console.error(e); }
    finally { setScanning(false); }
  };

  const handleCheckFirmware = async () => {
    setCheckingFw(true);
    try { await api.checkFirmwareUpdates(); await fetchFirmware(); }
    catch(e) { console.error(e); }
    finally { setCheckingFw(false); }
  };

  const data = dashboard ?? EMPTY;
  const maxSev = Math.max(...Object.values(data.vulnerability_by_severity), 1);
  const maxCat = Math.max(...Object.values(data.vulnerability_by_category), 1);

  const actions = [
    { icon: scanning ? <RefreshCw size={18} className="animate-spin"/> : <Play size={18}/>,
      label: scanning ? t('security.scanning') : t('security.scan'), variant: 'primary' as const, onClick: handleRunScan, disabled: scanning },
    { icon: <Plus size={18}/>, label: t('security.register_device'), onClick: () => {} },
  ];

  return (
    <DataPageShell
      title={t('security.title')}
      icon={<Shield size={17}/>}
      actions={actions}
    >
      <div style={{ overflowY: 'auto', height: '100%', padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 14 }}>

        {loading && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 160 }}>
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"/>
          </div>
        )}

        {!loading && <>
          {/* Last scan info */}
          <div style={{ fontSize: 12, color: '#6b7280' }}>
            {data.last_scan_date ? t('security.last_scan') + ': ' + new Date(data.last_scan_date).toLocaleString() : t('security.no_scans')}
          </div>

          {/* Stat cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
            {[
              { icon: <Monitor size={20} style={{ color: '#2563eb' }}/>, value: data.total_devices,           label: t('security.total_devices'),       border: '#3b82f6' },
              { icon: <AlertTriangle size={20} style={{ color: '#d97706' }}/>, value: data.total_vulnerabilities, label: t('security.open_vulns'), border: '#f59e0b' },
              { icon: <Shield size={20} style={{ color: '#dc2626' }}/>, value: data.critical_vulnerabilities, label: t('security.critical'),      border: '#ef4444' },
              { icon: <CheckCircle size={20} style={{ color: '#16a34a' }}/>, value: `${data.compliance_score}%`, label: t('security.compliance_score'), border: '#22c55e' },
            ].map((c, i) => (
              <div key={i} style={{ background: '#fff', borderRadius: 8, border: '1px solid #e5e7eb', borderLeft: `4px solid ${c.border}`, padding: '12px 16px', display: 'flex', alignItems: 'center', gap: 12 }}>
                {c.icon}
                <div>
                  <div style={{ fontSize: 22, fontWeight: 700, color: '#111827' }}>{c.value}</div>
                  <div style={{ fontSize: 12, color: '#6b7280' }}>{c.label}</div>
                </div>
              </div>
            ))}
          </div>

          {/* Charts row */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            {/* By Severity */}
            <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 8, padding: 16 }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: '#111827', marginBottom: 12 }}>{t('security.by_severity')}</div>
              {Object.keys(data.vulnerability_by_severity).length === 0
                ? <div style={{ color: '#9ca3af', fontSize: 13 }}>{t('common.no_data')}</div>
                : ['critical','high','medium','low','informational'].map(sev => {
                    const count = data.vulnerability_by_severity[sev] || 0;
                    if (!count) return null;
                    return (
                      <div key={sev} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                        <span style={{ fontSize: 12, fontWeight: 500, color: '#374151', width: 100, textTransform: 'capitalize' }}>{sev}</span>
                        <div style={{ flex: 1, background: '#f3f4f6', borderRadius: 4, height: 18, overflow: 'hidden' }}>
                          <div style={{ width: `${(count / maxSev) * 100}%`, background: SEV_BAR[sev] || '#9ca3af', height: 18, borderRadius: 4, transition: 'width 0.5s' }}/>
                        </div>
                        <span style={{ fontSize: 12, fontWeight: 700, color: '#111827', width: 24, textAlign: 'right' }}>{count}</span>
                      </div>
                    );
                  })
              }
            </div>
            {/* By Category */}
            <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 8, padding: 16 }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: '#111827', marginBottom: 12 }}>{t('security.by_category')}</div>
              {Object.keys(data.vulnerability_by_category).length === 0
                ? <div style={{ color: '#9ca3af', fontSize: 13 }}>{t('common.no_data')}</div>
                : Object.entries(data.vulnerability_by_category).sort(([,a],[,b]) => b - a).map(([cat, count]) => (
                  <div key={cat} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                    <span style={{ fontSize: 12, fontWeight: 500, color: '#374151', width: 100, textTransform: 'capitalize' }}>{cat.replace('_', ' ')}</span>
                    <div style={{ flex: 1, background: '#f3f4f6', borderRadius: 4, height: 18, overflow: 'hidden' }}>
                      <div style={{ width: `${(count / maxCat) * 100}%`, background: CAT_BAR[cat] || '#6b7280', height: 18, borderRadius: 4, transition: 'width 0.5s' }}/>
                    </div>
                    <span style={{ fontSize: 12, fontWeight: 700, color: '#111827', width: 24, textAlign: 'right' }}>{count}</span>
                  </div>
                ))
              }
            </div>
          </div>

          {/* Firmware Intelligence */}
          <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 8, padding: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: '#111827', display: 'flex', alignItems: 'center', gap: 6 }}>
                <Cpu size={16} style={{ color: '#7c3aed' }}/> {t('security.firmware_intelligence')}
              </div>
              <button onClick={handleCheckFirmware} disabled={checkingFw}
                style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '5px 12px', background: checkingFw ? '#6b7280' : '#7c3aed', color: '#fff', border: 'none', borderRadius: 6, fontSize: 12, fontWeight: 600, cursor: checkingFw ? 'not-allowed' : 'pointer' }}>
                <RefreshCw size={13} className={checkingFw ? 'animate-spin' : ''}/>
                {checkingFw ? t('security.checking') : t('security.check_firmware_cves')}
              </button>
            </div>
            {fwSummary ? (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
                {[
                  { label: t('security.devices_with_cves'), value: fwSummary.devices_with_known_cves || 0, bg: '#faf5ff', color: '#7c3aed' },
                  { label: t('security.unknown_firmware'),  value: fwSummary.devices_unknown_firmware || 0, bg: '#fffbeb', color: '#d97706' },
                  { label: t('security.critical_alerts'),   value: fwSummary.critical_alerts || 0,          bg: '#fef2f2', color: '#dc2626' },
                  { label: t('security.auto_tasks'),        value: fwSummary.auto_tasks_created || 0,       bg: '#eff6ff', color: '#2563eb' },
                ].map((c, i) => (
                  <div key={i} style={{ padding: '10px 12px', background: c.bg, borderRadius: 6 }}>
                    <div style={{ fontSize: 18, fontWeight: 700, color: c.color }}>{c.value}</div>
                    <div style={{ fontSize: 11, color: c.color }}>{c.label}</div>
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ fontSize: 13, color: '#9ca3af' }}>{t('security.no_firmware_data')}</div>
            )}
            {fwAlerts.length > 0 && (
              <div style={{ marginTop: 12 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: '#374151', marginBottom: 6, display: 'flex', alignItems: 'center', gap: 5 }}>
                  <Wifi size={13}/> {t('security.recent_fw_alerts')}
                </div>
                <div style={{ maxHeight: 160, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {fwAlerts.slice(0, 5).map((alert: any) => {
                    const b = SEV_BADGE[alert.severity] ?? { bg: '#e5e7eb', color: '#374151' };
                    return (
                      <div key={alert.id} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '6px 10px', background: '#f9fafb', borderRadius: 6, fontSize: 12 }}>
                        <span style={{ padding: '1px 6px', borderRadius: 4, fontSize: 10, fontWeight: 700, textTransform: 'uppercase', background: b.bg, color: b.color, whiteSpace: 'nowrap' }}>{alert.severity}</span>
                        <div style={{ flex: 1 }}>
                          <span style={{ fontWeight: 600 }}>{alert.device_name}</span> — {alert.title}
                          {alert.cve_id && <span style={{ marginLeft: 4, color: '#9ca3af' }}>({alert.cve_id})</span>}
                        </div>
                        <span style={{ fontFamily: 'monospace', color: '#6b7280', fontSize: 11, whiteSpace: 'nowrap' }}>CVSS {alert.cvss_score}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          {/* Top Risks */}
          <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 8, padding: 16 }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: '#111827', marginBottom: 12 }}>{t('security.top_risks')}</div>
            {data.top_risks.length === 0
              ? <div style={{ fontSize: 13, color: '#9ca3af' }}>{t('security.no_risks')}</div>
              : <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {data.top_risks.map(risk => {
                    const b = SEV_BADGE[risk.severity] ?? { bg: '#e5e7eb', color: '#374151' };
                    return (
                      <div key={risk.id} style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '10px 12px', border: '1px solid #f3f4f6', borderRadius: 6 }}>
                        <span style={{ padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 700, textTransform: 'uppercase', background: b.bg, color: b.color, whiteSpace: 'nowrap' }}>{risk.severity}</span>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontWeight: 600, color: '#111827', fontSize: 13 }}>{risk.title}</div>
                          <div style={{ fontSize: 12, color: '#6b7280', marginTop: 2 }}>{risk.device_name} · {risk.category}</div>
                        </div>
                        <div style={{ textAlign: 'right', flexShrink: 0 }}>
                          <div style={{ fontWeight: 700, color: '#111827', fontSize: 14 }}>{risk.cvss_score !== null ? risk.cvss_score.toFixed(1) : '—'}</div>
                          <div style={{ fontSize: 11, color: '#9ca3af' }}>CVSS</div>
                        </div>
                      </div>
                    );
                  })}
                </div>
            }
          </div>
        </>}
      </div>
    </DataPageShell>
  );
}
