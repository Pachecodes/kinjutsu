import type {
  AssetOut,
  CapabilityResponse,
  GenerationRequest,
  JobOut,
  Preset,
  StudioConfig,
  ValidationResponse,
} from '../lib/types'

let counter = 0
const nextId = (prefix: string) => `${prefix}-${(counter += 1)}`

export function makeAsset(overrides: Partial<AssetOut> = {}): AssetOut {
  const id = overrides.id ?? nextId('asset')
  return {
    id,
    kind: 'image',
    original_name: 'reference.png',
    stored_name: `${id}.png`,
    mime: 'image/png',
    size_bytes: 204_800,
    width: 1024,
    height: 576,
    duration_seconds: null,
    has_audio: null,
    created_at: '2026-08-04T12:00:00',
    url: `/api/assets/${id}/file`,
    ...overrides,
  }
}

export function makeVideoAsset(overrides: Partial<AssetOut> = {}): AssetOut {
  return makeAsset({
    kind: 'video',
    original_name: 'motion.mp4',
    mime: 'video/mp4',
    duration_seconds: 6,
    has_audio: true,
    ...overrides,
  })
}

export function makeAudioAsset(overrides: Partial<AssetOut> = {}): AssetOut {
  return makeAsset({
    kind: 'audio',
    original_name: 'voice.wav',
    mime: 'audio/wav',
    width: null,
    height: null,
    duration_seconds: 9,
    has_audio: true,
    ...overrides,
  })
}

export function makeCapabilities(overrides: Partial<CapabilityResponse> = {}): CapabilityResponse {
  return {
    comfy_online: true,
    comfy_url: 'http://127.0.0.1:8216',
    source: 'live',
    checked_at: '2026-08-04T12:00:00',
    error: null,
    modes: [
      { id: 'text', label: 'Text to video', blurb: 'Prompt only.', available: true, unavailable_reason: null },
      {
        id: 'first_frame',
        label: 'First frame',
        blurb: 'Start from one still.',
        available: true,
        unavailable_reason: null,
      },
      {
        id: 'first_last',
        label: 'First + last frame',
        blurb: 'Pin both ends.',
        available: true,
        unavailable_reason: null,
      },
      { id: 'ref2va', label: 'References', blurb: 'Up to 12 refs.', available: true, unavailable_reason: null },
      {
        id: 'performance',
        label: 'Performance transfer',
        blurb: 'Identity plus motion.',
        available: true,
        unavailable_reason: null,
      },
    ],
    methods: [
      {
        id: 'baseline',
        label: 'Quality',
        blurb: 'The reference render.',
        experimental: false,
        available: true,
        unavailable_reason: null,
        measured_seconds: 79.98,
        measured_ssim: null,
        caveat: 'Slowest, and the render every other profile is compared against.',
      },
      {
        id: 'easycache',
        label: 'Fast Preview',
        blurb: 'Reuses stable sampling steps.',
        experimental: false,
        available: true,
        unavailable_reason: null,
        measured_seconds: 57.53,
        measured_ssim: 0.914,
        caveat: '~28% faster, SSIM 0.914.',
      },
      {
        id: 'sage',
        label: 'Sage',
        blurb: 'Memory-efficient attention.',
        experimental: true,
        available: true,
        unavailable_reason: null,
        measured_seconds: 76.06,
        measured_ssim: 0.861,
        caveat: 'Experimental.',
      },
      {
        id: 'sol',
        label: 'SolAttn',
        blurb: 'Sparse research patch.',
        experimental: true,
        available: false,
        unavailable_reason: 'SolAttnPatch is not installed on this Comfy instance.',
        measured_seconds: 82.99,
        measured_ssim: 0.778,
        caveat: 'Experimental, never a default.',
      },
    ],
    weights: { int8: true, gguf_q3km: true, pinkcherry_v03: true, erosmax_beta4: true, erosmax_beta5: true },
    encoders: { standard: true, heretic: true },
    loras: [
      {
        name: 'PinkFluffyBunny-alpha-lora.safetensors',
        label: 'Pink Fluffy Bunny (alpha)',
        recommended_strength: 0.5,
        checkpoint: 'fl2va',
        note: 'Alpha LoRA for FL2VA.',
      },
    ],
    samplers: ['res_multistep', 'euler'],
    schedulers: ['beta', 'simple'],
    preferred_lengths: [
      { frames: 124, seconds: 5.167, label: '5.17s', native: true },
      { frames: 175, seconds: 7.292, label: '7.29s', native: true },
      { frames: 192, seconds: 8, label: '8.00s', native: true },
      { frames: 243, seconds: 10.125, label: '10.13s', native: true },
      { frames: 362, seconds: 15.083, label: '15.08s', native: true },
    ],
    limits: {
      max_ref_images: 9,
      max_ref_videos: 3,
      max_ref_audios: 3,
      max_ref_total: 12,
      max_ref_video_seconds: 15,
      min_ref_video_seconds: 2,
      max_ref_audio_seconds: 15,
      fps: 24,
      frame_step: 17,
      frame_base: 5,
      trained_frame_min: 124,
      trained_frame_max: 362,
      dimension_step: 32,
      dimension_min: 32,
      dimension_max: 1536,
      max_steps: 100,
    },
    benchmark_basis: { seconds: 5.17, width: 608, height: 352, steps: 16 },
    ...overrides,
  }
}

