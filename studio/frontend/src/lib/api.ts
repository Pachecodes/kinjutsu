/**
 * Typed client for the Studio API.
 *
 * Every call goes to the same loopback origin that serves the SPA, so there is
 * no base URL, no credentials and no external service anywhere in this file.
 */

import type {
  AssetOut,
  FolderKind,
  SelectRootResult,
  SelectRuntimeResult,
  StartComfyResult,
  WorkstationDiscovery,
  WorkstationStatus,
  BuildPromptResponse,
  ModelCatalog,
  ModelDownload,
  ModelStatus,
  PromptCatalog,
  PromptForm,
  PromptTemplateId,
  CapabilityResponse,
  DirectorRequest,
  DirectorResponse,
  GenerationRequest,
  HealthResponse,
  Issue,
  JobEvent,
  JobListResponse,
  JobOut,
  JobStatus,
  PromptChatRequest,
  PromptChatResponse,
  StudioConfig,
  ValidationResponse,
} from './types'

export class ApiError extends Error {
  readonly status: number
  readonly code: string | null
  readonly issues: Issue[]

  constructor(message: string, options: { status: number; code?: string | null; issues?: Issue[] }) {
    super(message)
    this.name = 'ApiError'
    this.status = options.status
    this.code = options.code ?? null
    this.issues = options.issues ?? []
  }
}

type FastApiDetail =
  | string
  | { code?: string; message?: string }
  | Array<{ msg?: string; loc?: (string | number)[] }>

interface ErrorBody {
  detail?: FastApiDetail
  issues?: Issue[]
}

function describe(body: ErrorBody | null, status: number): { message: string; code: string | null } {
  const detail = body?.detail
  if (typeof detail === 'string' && detail.trim()) return { message: detail, code: null }
  if (Array.isArray(detail)) {
    const first = detail[0]
    const where = first?.loc?.filter((part) => part !== 'body').join('.')
    const msg = first?.msg ?? 'The request was rejected.'
    return { message: where ? `${where}: ${msg}` : msg, code: null }
  }
  if (detail && typeof detail === 'object') {
    return { message: detail.message ?? 'The request was rejected.', code: detail.code ?? null }
  }
  const issue = body?.issues?.[0]
  if (issue) return { message: issue.message, code: issue.code }
  return { message: `Request failed (${status}).`, code: null }
}

async function readError(response: Response): Promise<ApiError> {
  let body: ErrorBody | null
  try {
    body = (await response.json()) as ErrorBody
  } catch {
    body = null
  }
  const { message, code } = describe(body, response.status)
  return new ApiError(message, { status: response.status, code, issues: body?.issues ?? [] })
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, {
      ...init,
      headers: {
        Accept: 'application/json',
        ...(init?.body && !(init.body instanceof FormData) ? { 'Content-Type': 'application/json' } : {}),
        ...init?.headers,
      },
    })
  } catch {
    throw new ApiError('The Studio backend is unreachable. Is it running on this machine?', {
      status: 0,
      code: 'network_error',
    })
  }
  if (!response.ok) throw await readError(response)
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

function json(body: unknown): RequestInit {
  return { method: 'POST', body: JSON.stringify(body) }
}

