"""Public request/response contracts for the Studio API."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .workflow.constants import (
    DEFAULT_SAMPLER,
    DEFAULT_SCHEDULER,
    DEFAULT_STEPS,
    DIMENSION_MAX,
    DIMENSION_MIN,
    EASYCACHE_DEFAULTS,
    FRAME_MAX,
    FRAME_MIN,
    SOL_DEFAULTS,
)


class Mode(str, Enum):
    text = "text"
    first_frame = "first_frame"
    first_last = "first_last"
    ref2va = "ref2va"
    performance = "performance"


class MethodId(str, Enum):
    baseline = "baseline"
    easycache = "easycache"
    w4a8_lightx2v = "w4a8_lightx2v"
    w4a8_lightx2v_trt = "w4a8_lightx2v_trt"
    w4a8_latent2x_refine3 = "w4a8_latent2x_refine3"
    ref2va_vsa = "ref2va_vsa"
    sage = "sage"
    sol = "sol"
    fast_h3_v2_8step = "fast_h3_v2_8step"
    taomate_3step = "taomate_3step"


class WeightVariant(str, Enum):
    int8 = "int8"
    gguf_q3km = "gguf_q3km"
    pinkcherry_v03 = "pinkcherry_v03"
    erosmax_beta4 = "erosmax_beta4"
    erosmax_beta5 = "erosmax_beta5"


class EncoderVariant(str, Enum):
    standard = "standard"
    heretic = "heretic"


class RefKind(str, Enum):
    image = "image"
    video = "video"
    audio = "audio"


class RefRole(str, Enum):
    # image roles
    first_frame = "first_frame"
    last_frame = "last_frame"
    identity = "identity"
    subject = "subject"
    scene = "scene"
    style = "style"
    prop = "prop"
    # video roles
    motion = "motion"
    scene_video = "scene_video"
    aligned_guide = "aligned_guide"
    # audio roles
    voice = "voice"
    ambience = "ambience"


IMAGE_ROLES = {
    RefRole.first_frame,
    RefRole.last_frame,
    RefRole.identity,
    RefRole.subject,
    RefRole.scene,
    RefRole.style,
    RefRole.prop,
}
VIDEO_ROLES = {RefRole.motion, RefRole.scene_video, RefRole.aligned_guide}
AUDIO_ROLES = {RefRole.voice, RefRole.ambience}

ROLES_BY_KIND: dict[RefKind, set[RefRole]] = {
    RefKind.image: IMAGE_ROLES,
    RefKind.video: VIDEO_ROLES,
    RefKind.audio: AUDIO_ROLES,
}


class Severity(str, Enum):
    error = "error"
    warning = "warning"
    info = "info"


class Issue(BaseModel):
    code: str
    message: str
    severity: Severity = Severity.error
    field: str | None = None


class EasyCacheOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reuse_threshold: float = Field(default=EASYCACHE_DEFAULTS["reuse_threshold"], ge=0.0, le=3.0)
    start_percent: float = Field(default=EASYCACHE_DEFAULTS["start_percent"], ge=0.0, le=1.0)
    end_percent: float = Field(default=EASYCACHE_DEFAULTS["end_percent"], ge=0.0, le=1.0)
    verbose: bool = False


class SolOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tau: float = Field(default=SOL_DEFAULTS["tau"], ge=0.0, le=4.0)
    start_percent: float = Field(default=SOL_DEFAULTS["start_percent"], ge=0.0, le=1.0)
    end_percent: float = Field(default=SOL_DEFAULTS["end_percent"], ge=0.0, le=1.0)
    min_tokens: int = Field(default=SOL_DEFAULTS["min_tokens"], ge=0, le=1_048_576)
    int8_qk: bool = SOL_DEFAULTS["int8_qk"]
    sink_conditioning: Literal["exact_kv", "exact_kv_and_rows", "off"] = SOL_DEFAULTS["sink_conditioning"]
    morton: bool = SOL_DEFAULTS["morton"]
    morton_curve: Literal["3d", "2d_frame"] = SOL_DEFAULTS["morton_curve"]
    verbose: bool = SOL_DEFAULTS["verbose"]
    use_tma: bool = SOL_DEFAULTS["use_tma"]


class ContinuityOptions(BaseModel):
    """Automatic long-take windowing for the reference RTX 4090 workstation RTX 4090 lane."""

    model_config = ConfigDict(extra="forbid")

    auto_split: bool = False
    window: Literal["auto", "243", "226", "209", "192", "175", "158", "141", "124", "107", "90"] = "auto"
    pin_frames: Literal["22", "5", "39", "56"] = "22"


class ReferenceInput(BaseModel):
    """One reference slot as the creator arranged it."""

    model_config = ConfigDict(extra="forbid")

    asset_id: str = Field(min_length=1, max_length=64)
    kind: RefKind
    role: RefRole
    #: For video references: also feed the clip's own soundtrack to the model.
    include_audio: bool = False

    @field_validator("role")
    @classmethod
    def _role_matches_kind(cls, role: RefRole, info: Any) -> RefRole:
        kind = info.data.get("kind")
        if kind is not None and role not in ROLES_BY_KIND[kind]:
            raise ValueError(f"role '{role.value}' is not valid for a {kind.value} reference")
        return role


class LoraInput(BaseModel):
    """One ordered model-only LoRA in the creator-visible chain."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    strength: float = Field(default=1.0, ge=-10.0, le=10.0)


