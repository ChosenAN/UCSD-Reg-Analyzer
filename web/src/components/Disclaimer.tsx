/** The standard risk caveat, shown wherever a risk score is displayed.
 *  Text mirrors analysis.RISK_DISCLAIMER. */
export const RISK_DISCLAIMER =
  "Heuristic estimate from a few terms of noisy WebReg snapshots — NOT a " +
  "guarantee. Registration appointment times, mid-term capacity changes, and " +
  "irregular scrape gaps all add uncertainty.";

export default function Disclaimer() {
  return <p className="disclaimer">{RISK_DISCLAIMER}</p>;
}
