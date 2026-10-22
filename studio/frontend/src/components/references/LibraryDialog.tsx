import { FolderOpen, ImagePlus, Music } from 'lucide-react'
import { useState, type ReactNode } from 'react'

import { useAssets } from '../../hooks/queries'
import { useReferenceIngest } from '../../hooks/useReferenceIngest'
import { formatSecondsEs } from '../../lib/guideSync'
import type { AssetOut, RefKind } from '../../lib/types'
import { Button } from '../ui/button'
import { Dialog, DialogPanel, DialogTrigger } from '../ui/dialog'
import { LazyVideo } from '../ui/lazy-video'
import { EmptyState, ErrorState } from '../ui/states'

const KIND_LABEL: Record<RefKind, string> = { image: 'Imagen', video: 'Vídeo', audio: 'Audio' }

/**
 * Everything already uploaded to this Studio. Picking an item adds it to the
 * current take through the same slot rules as an upload; nothing is re-uploaded
 * and no file is ever modified.
 */
export function LibraryDialog({ trigger, kinds }: { trigger?: ReactNode; kinds?: RefKind[] }) {
  const [open, setOpen] = useState(false)
  const library = useAssets()
  const { addFromLibrary } = useReferenceIngest()
  const items = (library.data ?? []).filter((asset) => !kinds || kinds.includes(asset.kind))

  const pick = (asset: AssetOut) => {
    if (addFromLibrary(asset)) setOpen(false)
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {trigger ?? (
          <Button variant="outline" size="sm">
            <FolderOpen aria-hidden />
            Biblioteca
          </Button>
        )}
      </DialogTrigger>
      <DialogPanel
        title="Biblioteca de referencias"
        description="Todo lo subido a este Studio. Elige un archivo para añadirlo a la toma actual; el original no se modifica."
      >
        {library.isLoading ? (
          <p className="text-xs text-faint">Cargando la biblioteca…</p>
        ) : library.isError ? (
          <ErrorState
            title="Biblioteca no disponible"
            message="No se pudo cargar la biblioteca de referencias."
            onRetry={() => void library.refetch()}
          />
        ) : items.length === 0 ? (
          <EmptyState icon={ImagePlus} title="Nada subido todavía" body="Sube un archivo desde la bandeja para empezar." />
        ) : (
          <ul className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {items.map((asset) => (
              <li key={asset.id}>
                <button
                  type="button"
                  onClick={() => pick(asset)}
                  aria-label={`Añadir ${asset.original_name}`}
                  className="w-full overflow-hidden rounded-xl border border-white/[0.07] bg-ink-850 text-left transition-colors hover:border-accent/50"
                >
                  <span className="block aspect-video bg-ink-950">
                    {asset.kind === 'image' ? (
                      <img src={asset.url} alt="" loading="lazy" className="size-full object-cover" />
                    ) : asset.kind === 'video' ? (
                      <LazyVideo src={asset.url} className="size-full object-cover" aria-hidden />
                    ) : (
                      <span className="flex size-full items-center justify-center">
                        <Music className="size-5 text-faint" aria-hidden />
                      </span>
                    )}
                  </span>
                  <span className="block truncate px-2 pt-1.5 text-[11px] font-medium text-fg">{asset.original_name}</span>
                  <span className="block truncate px-2 pb-1.5 text-[10px] text-faint">
                    {KIND_LABEL[asset.kind]}
                    {asset.width && asset.height ? ` · ${asset.width}×${asset.height}` : ''}
                    {asset.duration_seconds !== null ? ` · ${formatSecondsEs(asset.duration_seconds)}` : ''}
                    {asset.guide_provenance ? ' · guía preparada' : ''}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </DialogPanel>
    </Dialog>
  )
}
