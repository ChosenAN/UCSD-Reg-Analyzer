import { useEffect, useMemo, useState } from "react";
import { Link, useOutletContext } from "react-router-dom";
import { loadTerm } from "../lib/data";
import type { BuildIndex, CourseSummary } from "../lib/types";
import { fmtHours, fmtNum, fmtPct, riskClass } from "../lib/format";

type SortKey = keyof CourseSummary;

const COLUMNS: { key: SortKey; label: string; render: (c: CourseSummary) => string }[] = [
  { key: "course", label: "Course", render: (c) => c.course },
  { key: "risk_score", label: "Risk", render: (c) => fmtNum(c.risk_score, 1) },
  { key: "hours_to_full", label: "Hrs to full", render: (c) => fmtHours(c.hours_to_full) },
  {
    key: "peak_enrolled_per_hour",
    label: "Peak seats/hr",
    render: (c) => fmtNum(c.peak_enrolled_per_hour, 1),
  },
  { key: "peak_waitlist", label: "Peak waitlist", render: (c) => fmtNum(c.peak_waitlist) },
  { key: "final_pct_full", label: "Final full", render: (c) => fmtPct(c.final_pct_full) },
  { key: "nominal_capacity", label: "Capacity", render: (c) => fmtNum(c.nominal_capacity) },
];

export default function Dashboard() {
  const index = useOutletContext<BuildIndex | null>();
  const terms = index?.terms ?? [];
  const [term, setTerm] = useState<string>("");
  const [rows, setRows] = useState<CourseSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("risk_score");
  const [asc, setAsc] = useState(false);

  // Default to the first term once the index loads.
  useEffect(() => {
    if (!term && terms.length) setTerm(terms[0].term);
  }, [terms, term]);

  useEffect(() => {
    if (!term) return;
    setLoading(true);
    setError(null);
    loadTerm(term)
      .then(setRows)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [term]);

  const filtered = useMemo(() => {
    const q = search.trim().toUpperCase();
    const matched = q
      ? rows.filter((r) => r.course.toUpperCase().includes(q))
      : rows.slice();
    matched.sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      // Nulls always sort last regardless of direction.
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      const cmp = typeof av === "number" && typeof bv === "number"
        ? av - bv
        : String(av).localeCompare(String(bv));
      return asc ? cmp : -cmp;
    });
    return matched;
  }, [rows, search, sortKey, asc]);

  function toggleSort(key: SortKey) {
    if (key === sortKey) setAsc((v) => !v);
    else {
      setSortKey(key);
      setAsc(key === "course"); // text ascending, numbers descending by default
    }
  }

  if (!index) {
    return (
      <div className="empty">
        <h2>No data yet</h2>
        <p>
          Run the ingest step to populate <code>web/public/data</code>:
        </p>
        <pre>uv run ucsd-enroll-analyzer build-web --terms 2024Fall</pre>
      </div>
    );
  }

  return (
    <div>
      <div className="controls">
        <label>
          Term{" "}
          <select value={term} onChange={(e) => setTerm(e.target.value)}>
            {terms.map((t) => (
              <option key={t.term} value={t.term}>
                {t.term} ({t.courses})
              </option>
            ))}
          </select>
        </label>
        <input
          type="search"
          placeholder="Search course code (e.g. BILD 4)"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {loading && <p>Loading {term}…</p>}
      {error && <p className="error">Failed to load {term}: {error}</p>}

      {!loading && !error && (
        <>
          <p className="count">
            {filtered.length} course{filtered.length === 1 ? "" : "s"}
          </p>
          <table className="grid">
            <thead>
              <tr>
                {COLUMNS.map((col) => (
                  <th
                    key={col.key}
                    onClick={() => toggleSort(col.key)}
                    className={col.key === sortKey ? "sorted" : ""}
                  >
                    {col.label}
                    {col.key === sortKey ? (asc ? " ▲" : " ▼") : ""}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((c) => (
                <tr key={c.course}>
                  {COLUMNS.map((col) => (
                    <td
                      key={col.key}
                      className={col.key === "risk_score" ? riskClass(c.risk_label) : ""}
                    >
                      {col.key === "course" ? (
                        <Link to={`/course/${encodeURIComponent(term)}/${encodeURIComponent(c.course)}`}>
                          {c.course}
                        </Link>
                      ) : (
                        col.render(c)
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}
