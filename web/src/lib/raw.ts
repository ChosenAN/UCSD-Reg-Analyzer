/** Build raw-CSV URLs and parse them client-side.
 *
 * Mirrors the Python `fetch.build_url` (RAW_BASE/<term>/main/overall/<course>.csv,
 * course URL-encoded) and the `load.parse_csv` tidy schema. `enrolled` is absent
 * in the degraded Spring-2022 schema and becomes null.
 */
import type { Snapshot } from "./types";

export const RAW_BASE =
  "https://raw.githubusercontent.com/UCSD-Historical-Enrollment-Data";

export function buildRawUrl(term: string, course: string): string {
  return `${RAW_BASE}/${term}/main/overall/${encodeURIComponent(course)}.csv`;
}

function toNum(cell: string | undefined): number | null {
  if (cell === undefined) return null;
  const t = cell.trim();
  if (t === "") return null;
  const n = Number(t);
  return Number.isFinite(n) ? n : null;
}

/** Parse the simple numeric enrollment CSV into time-sorted snapshots. */
export function parseCsv(text: string): Snapshot[] {
  const lines = text.trim().split(/\r?\n/);
  if (lines.length < 2) return [];
  const header = lines[0].split(",").map((h) => h.trim());
  const idx = (name: string) => header.indexOf(name);
  const iTime = idx("time");
  const iEnr = idx("enrolled");
  const iAvail = idx("available");
  const iWait = idx("waitlisted");
  const iTotal = idx("total");

  const rows: Snapshot[] = [];
  for (let i = 1; i < lines.length; i++) {
    if (!lines[i].trim()) continue;
    const c = lines[i].split(",");
    const time = new Date(c[iTime]?.trim());
    if (isNaN(time.getTime())) continue;
    rows.push({
      time,
      enrolled: iEnr >= 0 ? toNum(c[iEnr]) : null,
      available: toNum(c[iAvail]),
      waitlisted: toNum(c[iWait]),
      total: toNum(c[iTotal]),
    });
  }
  rows.sort((a, b) => a.time.getTime() - b.time.getTime());
  return rows;
}

export async function fetchCourseCsv(
  term: string,
  course: string,
): Promise<Snapshot[]> {
  const resp = await fetch(buildRawUrl(term, course));
  if (!resp.ok) throw new Error(`CSV fetch failed (${resp.status})`);
  return parseCsv(await resp.text());
}
