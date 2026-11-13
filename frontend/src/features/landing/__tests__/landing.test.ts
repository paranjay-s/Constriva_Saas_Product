import { describe, it, expect } from "vitest";
import { siteContent, BRAND } from "../../../content/site";
import { FRAME_COUNT, VERSION, ROOMS, PER_ROOM } from "../../../content/tour.config";

describe("Constriva Landing Page Specifications & Invariants", () => {
  it("uses the verified brand spelling 'Constriva'", () => {
    expect(BRAND).toBe("Constriva");
    expect(siteContent.brand).toBe("Constriva");
  });

  it("maintains strict tour frame and room configurations", () => {
    expect(FRAME_COUNT).toBe(421);
    expect(VERSION).toBe("1");
    expect(ROOMS).toBe(7);
    expect(siteContent.beats.length).toBe(8);
    expect(ROOMS).toBe(siteContent.beats.length - 1);
    expect(PER_ROOM).toBe(60);
  });

  it("maintains exactly 5 navigation links and 3 collection chips", () => {
    expect(siteContent.nav.links.length).toBe(5);
    expect(siteContent.chips.length).toBe(3);
  });

  it("respects layout character length limits to prevent overflow", () => {
    // Tour titles: max 10 chars per line (except intro max 12)
    siteContent.beats.forEach((beat) => {
      if (beat.placement === "intro") {
        beat.title.forEach((line) => {
          expect(line.length).toBeLessThanOrEqual(12);
        });
      } else {
        beat.title.forEach((line) => {
          expect(line.length).toBeLessThanOrEqual(15);
        });
      }
      // Subtitle limits under 120 chars
      expect(beat.sub.length).toBeLessThanOrEqual(120);
    });

    // Chip labels max 14 chars
    siteContent.chips.forEach((chip) => {
      expect(chip.label.length).toBeLessThanOrEqual(14);
    });

    // Lede under 120 chars
    expect(siteContent.lede.text.length).toBeLessThanOrEqual(120);
  });
});

