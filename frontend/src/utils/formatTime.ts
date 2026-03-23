/**
 * "Just now", "5m ago", "2h ago", "3d ago", or "Mar 12, 2025"
 */
export function formatRelativeTime(isoString: string): string {
  try {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffSecs = Math.floor(diffMs / 1000);
    const diffMins = Math.floor(diffSecs / 60);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffDays > 30) {
      return date.toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
        year: "numeric",
      });
    }
    if (diffDays > 0) return `${diffDays}d ago`;
    if (diffHours > 0) return `${diffHours}h ago`;
    if (diffMins > 0) return `${diffMins}m ago`;
    return "Just now";
  } catch {
    return isoString;
  }
}

/**
 * "Mar 12, 2025 at 10:30 AM"
 */
export function formatDateTime(isoString: string): string {
  try {
    const date = new Date(isoString);
    return date.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return isoString;
  }
}

/**
 * "45s", "2m 30s", or "1h 15m"
 */
export function formatDuration(seconds: number): string {
  const abs = Math.abs(seconds);
  const sign = seconds < 0 ? "-" : "";

  if (abs < 60) return `${sign}${Math.round(abs)}s`;

  const h = Math.floor(abs / 3600);
  const m = Math.floor((abs % 3600) / 60);
  const s = Math.round(abs % 60);

  if (h > 0) return `${sign}${h}h ${m}m`;
  return `${sign}${m}m ${s}s`;
}
