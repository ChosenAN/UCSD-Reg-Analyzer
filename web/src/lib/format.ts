/** Small display helpers shared across views. */

export function fmtNum(v: number | null, digits = 0): string {
  return v == null ? "—" : v.toFixed(digits);
}

export function fmtPct(v: number | null): string {
  return v == null ? "—" : `${(v * 100).toFixed(0)}%`;
}

export function fmtHours(v: number | null): string {
  return v == null ? "—" : `${v.toFixed(1)} h`;
}

/** CSS class for a Low/Medium/High risk label. */
export function riskClass(label: string | null): string {
  switch (label) {
    case "High":
      return "risk-high";
    case "Medium":
      return "risk-med";
    case "Low":
      return "risk-low";
    default:
      return "risk-none";
  }
}
