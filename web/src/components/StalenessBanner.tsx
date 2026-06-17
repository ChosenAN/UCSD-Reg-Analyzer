/** Shows when the precomputed dataset was last built (from index.json). */
export default function StalenessBanner({ builtAt }: { builtAt: string }) {
  const when = new Date(builtAt);
  const label = isNaN(when.getTime()) ? builtAt : when.toLocaleString();
  return (
    <div className="staleness">
      Data last built: <strong>{label}</strong>. Completed terms don't change;
      rebuild to add newer terms.
    </div>
  );
}
