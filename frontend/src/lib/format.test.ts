import { describe, expect, it } from "vitest";
import { addDays, daysBetween, describeRecurrence, isoDate, parseDate, relativeDue } from "./format";
import { validatePhotos } from "../features/photos";

describe("date helpers", () => {
  it("round-trips local dates without timezone shifts", () => {
    expect(isoDate(parseDate("2026-03-29"))).toBe("2026-03-29");
    expect(addDays("2026-02-28", 1)).toBe("2026-03-01");
    expect(daysBetween("2026-03-28", "2026-03-30")).toBe(2);
  });

  it("describes due dates relative to today", () => {
    expect(relativeDue("2026-03-10", "2026-03-10")).toBe("oggi");
    expect(relativeDue("2026-03-11", "2026-03-10")).toBe("domani");
    expect(relativeDue("2026-03-07", "2026-03-10")).toBe("3 giorni fa");
  });
});

describe("describeRecurrence", () => {
  it("covers every recurrence mode", () => {
    expect(describeRecurrence("once", null, null)).toBe("Una tantum");
    expect(describeRecurrence("interval", 14, null)).toBe("Ogni 14 giorni");
    expect(describeRecurrence("calendar", null, { kind: "weekly", weekdays: [0, 4] })).toBe("Ogni lunedì, venerdì");
    expect(describeRecurrence("calendar", null, { kind: "monthly", day: 31 })).toBe("Il giorno 31 di ogni mese");
  });
});

describe("validatePhotos", () => {
  const photo = (type: string, size = 10) => new File([new Uint8Array(size)], "x", { type });

  it("rejects unsupported formats, oversized files and too many photos", () => {
    expect(validatePhotos([photo("image/jpeg")])).toBeNull();
    expect(validatePhotos([photo("application/pdf")])).toMatch(/Formato non supportato/);
    expect(validatePhotos([photo("image/png", 2 * 1024 * 1024)], 0, 1)).toMatch(/supera il limite/);
    expect(validatePhotos([photo("image/webp")], 10)).toMatch(/al massimo 10/);
  });
});
