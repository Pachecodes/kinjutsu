import { useCallback, useSyncExternalStore } from 'react'

const NOOP = () => () => {}

/**
 * Subscribe to a media query. Uses `useSyncExternalStore` so the first render
 * already has the right answer — no layout flash, no setState-in-effect.
 * jsdom has no `matchMedia`, where this degrades to `false`.
 */
export function useMediaQuery(query: string): boolean {
  const subscribe = useCallback(
    (onChange: () => void) => {
      if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return NOOP()
      const list = window.matchMedia(query)
      list.addEventListener('change', onChange)
      return () => list.removeEventListener('change', onChange)
    },
    [query],
  )

  const getSnapshot = useCallback(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return false
    return window.matchMedia(query).matches
  }, [query])

  return useSyncExternalStore(subscribe, getSnapshot, () => false)
}

/** The desktop creator workspace starts at the `lg` breakpoint. */
export function useIsDesktop(): boolean {
  return useMediaQuery('(min-width: 1024px)')
}
