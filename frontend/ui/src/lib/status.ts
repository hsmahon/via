/**
 * Map a lifecycle status onto display styling.
 *
 * @param status - Raw API status string.
 * @returns Tailwind-free CSS color class for the status chip.
 */
export function statusColor(status: string): string {
  switch (status) {
    case "PROCESSED":
      return "#1a7f37";
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
