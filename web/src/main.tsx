import React from "react";
import ReactDOM from "react-dom/client";
import { HashRouter, Routes, Route } from "react-router-dom";
import App from "./App";
import Dashboard from "./pages/Dashboard";
import CourseDetail from "./pages/CourseDetail";
import Compare from "./pages/Compare";
import "./index.css";

// HashRouter: GitHub Pages serves static files only and won't rewrite deep
// links to index.html, so client-side routes live behind the URL hash.
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <HashRouter>
      <Routes>
        <Route path="/" element={<App />}>
          <Route index element={<Dashboard />} />
          <Route path="course/:term/:code" element={<CourseDetail />} />
          <Route path="compare" element={<Compare />} />
        </Route>
      </Routes>
    </HashRouter>
  </React.StrictMode>,
);