class GenerationRequest(BaseModel):
    """Everything needed to build a workflow. Ordering of `references` is the
    creator-visible ordering and maps directly to <Picture i>/<Video k>/<Audio j>."""

    model_config = ConfigDict(extra="forbid")

    mode: Mode
    prompt: str = Field(min_length=1, max_length=20_000)
    width: int = Field(default=1024, ge=DIMENSION_MIN, le=DIMENSION_MAX)
    height: int = Field(default=576, ge=DIMENSION_MIN, le=DIMENSION_MAX)
    length: int = Field(default=124, ge=FRAME_MIN, le=FRAME_MAX)
    seed: int | None = Field(default=None, ge=0, le=18_446_744_073_709_551_615)
    steps: int = Field(default=DEFAULT_STEPS, ge=1, le=100)
    sampler_name: str = DEFAULT_SAMPLER
    scheduler: str = DEFAULT_SCHEDULER
    custom_sigmas: list[float] | None = Field(default=None, min_length=2, max_length=101)
    method: MethodId = MethodId.baseline
    easycache: EasyCacheOptions = Field(default_factory=EasyCacheOptions)
    sol: SolOptions = Field(default_factory=SolOptions)
    continuity: ContinuityOptions = Field(default_factory=ContinuityOptions)
    weights: WeightVariant = WeightVariant.int8
    encoder: EncoderVariant = EncoderVariant.standard
    lora_chain: list[LoraInput] = Field(default_factory=list, max_length=8)
    ref_image_size: Literal["match", "max"] = "match"
    references: list[ReferenceInput] = Field(default_factory=list, max_length=24)
    title: str | None = Field(default=None, max_length=120)
    preset_id: str | None = Field(default=None, max_length=64)


class _ManualGuidePromptGuard(BaseModel):
    @field_validator("references", check_fields=False)
    @classmethod
    def _manual_guides(cls, references: list[ReferenceInput]) -> list[ReferenceInput]:
        if any(r.role is RefRole.aligned_guide for r in references):
            raise ValueError("Aligned guides require a manual prompt; AI prompt tools do not yet understand guide-latent ownership.")
        return references


class DirectorRequest(_ManualGuidePromptGuard):
    """A non-destructive request for a locally generated H3 prompt preview."""

    model_config = ConfigDict(extra="forbid")
    mode: Mode
    prompt: str = Field(min_length=1, max_length=20_000)
    length: int = Field(default=124, ge=FRAME_MIN, le=FRAME_MAX)
    references: list[ReferenceInput] = Field(default_factory=list, max_length=24)


class DirectorAnalysis(BaseModel):
    asset_id: str
    token: str
    role: RefRole
    summary: str
    cached: bool


class DirectorResponse(BaseModel):
    original_prompt: str
    enhanced_prompt: str
    analyses: list[DirectorAnalysis]
    cached_analyses: int
    model: str


class PromptChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=12_000)


