import { useState } from "react";
import { useOutletContext } from "react-router-dom";
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
import { alignForCompare, type AlignedPoint } from "../lib/analysis";
import type { BuildIndex } from "../lib/types";

const PALETTE = ["#2563eb", "#dc2626", "#16a34a", "#d97706", "#7c3aed", "#0891b2"];

interface Series {
  term: string;
  points: AlignedPoint[];
  error?: string;
}

export default function Compare() {
  const index = useOutletContext<BuildIndex | null>();
  const terms = index?.terms ?? [];
  const [course, setCourse] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [series, setSeries] = useState<Series[]>([]);
  const [loading, setLoading] = useState(false);

  function toggleTerm(term: string) {
    setSelected((cur) =>
      cur.includes(term) ? cur.filter((t) => t !== term) : [...cur, term],
    );
  }

  async function run() {
    const code = course.trim();
    if (!code || selected.length === 0) return;
    setLoading(true);
    const results = await Promise.all(
      selected.map(async (term): Promise<Series> => {
        try {
          const rows = await fetchCourseCsv(term, code);
          return { term, points: alignForCompare(rows) };
        } catch (e) {
          return { term, points: [], error: String(e) };
        }
      }),
    );
    setSeries(results);
    setLoading(false);
  }

  return (
    <div>
      <h2>Compare a course across terms</h2>
      <p className="muted">
        Fill curves are aligned to each term's seat release (day 0), mirroring
        the analyzer's compare alignment.
      </p>

      <div className="controls">
        <input
          type="search"
          placeholder="Course code (e.g. BILD 4)"
          value={course}
          onChange={(e) => setCourse(e.target.value)}
        />
        <button onClick={run} disabled={!course.trim() || selected.length === 0}>
          Compare
        </button>
      </div>

      <div className="term-picker">
        {terms.map((t) => (
          <label key={t.term}>
            <input
              type="checkbox"
              checked={selected.includes(t.term)}
              onChange={() => toggleTerm(t.term)}
            />
            {t.term}
          </label>
        ))}
      </div>

      {loading && <p>Fetching CSVs…</p>}

      {series.length > 0 && (
        <>
          <div className="chart">
            <ResponsiveContainer width="100%" height={420}>
              <LineChart margin={{ top: 10, right: 20, bottom: 20, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  type="number"
                  dataKey="days_since_release"
                  name="Days since release"
                  label={{ value: "Days since seat release", position: "insideBottom", offset: -10 }}
                  domain={["dataMin", "dataMax"]}
                />
                <YAxis
                  type="number"
                  domain={[0, 1]}
                  tickFormatter={(v) => `${Math.round(v * 100)}%`}
                />
                <Tooltip formatter={(v: number) => `${Math.round(v * 100)}%`} />
                <Legend />
                {series.map((s, i) => (
                  <Line
                    key={s.term}
                    data={s.points}
                    dataKey="pct_full"
                    name={s.term}
                    stroke={PALETTE[i % PALETTE.length]}
                    dot={false}
                    connectNulls
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
          <ul className="muted">
            {series.map((s) => (
              <li key={s.term}>
                {s.term}:{" "}
                {s.error
                  ? `error (${s.error})`
                  : s.points.length === 0
                    ? "no seat release detected (not offered or flat)"
                    : `${s.points.length} points`}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