export const api = {
  health: () => request<HealthResponse>('/api/health'),

  config: () => request<StudioConfig>('/api/config'),

  capabilities: (refresh = false) =>
    request<CapabilityResponse>(`/api/capabilities${refresh ? '?refresh=true' : ''}`),

  validate: (body: GenerationRequest, signal?: AbortSignal) =>
    request<ValidationResponse>('/api/validate', { ...json(body), signal }),

  enhancePrompt: (body: DirectorRequest) => request<DirectorResponse>('/api/director/enhance', json(body)),

  chatPrompt: (body: PromptChatRequest) => request<PromptChatResponse>('/api/director/chat', json(body)),

  prepareGuide: (assetId: string, body: { width: number; height: number; length: number; fit: 'pad' | 'crop'; start_seconds: number }) =>
    request<{ asset: AssetOut; source_asset_id: string; verified: { width: number; height: number; frame_count: number; fps: number }; fit: 'pad' | 'crop'; start_seconds: number }>(`/api/assets/${encodeURIComponent(assetId)}/prepare-guide`, json(body)),

  listAssets: () => request<AssetOut[]>('/api/assets'),

  deleteAsset: (assetId: string) => request<void>(`/api/assets/${assetId}`, { method: 'DELETE' }),

  createJob: (body: GenerationRequest) => request<{ job: JobOut }>('/api/jobs', json(body)),

  listJobs: (params: { includeHidden?: boolean; status?: JobStatus[]; limit?: number; offset?: number } = {}) => {
    const search = new URLSearchParams()
    if (params.includeHidden) search.set('include_hidden', 'true')
    for (const status of params.status ?? []) search.append('status', status)
    if (params.limit) search.set('limit', String(params.limit))
    if (params.offset) search.set('offset', String(params.offset))
    const query = search.toString()
    return request<JobListResponse>(`/api/jobs${query ? `?${query}` : ''}`)
  },

  getJob: (jobId: string) => request<JobOut>(`/api/jobs/${jobId}`),

  patchJob: (jobId: string, patch: { hidden?: boolean; title?: string }) =>
    request<JobOut>(`/api/jobs/${jobId}`, { method: 'PATCH', body: JSON.stringify(patch) }),

  cancelJob: (jobId: string) => request<JobOut>(`/api/jobs/${jobId}/cancel`, { method: 'POST' }),

  deleteJob: (jobId: string) => request<void>(`/api/jobs/${jobId}`, { method: 'DELETE' }),

  jobEvents: (jobId: string) => request<{ events: JobEvent[] }>(`/api/jobs/${jobId}/events`),

  reuseJob: (jobId: string, keepSeed: boolean) =>
    request<GenerationRequest>(`/api/jobs/${jobId}/reuse`, json({ keep_seed: keepSeed })),

  /** Route list from the backend's own OpenAPI document, for feature detection. */
  openapiPaths: async () => Object.keys((await request<{ paths?: Record<string, unknown> }>('/api/openapi.json')).paths ?? {}),
  modelCatalog: () => request<ModelCatalog>('/api/models/catalog'),
  modelStatus: () => request<ModelStatus>('/api/models/status'),
  installModel: (modelId: string) =>
    request<ModelDownload>(`/api/models/${encodeURIComponent(modelId)}/install`, json({ license_acknowledged: true })),
  cancelModel: (modelId: string) =>
    request<{ id: string; cancel_requested: boolean }>(`/api/models/${encodeURIComponent(modelId)}/cancel`, { method: 'POST' }),
  /** Plain text from the backend allowlist; render as text only, never as HTML. */
  licenseText: async (name: string) => {
    const response = await fetch(`/api/models/licenses/${encodeURIComponent(name)}`, { headers: { Accept: 'text/plain' } })
    if (!response.ok) throw await readError(response)
    return response.text()
  },
  workstationStatus: () => request<WorkstationStatus>('/api/workstation/status'),
  workstationDiscover: () => request<WorkstationDiscovery>('/api/workstation/discover'),
  selectRuntime: (candidateId: string) =>
    request<SelectRuntimeResult>('/api/workstation/select', json({ candidate_id: candidateId, acknowledge: true })),
  selectRoot: (candidateId: string) =>
    request<SelectRootResult>('/api/workstation/roots/select', json({ candidate_id: candidateId, acknowledge: true })),
  startComfy: () => request<StartComfyResult>('/api/workstation/comfy/start', json({})),
  openComfy: () => request<{ requested: boolean }>('/api/workstation/comfy/open', json({})),
  openFolder: (kind: FolderKind) =>
    request<{ kind: FolderKind; requested: boolean }>(`/api/workstation/folders/${kind}/open`, json({})),
  promptCatalog: () => request<PromptCatalog>('/api/prompting/catalog'),
  buildPrompt: (template: PromptTemplateId, input: PromptForm) =>
    request<BuildPromptResponse>('/api/prompting/build', json({ template, input })),
  downloadUrl: (outputId: string) => `/api/outputs/${outputId}/download`,

  outputUrl: (outputId: string) => `/api/outputs/${outputId}/file`,

  latestPreview: async () => {
    const response = await fetch('/api/preview', { headers: { Accept: 'application/json' }, cache: 'no-store' })
    if (response.status === 204) return null
    if (!response.ok) throw await readError(response)
    return (await response.json()) as {
      data_url: string
      width: number
      height: number
      step: number
      total: number
    }
  },

  /**
   * Uploads go through XHR rather than fetch: the reference panel shows real
   * byte progress for the 512 MB video ceiling, and fetch cannot report it.
   */
  uploadAsset(file: File, options: { onProgress?: (fraction: number) => void; signal?: AbortSignal } = {}) {
    return new Promise<AssetOut>((resolve, reject) => {
      const form = new FormData()
      form.append('file', file, file.name)
      const xhr = new XMLHttpRequest()
      xhr.open('POST', '/api/assets')
      xhr.responseType = 'json'

      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable && options.onProgress) options.onProgress(event.loaded / event.total)
      }
      xhr.onload = () => {
        const body = (xhr.response ?? null) as (ErrorBody & AssetOut) | null
        if (xhr.status >= 200 && xhr.status < 300 && body) {
          resolve(body as AssetOut)
          return
        }
        const { message, code } = describe(body, xhr.status)
        reject(new ApiError(message, { status: xhr.status, code }))
      }
      xhr.onerror = () =>
        reject(new ApiError('The upload could not reach the Studio backend.', { status: 0, code: 'network_error' }))
      xhr.onabort = () => reject(new ApiError('Upload canceled.', { status: 0, code: 'aborted' }))

      options.signal?.addEventListener('abort', () => xhr.abort(), { once: true })
      xhr.send(form)
    })
  },
}

export type Api = typeof api
