import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import type { IVPoint } from '../api/client';

interface IVCurveChartProps {
  data: IVPoint[];
  width?: number;
  height?: number;
}

export function IVCurveChart({ data, width, height }: IVCurveChartProps) {
  // I-V curve: X=Voltage, Y=Current. Show as single line (V vs I)
  const chartData = data.map((p) => ({ voltage: p.voltage, current: p.current }));
  const tooltipFormatter = (
    value: string | number | ReadonlyArray<string | number> | undefined,
    name: string | number | undefined,
  ) => {
    const rawValue = Array.isArray(value) ? value[0] : value;
    const numericValue = typeof rawValue === "number" ? rawValue : Number(rawValue ?? 0);
    const seriesName = String(name ?? "").toLowerCase();
    return [
      seriesName === "voltage" ? `${numericValue.toFixed(2)} V` : `${numericValue.toFixed(3)} A`,
      seriesName === "voltage" ? "Voltage" : "Current",
    ] as [string, string];
  };

  return (
    <ResponsiveContainer width={width ?? '100%'} height={height ?? 320}>
      <LineChart data={chartData} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#2a2a2a" />
        <XAxis
          dataKey="voltage"
          type="number"
          unit=" V"
          stroke="#888"
          tick={{ fill: '#aaa' }}
        />
        <YAxis
          type="number"
          unit=" A"
          stroke="#888"
          tick={{ fill: '#aaa' }}
        />
        <Tooltip
          contentStyle={{ background: '#1a1a1a', border: '1px solid #333' }}
          labelStyle={{ color: '#fff' }}
          formatter={tooltipFormatter}
        />
        <Line
          type="monotone"
          dataKey="current"
          stroke="#22c55e"
          strokeWidth={2}
          dot={false}
          isAnimationActive={false}
          name="Current"
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
