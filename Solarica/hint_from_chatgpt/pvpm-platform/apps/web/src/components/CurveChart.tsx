import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid } from "recharts";

type Point = { pointIndex: number; voltageV: number; currentA: number };

export function CurveChart({ points }: { points: Point[] }) {
  return (
    <div className="chart card">
      <h3>I-V Curve</h3>
      <div style={{ width: "100%", height: 320 }}>
        <ResponsiveContainer>
          <LineChart data={points}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="voltageV" name="Voltage" unit="V" />
            <YAxis dataKey="currentA" name="Current" unit="A" />
            <Tooltip />
            <Line type="monotone" dataKey="currentA" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
