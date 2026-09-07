/** Seconds to zero-padded HH:MM:SS, the same shape the transcript files use. */
export function formatTimecode(totalSeconds: number): string {
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  return [hours, minutes, seconds].map((n) => String(n).padStart(2, "0")).join(":");
}

/** First language of an Accept-Language header, or the fallback when absent or invalid. */
export function pickLocale(acceptLanguage: string | null, fallback = "en-GB"): string {
  const first = acceptLanguage?.split(",")[0]?.trim();
  if (!first) return fallback;
  try {
    return new Intl.Locale(first).toString();
  } catch {
    return fallback;
  }
}

/** Medium date in the reader's locale, e.g. "7 Sept 2026". */
export function formatDate(iso: string, locale: string): string {
  return new Intl.DateTimeFormat(locale, { dateStyle: "medium" }).format(new Date(iso));
}

/** Medium date plus short time in the reader's locale, e.g. "7 Sept 2026, 13:05". */
export function formatDateTime(iso: string, locale: string, timeZone?: string): string {
  return new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short", timeZone }).format(new Date(iso));
}
