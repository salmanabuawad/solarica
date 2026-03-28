import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import type { Measurement } from "../api/client";
import { api } from "../api/client";
import { IVCurveChart } from "./IVCurveChart";
import { AnalysisPanel } from "./AnalysisPanel";

interface MeasurementListProps {
  refreshToken?: number;
  siteId?: number;
}

export function MeasurementList({ refreshToken = 0, siteId }: MeasurementListProps) {
  const { t } = useTranslation();
  const [measurements, setMeasurements] = useState<Measurement[]>([]);
  const [selected, setSelected] = useState<Measurement | null>(null);
  const [detail, setDetail] = useState<Measurement & { iv_curve: { voltage: number; current: number }[] } | null>(null);

  useEffect(() => {
    api.listMeasurements({ site_id: siteId }).then((items) => {
      setMeasurements(items);
      setSelected((current) => {
        if (!current) return current;
        return items.find((item) => item.id === current.id) || null;
      });
    });
  }, [refreshToken, siteId]);

  useEffect(() => {
    if (!selected) { setDetail(null); return; }
    api.getMeasurement(selected.id).then(setDetail);
  }, [selected, refreshToken]);

  const onSelect = async (m: Measurement) => {
    setSelected(m);
    const d = await api.getMeasurement(m.id);
    setDetail(d);
  };

  return (
    <div className="measurement-list">
      <div className="list-layout" style={{ display: "flex", gap: 16 }}>
        <ul style={{ listStyle: "none", margin: 0, padding: 0, minWidth: 200, maxHeight: 320, overflowY: "auto", borderRight: "1px solid rgb(var(--theme-card-border))", paddingRight: 8 }}>
          {measurements.length === 0 && (
            <li style={{ color: "rgb(var(--theme-text-muted))", fontSize: "var(--theme-font-size-xs)", padding: "8px 0" }}>{t("common.noData")}</li>
          )}
          {measurements.map((m) => (
            <li
              key={m.id}
              style={{ padding: "6px 8px", cursor: "pointer", borderRadius: 6, fontSize: "var(--theme-font-size-xs)", background: selected?.id === m.id ? "rgb(var(--theme-highlight))" : undefined, color: selected?.id === m.id ? "rgb(var(--theme-action-accent))" : "rgb(var(--theme-text-primary))", display: "flex", gap: 8 }}
              onClick={() => onSelect(m)}
            >
              <span style={{ fontWeight: 600 }}>#{m.id}</span>
              <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{m.source_file || "—"}</span>
              <span style={{ marginLeft: "auto", whiteSpace: "nowrap" }}>{m.ppk != null ? `${m.ppk.toFixed(1)} W` : "—"}</span>
            </li>
          ))}
        </ul>

        <div className="detail-panel" style={{ flex: 1, minWidth: 0 }}>
          {detail ? (
            <>
              <div className="chart-section" style={{ marginBottom: 12 }}>
                <div style={{ fontWeight: 600, fontSize: "var(--theme-font-size-sm)", marginBottom: 6 }}>{t("measurementList.ivCurve")}</div>
                <IVCurveChart data={detail.iv_curve} />
              </div>
              <AnalysisPanel detail={detail} />
              <div className="metrics" style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 6, marginTop: 8, fontSize: "var(--theme-font-size-xs)" }}>
                <div><strong>Ppk:</strong> {detail.ppk?.toFixed(2) ?? "—"} W</div>
                <div><strong>Rs:</strong> {detail.rs?.toFixed(4) ?? "—"} Ω</div>
                <div><strong>Rp:</strong> {detail.rp?.toFixed(2) ?? "—"} Ω</div>
                <div><strong>Voc:</strong> {detail.voc?.toFixed(2) ?? "—"} V</div>
                <div><strong>Isc:</strong> {detail.isc?.toFixed(2) ?? "—"} A</div>
                <div><strong>Eeff:</strong> {detail.eeff?.toFixed(0) ?? "—"} W/m²</div>
              </div>
            </>
          ) : (
            <p style={{ color: "rgb(var(--theme-text-muted))", fontSize: "var(--theme-font-size-xs)" }}>{t("measurementList.selectMeasurement")}</p>
          )}
        </div>
      </div>
    </div>
  );
}
