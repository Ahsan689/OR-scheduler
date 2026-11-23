export function pct(value: number): string {
  return `${value.toFixed(1)}%`;
}

export function minutes(value: number): string {
  if (value < 60) return `${Math.round(value)}m`;
  const hours = Math.floor(value / 60);
  const mins = Math.round(value % 60);
  return mins === 0 ? `${hours}h` : `${hours}h ${mins}m`;
}

export function rate(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function shortDate(iso: string): string {
  const date = new Date(iso);
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}