class PromptChatRequest(_ManualGuidePromptGuard):
    """Conversational H3 assistance using the local multimodal GPU writer."""

    model_config = ConfigDict(extra="forbid")
    mode: Mode
    current_prompt: str = Field(default="", max_length=20_000)
    length: int = Field(default=124, ge=FRAME_MIN, le=FRAME_MAX)
    references: list[ReferenceInput] = Field(default_factory=list, max_length=24)
    messages: list[PromptChatMessage] = Field(min_length=1, max_length=24)


class PromptChatResponse(BaseModel):
    message: str
    model: str
    visual_references: int = 0


class ValidationResponse(BaseModel):
    ok: bool
    issues: list[Issue]
    normalized: GenerationRequest | None = None
    estimate_seconds: float | None = None
    estimate_basis: str | None = None
    continuity_plan: "ContinuityPlan | None" = None


class ContinuityPlan(BaseModel):
    split: bool
    strategy: Literal["single", "context_pin"]
    window_frames: int
    window_count: int
    pin_frames: int
    sampled_frames: int
    rendered_frames: int
    delivered_frames: int
    trim_frames: int
    summary: str


class GuideProvenance(BaseModel):
    source_asset_id: str
    fit: Literal['pad', 'crop']
    start_seconds: float
    source_duration_seconds: float


class AssetOut(BaseModel):
    guide_provenance: GuideProvenance | None = None
    id: str
    kind: RefKind
    original_name: str
    stored_name: str
    mime: str
    size_bytes: int
    width: int | None = None
    height: int | None = None
    duration_seconds: float | None = None
    has_audio: bool | None = None
    created_at: str
    url: str


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    canceled = "canceled"


class OutputOut(BaseModel):
    id: str
    job_id: str
    kind: Literal["video", "audio", "image"]
    filename: str
    size_bytes: int
    url: str
    created_at: str


class JobOut(BaseModel):
    id: str
    status: JobStatus
    mode: Mode
    method: MethodId
    title: str | None
    prompt: str
    width: int
    height: int
    length: int
    seed: int
    steps: int
    progress: float
    stage: str | None
    queue_position: int | None
    error: str | None
    hidden: bool
    created_at: str
    started_at: str | None
    finished_at: str | None
    duration_seconds: float | None
    estimate_seconds: float | None
    comfy_prompt_id: str | None
    outputs: list[OutputOut] = Field(default_factory=list)
    request: GenerationRequest | None = None


class JobEventOut(BaseModel):
    """One line of the secondary activity log.

    The row is stored with a `ts` column; the API exposes it as `created_at`
    like every other timestamp in this file.
    """

    id: int
    job_id: str
    level: str
    message: str
    created_at: str = Field(validation_alias="ts")


class JobEventListResponse(BaseModel):
    events: list[JobEventOut]


class JobListResponse(BaseModel):
    jobs: list[JobOut]
    total: int


class CreateJobResponse(BaseModel):
    job: JobOut


class MethodInfo(BaseModel):
    id: str
    label: str
    blurb: str
    experimental: bool
    available: bool
    unavailable_reason: str | None = None
    measured_seconds: float | None = None
    measured_ssim: float | None = None
    measured_steps: int
    caveat: str


class ModeInfo(BaseModel):
    id: Mode
    label: str
    blurb: str
    available: bool
    unavailable_reason: str | None = None


class LoraInfo(BaseModel):
    name: str
    label: str
    recommended_strength: float = 1.0
    checkpoint: Literal["fl2va", "ref2va", "any"] = "any"
    note: str | None = None


class CapabilityResponse(BaseModel):
    aligned_guides: bool = False
    manual_sigmas: bool = False
    comfy_online: bool
    comfy_url: str
    source: Literal["live", "contract-fallback"]
    checked_at: str
    error: str | None = None
    modes: list[ModeInfo]
    methods: list[MethodInfo]
    weights: dict[str, bool]
    encoders: dict[str, bool]
    loras: list[LoraInfo]
    samplers: list[str]
    schedulers: list[str]
    preferred_lengths: list[dict[str, Any]]
    limits: dict[str, Any]
    benchmark_basis: dict[str, Any]


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    comfy_online: bool
    comfy_url: str
    active_jobs: int
    data_dir: str
