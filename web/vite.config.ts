import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// GitHub Pages serves this project site under /<repo>/, so assets and the
// data/ folder must resolve relative to that base. Use "/" for local dev.
export default defineConfig({
  base: "/UCSD-Reg-Analyzer/",
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
  },
});