export function makePreset(overrides: Partial<Preset> = {}): Preset {
  return {
    id: 'fast-preview-5s',
    label: 'Fast Preview 5s',
    blurb: 'Cheapest honest look at an idea.',
    suggests_mode: 'text',
    patch: {
      length: 124,
      width: 832,
      height: 480,
      steps: 16,
      method: 'easycache',
      scheduler: 'beta',
      sampler_name: 'res_multistep',
      ref_image_size: 'match',
    },
    recipe: ['5.17s at 832x480, 16 steps'],
    caveats: ['EasyCache softens fine detail.'],
    needs: [],
    recommended_duration_seconds: 5.167,
    estimate_seconds: 45.4,
    available: true,
    unavailable_reason: null,
    ...overrides,
  }
}

export function makeConfig(overrides: Partial<StudioConfig> = {}): StudioConfig {
  return {
    version: '0.1.0',
    capabilities: makeCapabilities(),
    presets: [makePreset()],
    defaults: {
      width: 1024,
      height: 576,
      length: 124,
      steps: 20,
      sampler_name: 'res_multistep',
      scheduler: 'beta',
      method: 'baseline',
      ref_image_size: 'match',
    },
    upload_limits: { image_mb: 32, video_mb: 512, audio_mb: 128 },
    estimate_basis: 'Scaled from a measured reference RTX 4090 workstation run.',
    method_profiles: {
      baseline: { measured_seconds: 79.98, measured_ssim: null, caveat: 'Reference render.' },
      easycache: { measured_seconds: 57.53, measured_ssim: 0.914, caveat: 'Softens fine detail.' },
      w4a8_lightx2v: { measured_seconds: 94.44, measured_ssim: null, caveat: 'Frame-driven only.' },
      w4a8_lightx2v_trt: { measured_seconds: 63.445, measured_ssim: null, caveat: 'TRT decode-only.' },
      w4a8_latent2x_refine3: { measured_seconds: 171.17, measured_ssim: null, caveat: 'Verified premium pipeline.' },
      ref2va_vsa: { measured_seconds: 94.299, measured_ssim: null, caveat: 'References mode only.' },
      sage: { measured_seconds: 76.06, measured_ssim: 0.861, caveat: 'Experimental.' },
      sol: { measured_seconds: 82.99, measured_ssim: 0.778, caveat: 'Experimental.' },
      fast_h3_v2_8step: { measured_seconds: null, measured_ssim: null, caveat: 'Unvalidated.' },
      taomate_3step: { measured_seconds: null, measured_ssim: null, caveat: 'Unvalidated.' },
    },
    ...overrides,
  }
}

export function makeRequest(overrides: Partial<GenerationRequest> = {}): GenerationRequest {
  return {
    mode: 'text',
    prompt: 'A lighthouse at dusk.',
    width: 1024,
    height: 576,
    length: 124,
    seed: null,
    steps: 20,
    sampler_name: 'res_multistep',
    scheduler: 'beta',
    method: 'baseline',
    easycache: { reuse_threshold: 0.3, start_percent: 0.2, end_percent: 0.9, verbose: false },
    sol: {
      tau: 1.3,
      start_percent: 0.2,
      end_percent: 0.9,
      min_tokens: 4096,
      int8_qk: true,
      sink_conditioning: 'exact_kv_and_rows',
      morton: false,
      morton_curve: '2d_frame',
      verbose: false,
      use_tma: false,
    },
    continuity: { auto_split: true, window: 'auto', pin_frames: '22' },
    weights: 'int8',
    encoder: 'standard',
    lora_chain: [],
    ref_image_size: 'match',
    references: [],
    title: null,
    preset_id: null,
    ...overrides,
  }
}

export function makeValidation(overrides: Partial<ValidationResponse> = {}): ValidationResponse {
  return {
    ok: true,
    issues: [],
    normalized: makeRequest(),
    estimate_seconds: 62.3,
    estimate_basis: 'Scaled from a measured reference RTX 4090 workstation run.',
    continuity_plan: {
      split: false,
      strategy: 'single',
      window_frames: 141,
      window_count: 1,
      pin_frames: 22,
      sampled_frames: 124,
      rendered_frames: 124,
      delivered_frames: 124,
      trim_frames: 0,
      summary: 'Safe as one window.',
    },
    ...overrides,
  }
}

export function makeJob(overrides: Partial<JobOut> = {}): JobOut {
  const id = overrides.id ?? nextId('job')
  return {
    id,
    status: 'completed',
    mode: 'text',
    method: 'baseline',
    title: 'Lighthouse',
    prompt: 'A lighthouse at dusk.',
    width: 1024,
    height: 576,
    length: 124,
    seed: 42,
    steps: 20,
    progress: 1,
    stage: 'Done',
    queue_position: null,
    error: null,
    hidden: false,
    created_at: '2026-08-04T12:00:00',
    started_at: '2026-08-04T12:00:01',
    finished_at: '2026-08-04T12:01:20',
    duration_seconds: 79,
    estimate_seconds: 80,
    comfy_prompt_id: 'prompt-1',
    outputs: [
      {
        id: `${id}-out`,
        job_id: id,
        kind: 'video',
        filename: 'take.mp4',
        size_bytes: 4_000_000,
        url: `/api/outputs/${id}-out/file`,
        created_at: '2026-08-04T12:01:20',
      },
    ],
    request: makeRequest(),
    ...overrides,
  }
}
