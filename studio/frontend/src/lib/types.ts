/**
 * Mirror of `backend/app/schemas.py`.
 *
 * Every type here corresponds 1:1 to a Pydantic model the Studio API actually
 * returns. Nothing is invented: if the backend does not send it, it is not in
 * this file.
 */

export type Mode = 'text' | 'first_frame' | 'first_last' | 'ref2va' | 'performance'

export type MethodId =
  | 'baseline'
  | 'easycache'
  | 'w4a8_lightx2v'
  | 'w4a8_lightx2v_trt'
  | 'w4a8_latent2x_refine3'
  | 'ref2va_vsa'
  | 'sage'
  | 'sol'
  | 'fast_h3_v2_8step'
  | 'taomate_3step'

export type WeightVariant = 'int8' | 'gguf_q3km' | 'pinkcherry_v03' | 'erosmax_beta4' | 'erosmax_beta5'
export type EncoderVariant = 'standard' | 'heretic'

export type RefKind = 'image' | 'video' | 'audio'

export type ImageRole = 'first_frame' | 'last_frame' | 'identity' | 'subject' | 'scene' | 'style' | 'prop'
export type VideoRole = 'motion' | 'scene_video' | 'aligned_guide'
export type AudioRole = 'voice' | 'ambience'
export type RefRole = ImageRole | VideoRole | AudioRole

export type Severity = 'error' | 'warning' | 'info'

export type RefImageSize = 'match' | 'max'

export interface Issue {
  code: string
  message: string
  severity: Severity
  field: string | null
}

export interface EasyCacheOptions {
  reuse_threshold: number
  start_percent: number
  end_percent: number
  verbose: boolean
}

export type SolSinkConditioning = 'exact_kv' | 'exact_kv_and_rows' | 'off'
export type SolMortonCurve = '3d' | '2d_frame'

export interface SolOptions {
  tau: number
  start_percent: number
  end_percent: number
  min_tokens: number
  int8_qk: boolean
  sink_conditioning: SolSinkConditioning
  morton: boolean
  morton_curve: SolMortonCurve
  verbose: boolean
  use_tma: boolean
}

export type ContinuityWindow = 'auto' | '243' | '226' | '209' | '192' | '175' | '158' | '141' | '124' | '107' | '90'
export type ContinuityPinFrames = '22' | '5' | '39' | '56'

export interface ContinuityOptions {
  auto_split: boolean
  window: ContinuityWindow
  pin_frames: ContinuityPinFrames
}

export interface ContinuityPlan {
  split: boolean
  strategy: 'single' | 'context_pin'
  window_frames: number
  window_count: number
  pin_frames: number
  sampled_frames: number
  rendered_frames: number
  delivered_frames: number
  trim_frames: number
  summary: string
}

export interface ReferenceInput {
  asset_id: string
  kind: RefKind
  role: RefRole
  include_audio: boolean
}

export interface LoraInput {
  name: string
  strength: number
}

export interface GenerationRequest {
  mode: Mode
  prompt: string
  width: number
  height: number
  length: number
  seed: number | null
  steps: number
  sampler_name: string
  scheduler: string
  custom_sigmas?: number[] | null
  method: MethodId
  easycache: EasyCacheOptions
  sol: SolOptions
  continuity: ContinuityOptions
  weights: WeightVariant
  encoder: EncoderVariant
  lora_chain: LoraInput[]
  ref_image_size: RefImageSize
  references: ReferenceInput[]
  title: string | null
  preset_id: string | null
}

export interface DirectorRequest {
  mode: Mode
  prompt: string
  length: number
  references: ReferenceInput[]
}

export interface DirectorAnalysis {
  asset_id: string
  token: string
  role: RefRole
  summary: string
  cached: boolean
}

export interface DirectorResponse {
  original_prompt: string
  enhanced_prompt: string
  analyses: DirectorAnalysis[]
  cached_analyses: number
  model: string
}

export interface PromptChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface PromptChatRequest {
  mode: Mode
  current_prompt: string
  length: number
  references: ReferenceInput[]
  messages: PromptChatMessage[]
}

export interface PromptChatResponse {
  message: string
  model: string
  visual_references: number
}

export interface ValidationResponse {
  ok: boolean
  issues: Issue[]
  normalized: GenerationRequest | null
  estimate_seconds: number | null
  estimate_basis: string | null
  continuity_plan: ContinuityPlan | null
}

export interface AssetOut {
  guide_provenance?: { source_asset_id: string; fit: 'pad' | 'crop'; start_seconds: number; source_duration_seconds: number } | null
  id: string
  kind: RefKind
  original_name: string
  stored_name: string
  mime: string
  size_bytes: number
  width: number | null
  height: number | null
  duration_seconds: number | null
  has_audio: boolean | null
  created_at: string
  url: string
}

