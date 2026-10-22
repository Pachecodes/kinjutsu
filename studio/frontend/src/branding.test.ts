import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

import { BRAND } from './lib/brand'

describe('portable Studio branding', () => {
  it('uses the central product title in HTML and the primary wordmark', () => {
    const html = readFileSync('index.html', 'utf8')
    const app = readFileSync('src/App.tsx', 'utf8')
    expect(BRAND.product).toBe('Pachecodes : Kinjutsu')
    expect(BRAND.tagline).toBe('MiniMax H3 · reference RTX 4090 workstation')
    expect(BRAND.machine).toBe('reference RTX 4090 workstation')
    expect(html).toContain(`<title>${BRAND.product}</title>`)
    expect(html).toContain('lang="es"')
    expect(html).toContain('content="#101112"')
    expect(app).toContain('{BRAND.product}')
  })
})
