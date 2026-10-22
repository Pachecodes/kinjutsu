/** React Query bindings for every Studio endpoint the UI touches. */

import { useMutation, useQuery, useQueryClient, type UseQueryResult } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'

import { api } from '../lib/api'
import type {
  AssetOut,
  GenerationRequest,
  HealthResponse,
  JobOut,
  JobStatus,
  StudioConfig,
  ValidationResponse,
} from '../lib/types'

export const queryKeys = {
  config: ['config'] as const,
  health: ['health'] as const,
  assets: ['assets'] as const,
  jobs: (includeHidden: boolean, statuses: JobStatus[]) => ['jobs', includeHidden, statuses] as const,
  job: (jobId: string) => ['job', jobId] as const,
  events: (jobId: string) => ['events', jobId] as const,
  validation: (request: GenerationRequest) => ['validate', request] as const,
}

const ACTIVE: JobStatus[] = ['queued', 'running']

/**
 * The already-loaded config, without subscribing or fetching. For leaf controls
 * that only need static recipe data (e.g. a recipe's own prompt) at click time.
 */
export function useCachedConfig(): () => StudioConfig | undefined {
  const client = useQueryClient()
  return () => client.getQueryData<StudioConfig>(queryKeys.config)
}

export function useConfig(): UseQueryResult<StudioConfig> {
  return useQuery({
    queryKey: queryKeys.config,
    queryFn: () => api.config(),
    staleTime: 20_000,
    retry: 1,
  })
}

export function useHealth(): UseQueryResult<HealthResponse> {
  return useQuery({
    queryKey: queryKeys.health,
    queryFn: () => api.health(),
    refetchInterval: 20_000,
    retry: false,
  })
}

export function useAssets(): UseQueryResult<AssetOut[]> {
  return useQuery({ queryKey: queryKeys.assets, queryFn: () => api.listAssets(), staleTime: 10_000 })
}

export function useAssetIndex(): Map<string, AssetOut> {
  const { data } = useAssets()
  return useMemo(() => new Map((data ?? []).map((asset) => [asset.id, asset])), [data])
}

interface JobsOptions {
  includeHidden: boolean
  statuses?: JobStatus[]
}

export function useJobs({ includeHidden, statuses = [] }: JobsOptions) {
  return useQuery({
    queryKey: queryKeys.jobs(includeHidden, statuses),
    queryFn: () => api.listJobs({ includeHidden, status: statuses, limit: 120 }),
    // Poll fast only while something is actually rendering.
    refetchInterval: (query) => {
      const jobs = query.state.data?.jobs ?? []
      return jobs.some((job) => ACTIVE.includes(job.status)) ? 1200 : 15_000
    },
    staleTime: 0,
  })
}

/** Follow one take closely while it is queued or rendering. */
export function useJob(jobId: string | null) {
  return useQuery({
    queryKey: queryKeys.job(jobId ?? 'none'),
    queryFn: () => api.getJob(jobId as string),
    enabled: Boolean(jobId),
    refetchInterval: (query) => (query.state.data && ACTIVE.includes(query.state.data.status) ? 900 : false),
  })
}

export function useJobEvents(jobId: string | null, active: boolean) {
  return useQuery({
    queryKey: queryKeys.events(jobId ?? 'none'),
    queryFn: () => api.jobEvents(jobId as string),
    enabled: Boolean(jobId),
    refetchInterval: active ? 2000 : false,
  })
}

/**
 * Live validation. Debounced so typing a prompt does not hammer the backend,
 * and keyed by the request itself so identical states reuse the same answer.
 */
export function useValidation(request: GenerationRequest, enabled: boolean) {
  // `request` is memoized upstream, so its identity only changes when the
  // composer actually changes — that is exactly the debounce trigger we want.
  const [debounced, setDebounced] = useState(request)

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(request), 400)
    return () => clearTimeout(timer)
  }, [request])

  return useQuery<ValidationResponse>({
    queryKey: queryKeys.validation(debounced),
    queryFn: ({ signal }) => api.validate(debounced, signal),
    enabled: enabled && debounced.prompt.trim().length > 0,
    staleTime: 30_000,
    retry: false,
    placeholderData: (previous) => previous,
  })
}

export function useJobMutations() {
  const client = useQueryClient()

  const invalidate = () => {
    void client.invalidateQueries({ queryKey: ['jobs'] })
    void client.invalidateQueries({ queryKey: queryKeys.health })
  }

  const create = useMutation({
    mutationFn: (request: GenerationRequest) => api.createJob(request),
    onSuccess: ({ job }) => {
      client.setQueryData(queryKeys.job(job.id), job)
      invalidate()
    },
  })

  const cancel = useMutation({
    mutationFn: (jobId: string) => api.cancelJob(jobId),
    onSuccess: (job: JobOut) => {
      client.setQueryData(queryKeys.job(job.id), job)
      invalidate()
    },
  })

  const setHidden = useMutation({
    mutationFn: ({ jobId, hidden }: { jobId: string; hidden: boolean }) => api.patchJob(jobId, { hidden }),
    onSuccess: (job: JobOut) => {
      client.setQueryData(queryKeys.job(job.id), job)
      invalidate()
    },
  })

  const remove = useMutation({
    mutationFn: (jobId: string) => api.deleteJob(jobId),
    onSuccess: (_data, jobId) => {
      client.removeQueries({ queryKey: queryKeys.job(jobId) })
      invalidate()
    },
  })

  const reuse = useMutation({
    mutationFn: ({ jobId, keepSeed }: { jobId: string; keepSeed: boolean }) => api.reuseJob(jobId, keepSeed),
  })

  return { create, cancel, setHidden, remove, reuse }
}

export function useAssetUpload() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ file, onProgress }: { file: File; onProgress?: (fraction: number) => void }) =>
      api.uploadAsset(file, { onProgress }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: queryKeys.assets })
    },
  })
}

export function useRefreshCapabilities() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: () => api.capabilities(true),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: queryKeys.config })
      void client.invalidateQueries({ queryKey: queryKeys.health })
    },
  })
}
