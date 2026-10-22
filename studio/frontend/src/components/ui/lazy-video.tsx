import { useEffect, useRef, useState, type VideoHTMLAttributes } from 'react'

/**
 * A muted preview that only fetches once it scrolls near the viewport. A
 * library of hundreds of clips should not open hundreds of range requests.
 */
export function LazyVideo({ src, ...props }: VideoHTMLAttributes<HTMLVideoElement> & { src: string }) {
  const ref = useRef<HTMLVideoElement>(null)
  const [near, setNear] = useState(false)
  const observable = typeof IntersectionObserver !== 'undefined'

  useEffect(() => {
    const node = ref.current
    if (!node || near || !observable) return
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setNear(true)
          observer.disconnect()
        }
      },
      { rootMargin: '200px' },
    )
    observer.observe(node)
    return () => observer.disconnect()
  }, [near, observable])

  return <video ref={ref} src={near || !observable ? src : undefined} muted playsInline preload="metadata" {...props} />
}
