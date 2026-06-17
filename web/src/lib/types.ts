/** Shapes that mirror the Python ingest output (web/public/data/*.json). */

/** One per-course summary row from `<term>.json`. */
export interface CourseSummary {
  course: string;
  nominal_capacity: number | null;
  hours_to_full: number | null;
  peak_enrolled_per_hour: number | null;
  peak_waitlist: number | null;
  final_pct_full: number | null;
  risk_score: number | null;
  risk_label: string | null;
  snapshots: number;
  degraded: boolean;
}

/** The build manifest from `index.json`. */
export interface BuildIndex {
  built_at: string;
  terms: { term: string; courses: number }[];
}

/** One parsed snapshot row from a raw course CSV. `enrolled` is null when the
 *  source uses the degraded Spring-2022 schema. */
export interface Snapshot {
  time: Date;
  enrolled: number | null;
  available: number | null;
  waitlisted: number | null;
  total: number | null;
}
