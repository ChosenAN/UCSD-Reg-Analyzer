import { useEffect, useState } from "react";
import { Link, NavLink, Outlet } from "react-router-dom";
import { loadIndex } from "./lib/data";
import type { BuildIndex } from "./lib/types";
import StalenessBanner from "./components/StalenessBanner";

export default function App() {
  const [index, setIndex] = useState<BuildIndex | null>(null);

  useEffect(() => {
    loadIndex()
      .then(setIndex)
      .catch(() => setIndex(null));
  }, []);

  return (
    <div className="app">
      <header className="topbar">
        <Link to="/" className="brand">
          UCSD Enrollment Dashboard
        </Link>
        <nav>
          <NavLink to="/" end>
            Dashboard
          </NavLink>
          <NavLink to="/compare">Compare</NavLink>
        </nav>
      </header>
      {index && <StalenessBanner builtAt={index.built_at} />}
      <main className="content">
        <Outlet context={index} />
      </main>
      <footer className="footer">
        Data:{" "}
        <a href="https://github.com/UCSD-Historical-Enrollment-Data">
          UCSD-Historical-Enrollment-Data
        </a>
        . Heuristic estimates from noisy WebReg snapshots — not a guarantee.
      </footer>
    </div>
  );
}
