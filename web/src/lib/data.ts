/** Load the precomputed dashboard JSON shipped under the site's data/ folder. */
import type { BuildIndex, CourseSummary } from "./types";

const DATA_BASE = `${import.meta.env.BASE_URL}data/`;

export async function loadIndex(): Promise<BuildIndex> {
  const resp = await fetch(`${DATA_BASE}index.json`);
  if (!resp.ok) throw new Error(`index.json not found (${resp.status})`);
  return resp.json();
}

export async function loadTerm(term: string): Promise<CourseSummary[]> {
  const resp = await fetch(`${DATA_BASE}${encodeURIComponent(term)}.json`);
  if (!resp.ok) throw new Error(`${term}.json not found (${resp.status})`);
  return resp.json();
}