export type JobStatus = 'queued' | 'running' | 'completed' | 'failed' | 'canceled'

export interface OutputOut {
  id: string
  job_id: string
  kind: 'video' | 'audio' | 'image'
  filename: string
  size_bytes: number
  url: string
  created_at: string
}

export interface JobOut {
  id: string
  status: JobStatus
  mode: Mode
  method: MethodId
  title: string | null
  prompt: string
  width: number
  height: number
  length: number
  seed: number
  steps: number
  progress: number
  stage: string | null
  queue_position: number | null
  error: string | null
  hidden: boolean
  created_at: string
  started_at: string | null
  finished_at: string | null
  duration_seconds: number | null
  estimate_seconds: number | null
  comfy_prompt_id: string | null
  outputs: OutputOut[]
  request: GenerationRequest | null
}

export interface JobListResponse {
  jobs: JobOut[]
  total: number
}

export interface JobEvent {
  id: number
  job_id: string
  level: string
  message: string
  created_at: string
}

export interface MethodInfo {
  id: MethodId
  label: string
  blurb: string
  experimental: boolean
  available: boolean
  unavailable_reason: string | null
  measured_seconds: number | null
  measured_ssim: number | null
  measured_steps?: number
  caveat: string
}

export interface ModeInfo {
  id: Mode
  label: string
  blurb: string
  available: boolean
  unavailable_reason: string | null
}

export interface LoraInfo {
  name: string
  label: string
  recommended_strength: number
  checkpoint: 'fl2va' | 'ref2va' | 'any'
  note: string | null
}

export interface LengthOption {
  frames: number
  seconds: number
  label: string
  native: boolean
}

export interface CapabilityLimits {
  max_ref_images: number
  max_ref_videos: number
  max_ref_audios: number
  max_ref_total: number
  max_ref_video_seconds: number
  min_ref_video_seconds: number
  max_ref_audio_seconds: number
  fps: number
  frame_step: number
  frame_base: number
  trained_frame_min: number
  trained_frame_max: number
  dimension_step: number
  dimension_min: number
  dimension_max: number
  max_steps: number
}

export interface CapabilityResponse {
  aligned_guides?: boolean
  comfy_online: boolean
  comfy_url: string
  source: 'live' | 'contract-fallback'
  checked_at: string
  error: string | null
  modes: ModeInfo[]
  methods: MethodInfo[]
  weights: Record<WeightVariant, boolean>
  encoders: Record<EncoderVariant, boolean>
  loras: LoraInfo[]
  samplers: string[]
  schedulers: string[]
  preferred_lengths: LengthOption[]
  limits: CapabilityLimits
  benchmark_basis: { seconds: number; width: number; height: number; steps: number }
}

export interface HealthResponse {
  status: 'ok' | 'degraded'
  version: string
  comfy_online: boolean
  comfy_url: string
  active_jobs: number
  data_dir: string
}

export interface Preset {
  /**
   * Requested curation contract (docs/ui-redesign/API-REQUESTS.md). Not sent by
   * the backend yet; the Studio falls back to `lib/curation.ts` when absent.
   */
  tier?: 'recommended' | 'standard' | 'experimental' | 'legacy'
  /** Kinjutsu backend curation. Not a statement that the models are installed. */
  group?: 'recommended' | 'control' | 'experimental'
  /** Kinjutsu: true only for the approved Character Swap HD Turbo8. */
  default?: boolean
  id: string
  label: string
  blurb: string
  suggests_mode: Mode | null
  patch: Partial<GenerationRequest> & { width: number; height: number; length: number; steps: number }
  recipe: string[]
  caveats: string[]
  needs: string[]
  recommended_duration_seconds: number
  estimate_seconds: number | null
  available: boolean
  unavailable_reason: string | null
}

export interface StudioConfig {
  version: string
  capabilities: CapabilityResponse
  presets: Preset[]
  defaults: {
    width: number
    height: number
    length: number
    steps: number
    sampler_name: string
    scheduler: string
    method: MethodId
    ref_image_size: RefImageSize
  }
  upload_limits: { image_mb: number; video_mb: number; audio_mb: number }
  estimate_basis: string
  method_profiles: Record<
    MethodId,
    { measured_seconds: number | null; measured_ssim: number | null; caveat: string }
  >
}

/* ---------------------------------------------------------------------------
 * Kinjutsu package routes (docs/MODEL-MANAGER-API.md, prompting/INTEGRATION.md).
 * Present only when the backend registers them; the UI detects them through
 * /api/openapi.json and never assumes they exist.
 * ------------------------------------------------------------------------- */

