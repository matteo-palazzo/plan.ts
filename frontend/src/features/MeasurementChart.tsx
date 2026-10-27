import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ChartRange, MeasurementKind } from "../api/types";
import { MEASUREMENT_KINDS, formatDate, formatMm, isoDate, parseDate } from "../lib/format";

const shortDate = new Intl.DateTimeFormat("it-IT", { day: "numeric", month: "short" });
const shortDateYear = new Intl.DateTimeFormat("it-IT", { month: "short", year: "2-digit" });

export default function MeasurementChart({ kind, points, range }: { kind: MeasurementKind; points: { date: string; value_mm: string }[]; range: ChartRange }) {
  const data = points.map((point) => ({ time: parseDate(point.date).getTime(), value: Number(point.value_mm), date: point.date }));
  const formatter = range === "month" ? shortDate : shortDateYear;
  const title = MEASUREMENT_KINDS[kind];
  const last = data[data.length - 1];

  return (
    <figure className="chart">
      <figcaption>
        <span>{title}</span>
        {last ? <span className="muted">ultima: {formatMm(last.value)}</span> : null}
      </figcaption>
      {data.length ? (
        <div className="chart-area" role="img" aria-label={`Grafico ${title.toLowerCase()}: ${data.length} rilevazioni`}>
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: -8 }}>
              <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
              <XAxis
                dataKey="time"
                type="number"
                scale="time"
                domain={data.length === 1 ? ["dataMin - 86400000", "dataMax + 86400000"] : ["dataMin", "dataMax"]}
                tickFormatter={(value: number) => formatter.format(new Date(value))}
                tick={{ fontSize: 12, fill: "var(--muted)" }}
                minTickGap={24}
              />
              <YAxis
                width={52}
                tick={{ fontSize: 12, fill: "var(--muted)" }}
                domain={["auto", "auto"]}
                tickFormatter={(value: number) => `${value}`}
                unit=" mm"
              />
              <Tooltip
                labelFormatter={(value) => formatDate(isoDate(new Date(Number(value))))}
                formatter={(value) => [formatMm(Number(value)), title]}
              />
              <Line type="monotone" dataKey="value" stroke="var(--accent)" strokeWidth={2} dot={{ r: 3 }} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <p className="muted chart-empty">Nessuna rilevazione nel periodo.</p>
      )}
    </figure>
  );
}
