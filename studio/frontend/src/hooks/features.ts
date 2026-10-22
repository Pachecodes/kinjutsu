import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../lib/api'
import type { FolderKind, ModelStatus, WorkstationStatus } from '../lib/types'

export interface StudioFeatures {
  /** Kinjutsu model manager: catalog, status, install, cancel. */
  models: boolean
  /** Kinjutsu deterministic prompt templates: catalog and build. */
  prompting: boolean
  /** Local workstation control plane: status, discovery, select, Comfy and folders. */
  workstation: boolean
  /** Plain-text license documents served from an allowlist. */
  licenses: boolean
  /** Detection finished (successfully or not); before this, render neither variant. */
  ready: boolean
}

const NONE: StudioFeatures = { models: false, prompting: false, workstation: false, licenses: false, ready: false }

/**
 * What this backend actually serves, read from its OpenAPI document. A route
 * that is not registered never gets a button: the live source app and the
 * Kinjutsu package run the same UI.
 */
export function useFeatures(): StudioFeatures {
  const query = useQuery({
    queryKey: ['features'],
    queryFn: async (): Promise<Omit<StudioFeatures, 'ready'>> => {
      const paths = await api.openapiPaths()
      const has = (path: string) => paths.includes(path)
      return {
        models:
          has('/api/models/catalog') &&
          has('/api/models/status') &&
          has('/api/models/{model_id}/install') &&
          has('/api/models/{model_id}/cancel'),
        prompting: has('/api/prompting/catalog') && has('/api/prompting/build'),
        workstation: [
          '/api/workstation/status',
          '/api/workstation/discover',
          '/api/workstation/select',
          '/api/workstation/roots/select',
          '/api/workstation/comfy/start',
          '/api/workstation/comfy/open',
          '/api/workstation/folders/{kind}/open',
        ].every(has),
        licenses: has('/api/models/licenses/{name}'),
      }
    },
    staleTime: Infinity,
    retry: false,
  })
  if (query.data) return { ...query.data, ready: true }
  // No OpenAPI document means no optional routes: the base Studio still works.
  return query.isError ? { ...NONE, ready: true } : NONE
}

const ACTIVE = ['queued', 'downloading', 'verifying']

/**
 * The catalog hashes every candidate file (tens of GB), so it only runs when the
 * creator asks, never on page load and never on an interval.
 */
export function useModelCatalog(enabled: boolean) {
  return useQuery({
    queryKey: ['models', 'catalog'],
    queryFn: api.modelCatalog,
    enabled,
    staleTime: Infinity,
    gcTime: Infinity,
    retry: false,
    refetchOnWindowFocus: false,
  })
}

/** Cheap in-memory job list; polled only while a download is moving. */
export function useModelStatus(enabled: boolean) {
  return useQuery({
    queryKey: ['models', 'status'],
    queryFn: api.modelStatus,
    enabled,
    refetchInterval: (query) =>
      (query.state.data as ModelStatus | undefined)?.downloads.some((job) => ACTIVE.includes(job.status)) ? 1500 : false,
  })
}

export function useModelMutations() {
  const client = useQueryClient()
  const refreshStatus = () => void client.invalidateQueries({ queryKey: ['models', 'status'] })
  const install = useMutation({ mutationFn: (modelId: string) => api.installModel(modelId), onSettled: refreshStatus })
  const cancel = useMutation({ mutationFn: (modelId: string) => api.cancelModel(modelId), onSettled: refreshStatus })
  return { install, cancel }
}

export function usePromptCatalog(enabled: boolean) {
  return useQuery({ queryKey: ['prompting', 'catalog'], queryFn: api.promptCatalog, enabled, staleTime: Infinity, retry: false })
}

/**
 * Read-only workstation state. GET only; it is polled solely while an owned
 * Comfy start is still `starting`, and never triggers an action.
 */
export function useWorkstationStatus(enabled: boolean) {
  return useQuery({
    queryKey: ['workstation', 'status'],
    queryFn: api.workstationStatus,
    enabled,
    retry: false,
    refetchInterval: (query) => ((query.state.data as WorkstationStatus | undefined)?.state === 'starting' ? 2000 : false),
  })
}

/** Bounded discovery runs only when the creator presses «Buscar instalaciones». */
export function useWorkstationDiscovery(enabled: boolean) {
  return useQuery({
    queryKey: ['workstation', 'discover'],
    queryFn: api.workstationDiscover,
    enabled,
    retry: false,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  })
}

/** Every workstation POST, each fired only from an explicit button. */
export function useWorkstationActions() {
  const client = useQueryClient()
  const refresh = () => void client.invalidateQueries({ queryKey: ['workstation', 'status'] })
  return {
    selectRuntime: useMutation({ mutationFn: api.selectRuntime, onSettled: refresh }),
    selectRoot: useMutation({
      mutationFn: api.selectRoot,
      onSettled: () => {
        refresh()
        // Shared roots change what the model manager can verify.
        void client.invalidateQueries({ queryKey: ['models', 'catalog'] })
      },
    }),
    start: useMutation({ mutationFn: api.startComfy, onSettled: refresh }),
    open: useMutation({ mutationFn: api.openComfy }),
    folder: useMutation({ mutationFn: (kind: FolderKind) => api.openFolder(kind) }),
  }
}

export function useLicenseText(name: string | null) {
  return useQuery({
    queryKey: ['models', 'license', name],
    queryFn: () => api.licenseText(name as string),
    enabled: Boolean(name),
    staleTime: Infinity,
    retry: false,
  })
}
