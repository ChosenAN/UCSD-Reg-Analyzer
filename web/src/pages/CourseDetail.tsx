import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fetchCourseCsv } from "../lib/raw";
import { loadTerm } from "../lib/data";
import type { CourseSummary, Snapshot } from "../lib/types";
import Disclaimer from "../components/Disclaimer";
import { fmtHours, fmtNum, fmtPct, riskClass } from "../lib/format";

export default function CourseDetail() {
  const { term = "", code = "" } = useParams();
  const [rows, setRows] = useState<Snapshot[] | null>(null);
  const [summary, setSummary] = useState<CourseSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setRows(null);
    setError(null);
    fetchCourseCsv(term, code).then(setRows).catch((e) => setError(String(e)));
    loadTerm(term)
      .then((list) => setSummary(list.find((c) => c.course === code) ?? null))
      .catch(() => setSummary(null));
  }, [term, code]);

  const chartData = (rows ?? []).map((r) => ({
    time: r.time.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit" }),
    enrolled: r.enrolled,
    available: r.available,
    waitlisted: r.waitlisted,
    total: r.total,
  }));

  return (
    <div>
      <p>
        <Link to="/">← Dashboard</Link>
      </p>
      <h2>
        {code} <span className="muted">· {term}</span>
      </h2>

      {summary && (
        <div className="panel">
          <div className={`risk-pill ${riskClass(summary.risk_label)}`}>
            Risk: {fmtNum(summary.risk_score, 1)}{" "}
            {summary.risk_label ? `(${summary.risk_label})` : ""}
          </div>
          <ul className="stats">
            <li>Capacity: {fmtNum(summary.nominal_capacity)}</li>
            <li>Hours to full: {fmtHours(summary.hours_to_full)}</li>
            <li>Peak seats/hr: {fmtNum(summary.peak_enrolled_per_hour, 1)}</li>
            <li>Peak waitlist: {fmtNum(summary.peak_waitlist)}</li>
            <li>Final full: {fmtPct(summary.final_pct_full)}</li>
            <li>Snapshots: {summary.snapshots}</li>
          </ul>
          {summary.degraded && (
            <p className="muted">
              Degraded schema (no enrolled column) — velocity/risk unavailable.
            </p>
          )}
        </div>
      )}

      {error && (
        <p className="error">
          Couldn't load the time series from raw.githubusercontent.com: {error}
        </p>
      )}
      {!rows && !error && <p>Loading time series…</p>}
      {rows && rows.length > 0 && (
        <div className="chart">
          <ResponsiveContainer width="100%" height={400}>
            <LineChart data={chartData} margin={{ top: 10, right: 20, bottom: 10, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="time" minTickGap={40} />
              <YAxis />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="enrolled" stroke="#2563eb" dot={false} />
              <Line type="monotone" dataKey="available" stroke="#16a34a" dot={false} />
              <Line type="monotone" dataKey="waitlisted" stroke="#dc2626" dot={false} />
              <Line type="monotone" dataKey="total" stroke="#9ca3af" strokeDasharray="4 4" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
      {rows && rows.length === 0 && <p className="muted">No snapshots in this CSV.</p>}

      <Disclaimer />
    </div>
  );
}
