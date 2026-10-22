/**
 * Per-browser conveniences (tour dismissed, experimental recipes shown). Storage
 * can be missing or throw (private windows, blocked site data), so every access
 * is guarded and the UI works the same without it.
 */

const PREFIX = 'h3studio.'

export function readPref(key: string): string | null {
  try {
    return window.localStorage.getItem(PREFIX + key)
  } catch {
    return null
  }
}

export function writePref(key: string, value: string | null): void {
  try {
    if (value === null) window.localStorage.removeItem(PREFIX + key)
    else window.localStorage.setItem(PREFIX + key, value)
  } catch {
    // A convenience, not state: losing it is fine.
  }
}

export const PREF_TOUR_DONE = 'tour.v1.done'
export const PREF_SHOW_EXPERIMENTAL = 'recipes.showExperimental'
