import { useCallback, useState } from 'react'

import { useToast } from '../components/ui/toast'
import { ApiError } from '../lib/api'
import { canAccept } from '../lib/references'
import type { AssetOut } from '../lib/types'
import { useComposer } from '../state/composer'
import { useAssetUpload } from './queries'

export interface UploadProgress {
  name: string
  fraction: number
}

/**
 * Upload → add-to-take, shared by the composer tray and the references panel so
 * both report the same progress, the same refusals and the same errors.
 */
export function useReferenceIngest() {
  const upload = useAssetUpload()
  const addAsset = useComposer((state) => state.addAsset)
  const { toast } = useToast()
  const [progress, setProgress] = useState<UploadProgress | null>(null)

  const ingest = useCallback(
    async (files: FileList | File[]) => {
      for (const file of Array.from(files)) {
        try {
          setProgress({ name: file.name, fraction: 0 })
          const asset = await upload.mutateAsync({
            file,
            onProgress: (fraction) => setProgress({ name: file.name, fraction }),
          })
          if (!addAsset(asset)) {
            toast({
              title: 'Subido, pero no añadido',
              description: `${asset.original_name} está en la biblioteca; esta tarea no tiene hueco libre para él.`,
              tone: 'info',
            })
          }
        } catch (error) {
          toast({
            title: `No se pudo añadir ${file.name}`,
            description: error instanceof ApiError ? error.message : 'La subida falló.',
            tone: 'error',
          })
        } finally {
          setProgress(null)
        }
      }
    },
    [addAsset, toast, upload],
  )

  const addFromLibrary = useCallback(
    (asset: AssetOut) => {
      const { mode, references } = useComposer.getState()
      const decision = canAccept(mode, references, asset.kind)
      if (!decision.ok) {
        toast({ title: 'Sin hueco libre', description: decision.reason, tone: 'info' })
        return false
      }
      return addAsset(asset)
    },
    [addAsset, toast],
  )

  return { ingest, addFromLibrary, progress, uploading: progress !== null }
}

export const ACCEPT_BY_KIND = {
  image: '.png,.jpg,.jpeg,.webp',
  video: '.mp4,.mov,.webm,.mkv',
  audio: '.wav,.mp3,.flac,.m4a,.ogg',
} as const

export const ACCEPT_ALL = `${ACCEPT_BY_KIND.image},${ACCEPT_BY_KIND.video},${ACCEPT_BY_KIND.audio}`
