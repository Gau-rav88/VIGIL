export type Timezone = "IST" | "UTC";

export function formatTime(ts: string | number | Date, tz: Timezone = "IST"): string {
  const d = new Date(ts);
  const timeZone = tz === "IST" ? "Asia/Kolkata" : "UTC";
  return new Intl.DateTimeFormat("en-GB", {
    timeZone,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(d);
}

export function formatDateTime(ts: string | number | Date, tz: Timezone = "IST"): string {
  const d = new Date(ts);
  const timeZone = tz === "IST" ? "Asia/Kolkata" : "UTC";
  return new Intl.DateTimeFormat("en-GB", {
    timeZone,
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(d);
}

export function formatRelativeTime(ts: string | number | Date): string {
  const now = Date.now();
  const past = new Date(ts).getTime();
  const diffSec = Math.max(0, Math.floor((now - past) / 1000));

  if (diffSec < 60) return `${diffSec}s ago`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  return `${diffDay}d ago`;
}
