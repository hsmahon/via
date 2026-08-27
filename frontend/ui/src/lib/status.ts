/**
 * Video status display helpers for the dark workstation palette.
 * Exports `statusColor` (status → CSS color, PROCESSED maps to `var(--accent)` green) and `formatDuration` (seconds → "1m 05s" / "42s" / "-") used by `Library` rows and `VideoWorkspace` header.
 * Depends only on CSS tokens in `globals.css`; no runtime dependencies and safe to import in any client component.
 */

/**
 * Map a lifecycle status onto display styling for the dark palette.
 *
 * @param status - Raw API status string.
 * @returns CSS color for the status chip or dot (PROCESSED → `var(--accent)`).
 */
export function statusColor(status: string): string {
  switch (status) {
    case "PROCESSED":
      return "var(--accent)";
    case "PROCESSING":
      return "#9a6700";
    case "FAILED":
      return "#cf222e";
    case "DELETED":
      return "#57606a";
    default:
      return "#0969da";
  }
}

/**
 * Format a duration in seconds for compact display.
 *
 * @param seconds - Duration or null when unknown.
 * @returns Human-readable duration such as "1m 05s" or "42s".
 */
export function formatDuration(seconds: number | null): string {
  if (seconds === null || seconds <= 0) {
    return "-";
  }
  const total = Math.round(seconds);
  const minutes = Math.floor(total / 60);
  const rest = total % 60;
  return minutes > 0 ? `${minutes}m ${String(rest).padStart(2, "0")}s` : `${rest}s`;
}
