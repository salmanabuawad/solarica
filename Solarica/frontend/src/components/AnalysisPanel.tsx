import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { MeasurementDetail } from "../api/client";

interface AnalysisPanelProps {
  detail: MeasurementDetail;
}

function getOverallGrade(score: number | null): { label: string; gradeClass: string } | null {
  if (score == null) return null;
  if (score >= 85) return { label: "Good", gradeClass: "good" };
  if (score >= 65) return { label: "Fair", gradeClass: "ok" };
  return { label: "Needs attention", gradeClass: "low" };
}

export function AnalysisPanel({ detail }: AnalysisPanelProps) {
  const { ppk, rs, rp, voc, isc, pmax, fill_factor, eeff, iv_curve } = detail;

  // P-V curve: Power = V * I
  const pvData =
    iv_curve?.map((p) => ({
      voltage: p.voltage,
      current: p.current,
      power: Math.round(p.voltage * p.current * 100) / 100,
    })) ?? [];

  // Theoretical fill factor FF = Pmax / (Voc * Isc)
  const theoreticalFF =
    voc != null && isc != null && voc > 0 && isc > 0 && pmax != null
      ? ((pmax / (voc * isc)) * 100).toFixed(1)
      : null;

  // Performance ratio (actual power / theoretical at STC-ish conditions)
  const perfRatio =
    eeff != null && eeff > 0 && pmax != null && ppk != null
      ? ((pmax / ppk) * (1000 / eeff) * 100).toFixed(1)
      : null;

  // Health indicators (typical healthy ranges: Rs 0.2-1 ohm, Rp > 50 ohm)
  const rsStatus =
    rs != null
      ? rs < 0.5
        ? "good"
        : rs < 1.5
          ? "ok"
          : "high"
      : null;
  const rpStatus =
    rp != null
      ? rp > 100
        ? "good"
        : rp > 30
          ? "ok"
          : "low"
      : null;

  // Overall performance score (0-100) from FF, Rs, Rp, irradiance adequacy
  const ff = fill_factor ?? (theoreticalFF ? parseFloat(theoreticalFF) : null);
  const ffScore = ff != null ? Math.min(100, (ff / 80) * 100) : 50;
  const rsScore = rs != null ? (rsStatus === "good" ? 100 : rsStatus === "ok" ? 70 : 40) : 50;
  const rpScore = rp != null ? (rpStatus === "good" ? 100 : rpStatus === "ok" ? 70 : 40) : 50;
  const irradScore = eeff != null && eeff >= 500 ? 100 : eeff != null && eeff >= 300 ? 70 : eeff != null ? 50 : 50;
  const scores = [ffScore, rsScore, rpScore, irradScore];
  const validScores = scores.filter((s) => s !== 50);
  const overallScore =
    validScores.length > 0
      ? Math.round(validScores.reduce((a, b) => a + b, 0) / validScores.length)
      : null;

  const overallGrade = getOverallGrade(overallScore);

  const tooltipFormatter = (
    value: string | number | ReadonlyArray<string | number> | undefined,
    name: string | number | undefined,
  ) => {
    const rawValue = Array.isArray(value) ? value[0] : value;
    const numericValue = typeof rawValue === "number" ? rawValue : Number(rawValue ?? 0);
    const seriesName = String(name ?? "");
    return [
      `${numericValue.toFixed(2)} ${seriesName === "power" ? "W" : "V"}`,
      seriesName === "power" ? "Power" : "Voltage",
    ] as [string, string];
  };

  // Improvement recommendations based on analysis
  const recommendations: string[] = [];
  if (rsStatus === "high" && rs != null) {
    recommendations.push(
      "High Rs: Check interconnects, solder joints, and contact resistance. Clean MC4 connectors and ensure tight connections."
    );
  }
  if (rpStatus === "low" && rp != null) {
    recommendations.push(
      "Low Rp: Possible shunt paths or cell defects. Inspect for hot spots, cracked cells, or moisture ingress. Check bypass diodes."
    );
  }
  if (eeff != null && eeff < 500) {
    recommendations.push(
      "Low irradiance: For more accurate STC values, remeasure when irradiance > 500 W/m² (ideally > 800 W/m² per IEC 60904)."
    );
  }
  if (ff != null && ff < 70) {
    recommendations.push(
      "Low fill factor: May indicate mismatch, shading, or degradation. Verify modules are clean and no partial shading during measurement."
    );
  }
  if (pmax != null && ppk != null && eeff != null && eeff > 0) {
    const utilization = (pmax / ppk) * (1000 / eeff);
    if (utilization < 0.85) {
      recommendations.push(
        "Below-expected power: Ensure reference sensor is co-planar with modules, measure within ±10 W/m² stable irradiance, and verify 4-wire connection."
      );
    }
  }
  if (recommendations.length === 0 && overallScore != null && overallScore >= 85) {
    recommendations.push("No major issues detected. Maintain regular cleaning and periodic IV curve checks.");
  }

  return (
    <div className="analysis-panel">
      <h3>Analysis</h3>

      <div className="analysis-section">
        <h4>Key metrics</h4>
        <table className="metrics-table">
          <tbody>
            <tr>
              <td>Peak power (Ppk)</td>
              <td>{ppk != null ? `${ppk.toFixed(2)} W` : "—"}</td>
              <td className="muted">@ STC</td>
            </tr>
            <tr>
              <td>Max power (Pmax)</td>
              <td>{pmax != null ? `${pmax.toFixed(2)} W` : "—"}</td>
              <td className="muted">at measurement conditions</td>
            </tr>
            <tr>
              <td>Fill factor</td>
              <td>{fill_factor != null ? `${fill_factor.toFixed(1)}%` : theoreticalFF ? `${theoreticalFF}% (calc)` : "—"}</td>
            </tr>
            {perfRatio != null && (
              <tr>
                <td>Relative performance</td>
                <td>{perfRatio}%</td>
                <td className="muted">vs irradiance</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {overallScore != null && (
        <div className="analysis-section overall-performance">
          <h4>Overall performance</h4>
          <div className={`perf-score ${overallGrade?.gradeClass ?? ""}`}>
            <span className="score-value">{overallScore}</span>
            <span className="score-label">/ 100</span>
            <span className="score-grade">{overallGrade?.label}</span>
          </div>
          <p className="score-hint">Based on fill factor, Rs, Rp, and irradiance adequacy</p>
        </div>
      )}

      {recommendations.length > 0 && (
        <div className="analysis-section recommendations">
          <h4>Improvement recommendations</h4>
          <ul>
            {recommendations.map((rec, i) => (
              <li key={i}>{rec}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="analysis-section">
        <h4>Resistance health</h4>
        <div className="health-badges">
          <span
            className={`badge ${rsStatus ?? ""}`}
            title="Series resistance (Rs). Lower is generally better. High Rs can indicate soldering/contact issues."
          >
            Rs: {rs != null ? `${rs.toFixed(3)} Ω` : "—"}{" "}
            {rsStatus === "good" && "✓"}
            {rsStatus === "high" && "↑"}
          </span>
          <span
            className={`badge ${rpStatus ?? ""}`}
            title="Parallel resistance (Rp). Higher is generally better. Low Rp can indicate shunt paths or cell defects."
          >
            Rp: {rp != null ? `${rp.toFixed(1)} Ω` : "—"}{" "}
            {rpStatus === "good" && "✓"}
            {rpStatus === "low" && "↓"}
          </span>
        </div>
      </div>

      <div className="analysis-section">
        <h4>P-V curve (Power vs Voltage)</h4>
        {pvData.length > 0 ? (
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={pvData} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2a2a2a" />
              <XAxis
                dataKey="voltage"
                type="number"
                unit=" V"
                stroke="#888"
                tick={{ fill: "#aaa" }}
              />
              <YAxis
                yAxisId="power"
                type="number"
                unit=" W"
                stroke="#888"
                tick={{ fill: "#aaa" }}
              />
              <Tooltip
                contentStyle={{ background: "#1a1a1a", border: "1px solid #333" }}
                formatter={tooltipFormatter}
                labelFormatter={(v) => `Voltage: ${v} V`}
              />
              <Line
                yAxisId="power"
                type="monotone"
                dataKey="power"
                stroke="#3b82f6"
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
                name="power"
              />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <p className="hint">No I-V data for P-V curve</p>
        )}
      </div>
    </div>
  );
}
