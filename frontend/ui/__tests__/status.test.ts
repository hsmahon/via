/**
 * Unit tests for status display helpers.
 */
import { describe, expect, it } from "vitest";
import { formatDuration, statusColor } from "../src/lib/status";

describe("statusColor", () => {
  /** Processed videos render green. */
  it("maps PROCESSED to green", () => {
    expect(statusColor("PROCESSED")).toBe("#1a7f37");
  });

  /** Failed videos render red. */
  it("maps FAILED to red", () => {
    expect(statusColor("FAILED")).toBe("#cf222e");
  });

  /** Unknown statuses fall back to the default blue. */
  it("falls back to blue for unknown statuses", () => {
    expect(statusColor("SOMETHING_ELSE")).toBe("#0969da");
  });
});

describe("formatDuration", () => {
  /** Null durations render as a dash. */
  it("returns dash for null", () => {
    expect(formatDuration(null)).toBe("-");
  });

  /** Short durations stay in seconds. */
  it("formats seconds under a minute", () => {
    expect(formatDuration(42)).toBe("42s");
  });

  /** Longer durations switch to minutes + seconds. */
  it("formats minutes with padded seconds", () => {
    expect(formatDuration(65)).toBe("1m 05s");
  });
});