export interface ManagedModel {
  /** Opaque, stable manifest index. */
  id: string
  /** `<category>/<file>`, category one of loras, vae, diffusion_models, text_encoders. */
  target: string
  size: number
  sha256: string
  /** Shipped inside the package. */
  included: boolean
  installed: boolean
  verified: boolean
  /** Verified in an operator-authorized root outside the package; used in place, never copied. */
  reused: boolean
  revision: string
  repo: string
  /** Newer backends: readable name, role and the recipes that need this file. */
  label?: string
  role?: string
  required_by?: string[]
  /** Bytes of a `.part` kept from an interrupted download (0 when none). */
  partial_bytes?: number
  /** False when the partial is larger than the pinned size: inspect, do not resume. */
  partial_valid_size?: boolean
}

export interface ModelCatalog {
  manifest_sha256: string
  models: ManagedModel[]
  license_documents: string[]
  /** Free DISK space where models are written (not VRAM). */
  free_bytes?: number
}

export type DownloadStatus = 'queued' | 'downloading' | 'verifying' | 'installed' | 'cancelled' | 'error'

export interface ModelDownload {
  id: string
  status: DownloadStatus
  bytes: number
  total: number
  error: string | null
  reused?: boolean
}

export interface ModelStatus {
  downloads: ModelDownload[]
  restart_comfy_after_install: boolean
}

export type PromptTemplateId = 'character-swap-aligned' | 'motion-ref2va' | 't2va' | 'i2va' | 'fl2va' | 'l2va'

export interface PromptTemplateInfo {
  id: PromptTemplateId
  mode: string
  trigger: string | null
  section_style: string
  asset_roles: string[]
  additional_image_roles: string[]
  compatibility: {
    preset_ids: string[]
    aligned_guide: boolean
    ordinary_video_token: string | null
    changes_recipe: boolean
    changes_weights_or_loras: boolean
    submits_render: boolean
  }
  status: string
}

export interface PromptCatalog {
  version: number
  requires_agent: boolean
  requires_api_token: boolean
  templates: PromptTemplateInfo[]
}

export type FormAssetRole =
  | 'identity'
  | 'aligned_guide'
  | 'motion'
  | 'scene'
  | 'costume'
  | 'style'
  | 'first_frame'
  | 'last_frame'

export interface FormAsset {
  kind: 'image' | 'video' | 'aligned_guide'
  role: FormAssetRole
  token?: string
  description: string
}

export interface FormShot {
  start_seconds: number
  scene: string
  performance: string
  camera: string
  lighting: string
  sound: string
}

export interface FormDialogue {
  shot: number
  start_seconds: number
  end_seconds: number
  speaker: string
  language: string
  text: string
  delivery: string
  voiceover?: boolean
  subject?: 1
}

export interface PromptForm {
  duration_seconds: number
  identity: string
  style: string
  assets: FormAsset[]
  shots: FormShot[]
  audio: { soundscape: string; music: string; silent: boolean }
  dialogue: FormDialogue[]
}

export interface BuildPromptResponse {
  template: PromptTemplateId
  prompt: string
  requires_agent: false
  submits_render: false
}

/* ---------------------------------------------------------------------------
 * Local workstation control plane (docs/WORKSTATION-API.md). Loopback only:
 * remote/Tailnet clients get 403 by design. No route accepts paths or commands.
 * ------------------------------------------------------------------------- */

export type WorkstationState =
  | 'configuration_required'
  | 'online'
  | 'unhealthy'
  | 'port_conflict'
  | 'stopped'
  | 'starting'
  | 'configuration_changed'
  | 'launch_unverified'

export type FolderKind = 'models' | 'loras' | 'outputs'

export interface WorkstationStatus {
  state: WorkstationState
  selected_id: string | null
  label: string | null
  url: string | null
  capabilities: {
    start: boolean
    open_comfy: boolean
    select: boolean
    folders: Record<FolderKind, boolean>
  }
  automatic_downloads: boolean
  stop_supported: boolean
  generation_binding: 'not_selected' | 'matches' | 'different' | 'unknown'
}

export interface RuntimeCandidate {
  id: string
  label: string
  location: string
  /** Comfy answered health during this discovery. Not ownership or approval. */
  online: boolean
  approved: boolean
  configuration_required: boolean
}

export interface RootCandidate {
  id: string
  label: string
  location: string
  approved: boolean
  /** Null for roots already authorized in model-roots.json. */
  runtime_id: string | null
}

export interface WorkstationDiscovery {
  runtimes: RuntimeCandidate[]
  roots: RootCandidate[]
  limits: { max_roots: number; max_depth: number; max_results: number; budget_seconds: number }
  automatic_downloads: false
}

export interface SelectRuntimeResult {
  selected_id: string
  selected: boolean
  generation_routing_changed: false
}

export interface SelectRootResult {
  root_id: string
  verified_models: number
  reused: boolean
  external_comfy_mapping_changed: false
  restart_required: boolean
}

export type StartComfyResult = { state: 'online' | 'starting'; reused: boolean; log?: string }
