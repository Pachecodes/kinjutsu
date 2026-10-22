/**
 * Minimal, dependency-free i18n for Studio (Spanish and English).
 *
 * Keys are the Spanish source strings themselves (gettext style): the code
 * stays readable, and a missing English entry degrades to Spanish instead of a
 * raw key. Only interface copy is translated. Never pass prompts, dialogue,
 * file names, backend messages or API/model/recipe identifiers through `t`.
 */

import { create } from 'zustand'

import { readPref, writePref } from '../lib/prefs'
import { EN } from './en'

export type Locale = 'es' | 'en'
export const LOCALES: Locale[] = ['es', 'en']
export const PREF_LOCALE = 'locale'

export const LOCALE_NAME: Record<Locale, string> = { es: 'Español', en: 'English' }

function initialLocale(): Locale {
  const stored = readPref(PREF_LOCALE)
  if (stored === 'es' || stored === 'en') return stored
  const browser = typeof navigator !== 'undefined' ? navigator.language : 'es'
  return browser.toLowerCase().startsWith('es') ? 'es' : 'en'
}

function applyDocumentLanguage(locale: Locale) {
  if (typeof document !== 'undefined') document.documentElement.lang = locale
}

interface LocaleState {
  locale: Locale
  setLocale: (locale: Locale) => void
}

export const useLocale = create<LocaleState>((set) => ({
  locale: initialLocale(),
  setLocale: (locale) => {
    writePref(PREF_LOCALE, locale)
    applyDocumentLanguage(locale)
    set({ locale })
  },
}))

applyDocumentLanguage(useLocale.getState().locale)

export function getLocale(): Locale {
  return useLocale.getState().locale
}

export type Vars = Record<string, string | number>

function interpolate(text: string, vars?: Vars): string {
  if (!vars) return text
  return text.replace(/\{(\w+)\}/g, (match, name: string) => (name in vars ? String(vars[name]) : match))
}

/** Translate a Spanish source string into the active language. */
export function t(source: string, vars?: Vars): string {
  const text = getLocale() === 'en' ? (EN[source] ?? source) : source
  return interpolate(text, vars)
}

/**
 * Subscribe a component to the active language and get `t`. Re-rendering the
 * root is enough for children, but leaf components that render outside the
 * main tree (portals created later) also call this.
 */
export function useT(): typeof t {
  useLocale((state) => state.locale)
  return t
}

/**
 * A copy table whose strings follow the active language. The factory runs per
 * language (cached), so existing call sites like `HELP.steps.what` keep working.
 */
export function localized<T extends object>(factory: () => T): T {
  const cache: Partial<Record<Locale, T>> = {}
  const current = (): T => {
    const locale = getLocale()
    cache[locale] ??= factory()
    return cache[locale] as T
  }
  return new Proxy({} as T, {
    get: (_target, key) => {
      const value = Reflect.get(current(), key)
      return typeof value === 'function' ? value.bind(current()) : value
    },
    has: (_target, key) => Reflect.has(current(), key),
    ownKeys: () => Reflect.ownKeys(current()),
    getOwnPropertyDescriptor: (_target, key) => {
      const descriptor = Reflect.getOwnPropertyDescriptor(current(), key)
      return descriptor ? { ...descriptor, configurable: true } : undefined
    },
  })
}

/** A localized array (e.g. menu options). Iteration and `.map` work as usual. */
export function localizedList<T>(factory: () => T[]): T[] {
  const cache: Partial<Record<Locale, T[]>> = {}
  const current = (): T[] => {
    const locale = getLocale()
    cache[locale] ??= factory()
    return cache[locale] as T[]
  }
  return new Proxy([] as T[], {
    get: (_target, key) => {
      const list = current()
      const value = Reflect.get(list, key)
      return typeof value === 'function' ? value.bind(list) : value
    },
    has: (_target, key) => Reflect.has(current(), key),
    ownKeys: () => Reflect.ownKeys(current()),
    getOwnPropertyDescriptor: (_target, key) => Reflect.getOwnPropertyDescriptor(current(), key),
  })
}

/** Locale-aware number with fixed decimals (5,17 vs 5.17). */
export function formatDecimal(value: number, digits: number): string {
  return value.toLocaleString(getLocale() === 'es' ? 'es-ES' : 'en-US', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
    useGrouping: false,
  })
}

export function formatInteger(value: number): string {
  return value.toLocaleString(getLocale() === 'es' ? 'es-ES' : 'en-US')
}
