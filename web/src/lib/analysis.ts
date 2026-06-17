/** Chart-only re-derivations from raw snapshots.
 *
 * Mirrors the Python `analysis.fill_curve`, `first_seat_release`, and
 * `align_for_compare`. All ranking metrics come from the Python precompute; this
 * only computes the series the charts draw. Keep behavior in sync with
 * src/ucsd_enroll_analyzer/analysis.py.
 */
import type { Snapshot } from "./types";

/** Per-row pct_full = (total - available) / total; null where total <= 0. */
export function fillCurve(rows: Snapshot[]): (number | null)[] {
  return rows.map((r) => {
    if (r.total == null || r.available == null || r.total <= 0) return null;
    return (r.total - r.available) / r.total;
  });
}

/** First timestamp seats were released: first positive jump in total of at
 *  least min_jump, else the first row with total > 0. null if none. */
export function firstSeatRelease(
  rows: Snapshot[],
  minJump = 10,
): Date | null {
  let prev: number | null = null;
  for (const r of rows) {
    if (prev != null && r.total != null && r.total - prev >= minJump) {
      return r.time;
    }
    if (r.total != null) prev = r.total;
  }
  for (const r of rows) {
    if (r.total != null && r.total > 0) return r.time;
  }
  return null;
}

export interface AlignedPoint {
  days_since_release: number;
  pct_full: number | null;
}

/** Align one course's fill curve to days since its own seat release (day 0).
 *  Returns [] if no release is detectable. */
export function alignForCompare(
  rows: Snapshot[],
  minJump = 10,
): AlignedPoint[] {
  const release = firstSeatRelease(rows, minJump);
  if (release === null) return [];
  const pct = fillCurve(rows);
  const out: AlignedPoint[] = [];
  rows.forEach((r, i) => {
    const days =
      (r.time.getTime() - release.getTime()) / (1000 * 60 * 60 * 24);
    if (days >= 0) out.push({ days_since_release: days, pct_full: pct[i] });
  });
  return out;
}
