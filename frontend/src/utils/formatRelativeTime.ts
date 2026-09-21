/**
 * Formats an ISO timestamp as a short relative time string (e.g. "2m ago",
 * "just now"), used for lightweight "last updated" style indicators.
 */

export function formatRelativeTime(isoTimestamp: string): string {
  const then = new Date(isoTimestamp).getTime();
  if (Number.isNaN(then)) return isoTimestamp;

  const diffSeconds = Math.max(0, Math.round((Date.now() - then) / 1000));

  if (diffSeconds < 30) return 'just now';
  if (diffSeconds < 60) return `${diffSeconds}s ago`;

  const diffMinutes = Math.round(diffSeconds / 60);
  if (diffMinutes < 60) return `${diffMinutes}m ago`;

  const diffHours = Math.round(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours}h ago`;

  const diffDays = Math.round(diffHours / 24);
  return `${diffDays}d ago`;
}
