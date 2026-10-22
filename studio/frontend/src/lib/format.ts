/** Small display formatters. Nothing here invents a metric the API did not send. */

export function formatSeconds(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds)) return '—'
  if (seconds < 60) return `${seconds < 10 ? seconds.toFixed(1) : Math.round(seconds)}s`
  const minutes = Math.floor(seconds / 60)
  const rest = Math.round(seconds % 60)
  if (rest === 60) return `${minutes + 1}m`
  return rest === 0 ? `${minutes}m` : `${minutes}m ${rest}s`
}

export function formatClock(seconds: number): string {
  const safe = Math.max(0, Math.floor(seconds))
  const minutes = Math.floor(safe / 60)
  const rest = safe % 60
  return `${minutes}:${String(rest).padStart(2, '0')}`
}

export function formatBytes(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined || !Number.isFinite(bytes)) return '—'
  if (bytes < 1024) return `${bytes} B`
  const units = ['KB', 'MB', 'GB']
  let value = bytes / 1024
  let unit = 0
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024
    unit += 1
  }
  return `${value < 10 ? value.toFixed(1) : Math.round(value)} ${units[unit]}`
}

/** SQLite timestamps are stored UTC-naive; treat them as UTC. */
export function parseTimestamp(value: string | null | undefined): Date | null {
  if (!value) return null
  const normalized = /(Z|[+-]\d{2}:?\d{2})$/.test(value) ? value : `${value}Z`
  const date = new Date(normalized)
  return Number.isNaN(date.getTime()) ? null : date
}

export function formatRelative(value: string | null | undefined, now: Date = new Date()): string {
  const date = parseTimestamp(value)
  if (!date) return '—'
  const delta = Math.round((now.getTime() - date.getTime()) / 1000)
  if (delta < 45) return 'ahora'
  if (delta < 3600) return `hace ${Math.round(delta / 60)} min`
  if (delta < 86_400) return `hace ${Math.round(delta / 3600)} h`
  if (delta < 7 * 86_400) return `hace ${Math.round(delta / 86_400)} d`
  return date.toLocaleDateString('es', { month: 'short', day: 'numeric' })
}

export function formatTimeOfDay(value: string | null | undefined): string {
  const date = parseTimestamp(value)
  if (!date) return '—'
  return date.toLocaleTimeString('es', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export function elapsedSeconds(startedAt: string | null, now: number): number | null {
  const date = parseTimestamp(startedAt)
  if (!date) return null
  return Math.max(0, (now - date.getTime()) / 1000)
}

export function formatPercent(fraction: number): string {
  return `${Math.round(Math.max(0, Math.min(1, fraction)) * 100)}%`
}
