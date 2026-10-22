import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { CANCEL_COPY, MODE_COPY, PHASES } from '../lib/curation'
import { HELP } from '../lib/help'
import { CAMERA_OPTIONS } from '../lib/promptBuilder'
import { EN } from './en'
import { formatDecimal, getLocale, localized, t, useLocale } from './index'

/** Every interface source file (tests, fixtures and the catalog itself excluded). */
const SOURCES = import.meta.glob(['../**/*.{ts,tsx}', '!../**/*.test.{ts,tsx}', '!../test/**', '!./en.ts'], {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>

const KEY = /(?<![\w.])t\(\s*'((?:[^'\\\n]|\\.)*)'/g
const DYNAMIC = /(?<![\w.$]|function )t\((?!\s*[')])/g

function sourceKeys(): Map<string, string> {
  const keys = new Map<string, string>()
  for (const [file, text] of Object.entries(SOURCES)) {
    for (const match of text.matchAll(KEY)) {
      const key = match[1].replace(/\\(.)/g, '$1')
      if (!keys.has(key)) keys.set(key, file)
    }
  }
  return keys
}

const placeholders = (text: string) => [...text.matchAll(/\{(\w+)\}/g)].map((match) => match[1]).sort()

beforeEach(() => {
  window.localStorage.clear()
})
afterEach(() => {
  useLocale.setState({ locale: 'es' })
})

describe('English catalog', () => {
  it('scans real source files', () => {
    expect(Object.keys(SOURCES).length).toBeGreaterThan(40)
    expect(sourceKeys().size).toBeGreaterThan(400)
  })

  it('has an English entry for every interface string', () => {
    const missing = [...sourceKeys()].filter(([key]) => !(key in EN)).map(([key, file]) => `${file}: ${key}`)
    expect(missing).toEqual([])
  })

  it('has no stale entries left behind by removed copy', () => {
    const keys = sourceKeys()
    expect(Object.keys(EN).filter((key) => !keys.has(key))).toEqual([])
  })

  it('keeps every {placeholder} of the Spanish source', () => {
    const broken = Object.entries(EN)
      .filter(([key, value]) => placeholders(key).join() !== placeholders(value).join())
      .map(([key]) => key)
    expect(broken).toEqual([])
  })

  it('only translates string literals, so the catalog check above sees every key', () => {
    const dynamic = Object.entries(SOURCES).flatMap(([file, text]) =>
      [...text.matchAll(DYNAMIC)].map((match) => `${file}: ${text.slice(match.index, match.index + 40)}`),
    )
    expect(dynamic).toEqual([])
  })

  it('has no empty translations', () => {
    expect(Object.entries(EN).filter(([, value]) => !value.trim())).toEqual([])
  })
})

describe('t()', () => {
  it('returns the Spanish source in Spanish and the catalog entry in English', () => {
    useLocale.setState({ locale: 'es' })
    expect(t('Toma en cola')).toBe('Toma en cola')
    useLocale.setState({ locale: 'en' })
    expect(t('Toma en cola')).toBe('Take queued')
  })

  it('interpolates variables in both languages', () => {
    useLocale.setState({ locale: 'es' })
    expect(t('Se quitaron {n} referencias: esta tarea no las admite.', { n: 3 })).toBe(
      'Se quitaron 3 referencias: esta tarea no las admite.',
    )
    useLocale.setState({ locale: 'en' })
    expect(t('Se quitaron {n} referencias: esta tarea no las admite.', { n: 3 })).toBe(
      "Removed 3 references: this task doesn't support them.",
    )
  })

  it('falls back to Spanish for an unknown string instead of showing a key', () => {
    useLocale.setState({ locale: 'en' })
    expect(t('Texto sin traducir')).toBe('Texto sin traducir')
  })
})

describe('language preference', () => {
  it('persists the choice and updates the document language', () => {
    useLocale.getState().setLocale('en')
    expect(window.localStorage.getItem('h3studio.locale')).toBe('en')
    expect(document.documentElement.lang).toBe('en')
    expect(getLocale()).toBe('en')

    useLocale.getState().setLocale('es')
    expect(window.localStorage.getItem('h3studio.locale')).toBe('es')
    expect(document.documentElement.lang).toBe('es')
  })

  it('restores the stored choice on the next visit', async () => {
    window.localStorage.setItem('h3studio.locale', 'en')
    vi.resetModules()
    const fresh = await import('./index')
    expect(fresh.getLocale()).toBe('en')

    window.localStorage.setItem('h3studio.locale', 'es')
    vi.resetModules()
    const again = await import('./index')
    expect(again.getLocale()).toBe('es')
  })

  it('follows the browser language when nothing is stored', async () => {
    const language = vi.spyOn(window.navigator, 'language', 'get')
    language.mockReturnValue('es-MX')
    vi.resetModules()
    expect((await import('./index')).getLocale()).toBe('es')

    language.mockReturnValue('en-GB')
    vi.resetModules()
    expect((await import('./index')).getLocale()).toBe('en')
    language.mockRestore()
  })
})

describe('localized copy tables', () => {
  it('switch with the active language at access time', () => {
    useLocale.setState({ locale: 'es' })
    expect(MODE_COPY.text.label).toBe('Texto a vídeo')
    expect(PHASES.map((phase) => phase.label)).toContain('Renderizando')
    expect(HELP.steps.what).toBe('Iteraciones de muestreo.')

    useLocale.setState({ locale: 'en' })
    expect(MODE_COPY.text.label).toBe('Text to video')
    expect(PHASES.map((phase) => phase.label)).toContain('Rendering')
    expect(HELP.steps.what).toBe('Sampling iterations.')
    expect(Object.keys(CANCEL_COPY).length).toBeGreaterThan(0)
  })

  it('never translates the prompt text sent to H3, only its menu label', () => {
    useLocale.setState({ locale: 'es' })
    const spanish = CAMERA_OPTIONS.map((option) => ({ ...option }))
    useLocale.setState({ locale: 'en' })
    const english = CAMERA_OPTIONS.map((option) => ({ ...option }))
    expect(english.map((option) => option.text)).toEqual(spanish.map((option) => option.text))
    expect(english.map((option) => option.label)).not.toEqual(spanish.map((option) => option.label))
  })

  it('supports spreading, Object.keys and iteration', () => {
    const table = localized(() => ({ a: t('Toma en cola'), b: t('Toma oculta') }))
    useLocale.setState({ locale: 'en' })
    expect({ ...table }).toEqual({ a: 'Take queued', b: 'Take hidden' })
    expect(Object.keys(table)).toEqual(['a', 'b'])
  })
})

describe('numbers', () => {
  it('uses a decimal comma in Spanish and a point in English', () => {
    useLocale.setState({ locale: 'es' })
    expect(formatDecimal(5.1666, 2)).toBe('5,17')
    useLocale.setState({ locale: 'en' })
    expect(formatDecimal(5.1666, 2)).toBe('5.17')
  })
})
