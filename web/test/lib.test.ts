import { describe, expect, it } from "vitest";
import { buildRawUrl, parseCsv } from "../src/lib/raw";
import { alignForCompare, fillCurve, firstSeatRelease } from "../src/lib/analysis";

const NORMAL = `time,enrolled,available,waitlisted,total
2024-08-27T04:24:26,100,50,0,150
2024-08-27T08:00:00,130,20,0,150
2024-08-27T12:00:00,150,0,10,150
2024-08-28T00:00:00,150,0,25,150`;

const DEGRADED = `time,available,waitlisted,total
2022-02-01T00:00:00,40,0,40
2022-02-02T00:00:00,10,0,40`;

describe("buildRawUrl", () => {
  it("URL-encodes the course code and uses the overall path", () => {
    expect(buildRawUrl("2024Fall", "BILD 4")).toBe(
      "https://raw.githubusercontent.com/UCSD-Historical-Enrollment-Data/2024Fall/main/overall/BILD%204.csv",
    );
  });
});

describe("parseCsv", () => {
  it("parses the normal schema time-sorted", () => {
    const rows = parseCsv(NORMAL);
    expect(rows).toHaveLength(4);
    expect(rows[0].enrolled).toBe(100);
    expect(rows[0].total).toBe(150);
    expect(rows[0].time.getTime()).toBeLessThan(rows[3].time.getTime());
  });

  it("sets enrolled to null on the degraded schema", () => {
    const rows = parseCsv(DEGRADED);
    expect(rows).toHaveLength(2);
    expect(rows[0].enrolled).toBeNull();
    expect(rows[0].available).toBe(40);
  });

  it("returns [] for empty input", () => {
    expect(parseCsv("")).toEqual([]);
    expect(parseCsv("time,enrolled,available,waitlisted,total")).toEqual([]);
  });
});

describe("fillCurve", () => {
  it("computes (total - available) / total per row", () => {
    const rows = parseCsv(NORMAL);
    const pct = fillCurve(rows);
    expect(pct[0]).toBeCloseTo((150 - 50) / 150);
    expect(pct[2]).toBe(1); // available 0
  });

  it("is null when total is 0", () => {
    const rows = parseCsv(`time,enrolled,available,waitlisted,total
2024-08-01T00:00:00,0,0,0,0`);
    expect(fillCurve(rows)[0]).toBeNull();
  });
});

describe("firstSeatRelease", () => {
  it("returns the first row above the jump threshold", () => {
    const rows = parseCsv(`time,enrolled,available,waitlisted,total
2024-08-01T00:00:00,0,0,0,0
2024-08-02T00:00:00,0,150,0,150`);
    expect(firstSeatRelease(rows)?.toISOString()).toContain("2024-08-02");
  });

  it("returns null when total never moves", () => {
    const rows = parseCsv(`time,enrolled,available,waitlisted,total
2024-08-01T00:00:00,0,0,0,0`);
    expect(firstSeatRelease(rows)).toBeNull();
  });
});

describe("alignForCompare", () => {
  it("aligns to day 0 at seat release and keeps only non-negative days", () => {
    const rows = parseCsv(`time,enrolled,available,waitlisted,total
2024-08-01T00:00:00,0,0,0,0
2024-08-02T00:00:00,75,75,0,150
2024-08-04T00:00:00,150,0,0,150`);
    const pts = alignForCompare(rows);
    expect(pts[0].days_since_release).toBe(0);
    expect(pts[1].days_since_release).toBeCloseTo(2);
    expect(pts[1].pct_full).toBe(1);
  });

  it("returns [] when no release is detectable", () => {
    const rows = parseCsv(`time,enrolled,available,waitlisted,total
2024-08-01T00:00:00,0,0,0,0`);
    expect(alignForCompare(rows)).toEqual([]);
  });
});
