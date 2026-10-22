/* eslint-disable react-refresh/only-export-components -- test helpers intentionally export providers and utilities */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, type RenderOptions } from '@testing-library/react'
import type { ReactElement, ReactNode } from 'react'
import { vi } from 'vitest'

import { ToastProvider } from '../components/ui/toast'
import { TooltipProvider } from '../components/ui/tooltip'
import { createComposerState, useComposer } from '../state/composer'
import { useUi } from '../state/ui'

export function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
      mutations: { retry: false },
    },
  })
}

function Providers({ client, children }: { client: QueryClient; children: ReactNode }) {
  return (
    <QueryClientProvider client={client}>
      <TooltipProvider delayDuration={0}>
        <ToastProvider>{children}</ToastProvider>
      </TooltipProvider>
    </QueryClientProvider>
  )
}

export function renderWithProviders(ui: ReactElement, options?: RenderOptions) {
  const client = makeQueryClient()
  return {
    client,
    ...render(ui, { wrapper: ({ children }) => <Providers client={client}>{children}</Providers>, ...options }),
  }
}

/** Drop both stores back to their initial state between tests. */
export function resetStores() {
  useComposer.setState(createComposerState())
  useUi.setState({
    selectedJobId: null,
    activeJobId: null,
    inspectorTab: 'references',
    mobileView: 'compose',
    showHidden: false,
    showExperimental: false,
    tourStep: null,
    tourDone: false,
  })
}

export interface RouteStub {
  /** Substring matched against the request URL. */
  match: string
  method?: string
  status?: number
  body?: unknown
}

export interface FetchCall {
  url: string
  method: string
  body: unknown
}

/**
 * Route-table stub for `fetch`. Returns the recorded calls so a test can assert
 * that an action actually reached the API contract it claims to use.
 */
export function stubFetch(routes: RouteStub[]) {
  const calls: FetchCall[] = []

  const impl = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url
    const method = (init?.method ?? 'GET').toUpperCase()
    let parsed: unknown = null
    if (typeof init?.body === 'string') {
      try {
        parsed = JSON.parse(init.body)
      } catch {
        parsed = init.body
      }
    }
    calls.push({ url, method, body: parsed })

    const route = routes.find(
      (entry) => url.includes(entry.match) && (!entry.method || entry.method.toUpperCase() === method),
    )
    const status = route?.status ?? (route ? 200 : 404)
    const payload = route?.body ?? { detail: `No stub for ${method} ${url}` }

    return new Response(status === 204 ? null : JSON.stringify(payload), {
      status,
      headers: { 'Content-Type': 'application/json' },
    })
  })

  vi.stubGlobal('fetch', impl)
  return { calls, impl }
}
