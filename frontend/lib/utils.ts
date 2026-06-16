/**
 * Format ISO date string to readable format.
 * @param iso - ISO 8601 date string
 * @param includeSeconds - Whether to include seconds (default: false)
 */
export function formatTime(iso: string, includeSeconds = false): string {
  if (!iso) return ''
  const regex = includeSeconds
    ? /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})/
    : /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/
  const m = iso.match(regex)
  return m ? `${m[1]} ${m[2]}` : iso
}
