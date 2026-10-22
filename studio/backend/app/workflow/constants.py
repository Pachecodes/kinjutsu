"""Hard facts about the live H3 lab install.

Everything here is derived from `docs/contracts/h3-node-contracts.json` and the
measured reference RTX 4090 workstation benchmark table in CLAUDE.md. Nothing may be invented: if a
node name, input name or checkpoint file is not in the contract, it does not
belong in this file.
"""

from __future__ import annotations

from typing import Final

# --- Checkpoints ----------------------------------------------------------
FL2VA_INT8: Final = "minimax_h3_fl2va_pruned_int8_convrot.safetensors"
FL2VA_W4A8: Final = "minimax_h3_fl2va_pruned_w4a8_mixed.safetensors"
FASTH3_V2: Final = "fastvideo_fasth3_8step_v2_pruned_int8_convrot.safetensors"
PINKCHERRY_FL2VA_INT8_V03: Final = "PinkCherry_h3_fl2va_int8_convrot_v0.3-alpha.safetensors"
EROSMAX_BETA4: Final = "h3ErosMax_beta4.safetensors"
EROSMAX_BETA5: Final = "h3ErosMax_beta5.safetensors"
REF2VA_INT8: Final = "minimax_h3_ref2va_pruned_int8_convrot.safetensors"
REF2VA_GGUF_Q3KM: Final = "MiniMax-H3-Ref2VA-Q3_K_M.gguf"

CLIP_NAME: Final = "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
HERETIC_CLIP_NAME: Final = "qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors"
CLIP_TYPE: Final = "minimax"
VIDEO_VAE: Final = "minimax_h3_video_vae_fp16.safetensors"
W4A8_VIDEO_VAE: Final = "minimax_h3_video_vae_int8_convrot.safetensors"
AUDIO_VAE: Final = "minimax_h3_audio_vae_fp32.safetensors"
LIGHTX2V_4STEP_LORA: Final = "minimax_h3_fl2v_lightx2v_turbo_4step_v0.1_comfy.safetensors"
LIGHTX2V_4STEP_STRENGTH: Final = 0.75
FAST_FINAL_4STEP_LORA: Final = "minimax_h3_fl2v_turbo_4step_v1.1_768p_comfyui_bf16.safetensors"
FAST_FINAL_4STEP_STRENGTH: Final = 1.0
REF2VA_TURBO_4STEP_LORA: Final = "minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors"
REF2VA_VSA_GATE: Final = "fasth3_vsa_gate.safetensors"
REF2VA_VSA_SPARSITY: Final = 0.75
TAOMATE_3STEP_LORA: Final = "TaoMate-H3-3step-ComfyUI.safetensors"
TRT_VAE_DECODER: Final = "minimax_h3_vae_decoder.engine"
TRT_VAE_ENCODER: Final = "minimax_h3_vae_encoder.engine"
H3_LATENT_UPSCALER_3D: Final = "minimax_h3_latent_upscaler_3d_bf16.safetensors"
PREMIUM_REFINE_SIGMAS: Final = "0.9035, 0.6316, 0.3158, 0.0000"

# --- Node class names -----------------------------------------------------
NODE_UNET_LOADER: Final = "UNETLoader"
NODE_UNET_LOADER_GGUF: Final = "UnetLoaderGGUF"
NODE_CLIP_LOADER: Final = "CLIPLoader"
NODE_LORA_LOADER_MODEL_ONLY: Final = "LoraLoaderModelOnly"
NODE_VAE_LOADER: Final = "VAELoader"
NODE_TRT_VAE_LOADER: Final = "MiniMaxH3TRTVAELoader"
NODE_IMAGE_TO_VIDEO: Final = "MiniMaxH3ImageToVideo"
NODE_REFERENCE_TO_VIDEO: Final = "MiniMaxH3ReferenceToVideo"
NODE_LOAD_IMAGE: Final = "LoadImage"
NODE_LOAD_VIDEO: Final = "LoadVideo"
NODE_LOAD_AUDIO: Final = "LoadAudio"
NODE_GET_VIDEO_COMPONENTS: Final = "GetVideoComponents"
NODE_EASYCACHE: Final = "EasyCache"
NODE_SAGE_PATCH: Final = "MiniMaxH3MemoryEfficientSageAttentionPatch"
NODE_SOL_PATCH: Final = "SolAttnPatch"
NODE_REF2VA_VSA_PATCH: Final = "Ref2VAVSAGatePatch"
NODE_H3_SIGMA_SHIFT: Final = "MiniMaxH3SigmaShift"
NODE_MODEL_ATTENTION_BACKEND: Final = "ModelAttentionBackend"
NODE_BLOCK_SPARSE_ATTENTION: Final = "BlockSparseAttention"
NODE_BASIC_GUIDER: Final = "BasicGuider"
NODE_RANDOM_NOISE: Final = "RandomNoise"
NODE_KSAMPLER_SELECT: Final = "KSamplerSelect"
NODE_BASIC_SCHEDULER: Final = "BasicScheduler"
NODE_SAMPLER_CUSTOM_ADVANCED: Final = "SamplerCustomAdvanced"
NODE_VAE_DECODE: Final = "VAEDecode"
NODE_VAE_DECODE_AUDIO: Final = "VAEDecodeAudio"
NODE_CREATE_VIDEO: Final = "CreateVideo"
NODE_SAVE_VIDEO: Final = "SaveVideo"
NODE_H3_MULTISHOT_MEMORY: Final = "H3MultishotMemorySampler"
NODE_IMAGE_RANGE: Final = "GetImageRangeFromBatch"
NODE_TRIM_AUDIO_DURATION: Final = "TrimAudioDuration"
NODE_BATCH_IMAGES: Final = "BatchImagesNode"
NODE_SEPARATE_AV_LATENT: Final = "LTXVSeparateAVLatent"
NODE_H3_LATENT_UPSCALER_3D: Final = "MinimaxH3LatentUpscaler3D"
NODE_CONCAT_AV_LATENT: Final = "LTXVConcatAVLatent"
NODE_MANUAL_SIGMAS: Final = "ManualSigmas"

#: Nodes that must exist on the Comfy instance for the Studio to work at all.
REQUIRED_NODES: Final = (
    NODE_UNET_LOADER,
    NODE_CLIP_LOADER,
    NODE_VAE_LOADER,
    NODE_BASIC_GUIDER,
    NODE_RANDOM_NOISE,
    NODE_KSAMPLER_SELECT,
    NODE_BASIC_SCHEDULER,
    NODE_SAMPLER_CUSTOM_ADVANCED,
    NODE_VAE_DECODE,
    NODE_VAE_DECODE_AUDIO,
    NODE_CREATE_VIDEO,
    NODE_SAVE_VIDEO,
)

# --- Model invariants -----------------------------------------------------
FPS: Final = 24.0
FRAME_STEP: Final = 17
FRAME_BASE: Final = 5
FRAME_MIN: Final = FRAME_BASE
FRAME_MAX: Final = 3600
#: Native trained window, ~5.17s - 15.08s at 24fps.
TRAINED_FRAME_MIN: Final = 124
TRAINED_FRAME_MAX: Final = 362
#: Lengths we surface as first-class choices in the UI.
PREFERRED_LENGTHS: Final = (124, 175, 192, 243, 362)

DIMENSION_STEP: Final = 32
DIMENSION_MIN: Final = 32
#: The node contract allows 16384; the Studio caps at a value a 4090 can
#: actually finish, and says so honestly in the UI.
DIMENSION_MAX: Final = 1536

MAX_REF_IMAGES: Final = 9
MAX_REF_VIDEOS: Final = 3
MAX_REF_AUDIOS: Final = 3
MAX_REF_TOTAL: Final = 12
MAX_REF_VIDEO_SECONDS: Final = 15.0
MIN_REF_VIDEO_SECONDS: Final = 2.0
MAX_REF_AUDIO_SECONDS: Final = 15.0
MAX_LORAS: Final = 8

# Known H3 LoRA metadata. Unknown files discovered live remain selectable with
# checkpoint="any"; this entry carries the author's explicit FL2VA guidance.
KNOWN_LORAS: Final = {
    "minimax_h3_character_swap_v1.1_ref2va_fro.safetensors": {
        "label": "Character Swap v1.1 (experimental)",
        "recommended_strength": 1.0,
        "checkpoint": "ref2va",
        "note": "Experimental Ref2VA character adapter. Prompt prefix: body_swap:; character image: <Picture 1>. Author docs/workflow still describe v1.0 at strength 1.0 and require aligned guide-latent video via MiniMaxH3AddGuide (frame_idx=0). Studio native video references are not equivalent to guide latents; this selector alone does not reproduce that workflow. v1.1 has not been render-tested here. BFS license: internal media creation allowed; no hosted model service.",
    },
    "camera_motion_h3_lora_v1_1000_pruned.safetensors": {
        "label": "Camera Motion v1 · 1000 steps",
        "recommended_strength": 0.8,
        "checkpoint": "any",
        "note": "Camera-control LoRA. Start the prompt with: camera motion. Recommended strength 0.8-1.0.",
    },
    "camera_motion_h3_lora_v1_3000_pruned.safetensors": {
        "label": "Camera Motion v1 · 3000 steps",
        "recommended_strength": 0.8,
        "checkpoint": "any",
        "note": "Later camera-control checkpoint. Start the prompt with: camera motion. Recommended strength 0.8-1.0.",
    },
    "minimax_h3_fl2v_turbo_4step_v1.1_768p_comfyui_bf16.safetensors": {
        "label": "LightX2V Turbo 4-step v1.1 (768p)",
        "recommended_strength": 1.0,
        "checkpoint": "fl2va",
        "note": "Official FL2VA four-step acceleration LoRA. Select Quality, set 4 steps and use the simple scheduler.",
    },
    "minimax-h3_fl2v_8Step_motion_enhancer.safetensors": {
        "label": "Motion Enhancer · FL2VA 8-step",
        "recommended_strength": 1.0,
        "checkpoint": "fl2va",
        "note": "FL2VA motion/anatomy enhancer derived from LightX2V8. Use alone at strength 1.0 with 8 steps, er_sde and beta; do not combine with another LightX2V/Turbo LoRA.",
    },
    "PinkFluffyBunny-alpha-lora.safetensors": {
        "label": "Pink Fluffy Bunny (alpha)",
        "recommended_strength": 0.5,
        "checkpoint": "fl2va",
        "note": "Alpha style/pose LoRA; author recommends 0.5 on the pruned FL2VA INT8 checkpoint.",
    },
    "h3-realism-people-t2v-i2v-r2v.safetensors": {
        "label": "Realism People",
        "recommended_strength": 1.0,
        "checkpoint": "any",
        "note": "fal MiniMax H3 people realism LoRA. Start prompts with trigger r34l1sm; use 0.6-0.8 for a lighter touch.",
    },
    "MysticXXX_MMH3-V3.safetensors": {
        "label": "MysticXXX MMH3 V3",
        "recommended_strength": 0.7,
        "checkpoint": "any",
        "note": "User-provided MiniMax H3 LoRA. Start around 0.6-0.8; embedded metadata is non-authoritative.",
    },
}

SAMPLERS: Final = (
    "res_multistep",
    "er_sde",
    "euler",
    "dpmpp_2m",
    "uni_pc",
    "ddim",
)
SCHEDULERS: Final = ("beta", "simple", "sgm_uniform", "normal", "linear_quadratic", "kl_optimal")

DEFAULT_SAMPLER: Final = "res_multistep"
DEFAULT_SCHEDULER: Final = "beta"
DEFAULT_STEPS: Final = 20

# --- Method profiles ------------------------------------------------------
# Measured on reference RTX 4090 workstation, 5.17s / 608x352 / 16 steps. These are honest reference
# points from one measured configuration, never a universal guarantee.
BENCHMARK_BASIS: Final = {
    "seconds": 5.17,
    "width": 608,
    "height": 352,
    "steps": 16,
}

METHOD_PROFILES: Final = {
    "fast_h3_v2_8step": {
        "id": "fast_h3_v2_8step",
        "label": "FastH3 V2 8-Step (Experimental)",
        "blurb": "Official FastVideo DMD2 eight-step T2VA recipe on the isolated ComfyUI 0.36 runtime.",
        "experimental": True,
        "backend": "experimental",
        "measured_seconds": None,
        "measured_ssim": None,
        "basis_steps": 8,
        "caveat": "Installed but not validated on this RTX 4090. Text-to-video only; H3VAE-PyOpt is omitted and the native ComfyUI 0.36 VAE path is used. the operator will run the first GPU test.",
        "requires_nodes": (NODE_MODEL_ATTENTION_BACKEND, NODE_BLOCK_SPARSE_ATTENTION, NODE_H3_SIGMA_SHIFT),
        "requires_unets": (FASTH3_V2,),
        "requires_samplers": ("res_multistep",),
        "requires_schedulers": ("simple",),
    },
    "taomate_3step": {
        "id": "taomate_3step",
        "label": "TaoMate H3 3-Step (Draft/Experimental)",
        "blurb": "Official three-step TaoMate LoRA recipe on the isolated ComfyUI 0.36 runtime.",
        "experimental": True,
        "backend": "experimental",
        "measured_seconds": None,
        "measured_ssim": None,
        "basis_steps": 3,
        "caveat": "Installed but not validated on this RTX 4090. H3VAE-PyOpt is omitted and the native ComfyUI 0.36 VAE path is used. Draft/experimental until the operator completes visual and audio QA.",
        "requires_nodes": (NODE_LORA_LOADER_MODEL_ONLY,),
        "requires_unets": (FL2VA_INT8,),
        "requires_loras": (TAOMATE_3STEP_LORA,),
        "requires_samplers": ("euler",),
        "requires_schedulers": ("simple",),
    },
    "baseline": {
        "id": "baseline",
        "label": "Quality",
        "blurb": "No attention or cache tricks. The reference render.",
        "experimental": False,
        "measured_seconds": 79.98,
        "measured_ssim": None,
        "caveat": "Slowest, and the render every other profile is compared against.",
        "requires_nodes": (),
    },
    "easycache": {
        "id": "easycache",
        "label": "Fast Preview",
        "blurb": "Reuses stable sampling steps. Recommended default for short takes.",
        "experimental": False,
        "measured_seconds": 57.53,
        "measured_ssim": 0.914,
        "caveat": "~28% faster on the measured 5.17s clip, SSIM 0.914 vs Quality. Fine detail can soften.",
        "requires_nodes": (NODE_EASYCACHE,),
    },
    "w4a8_lightx2v": {
        "id": "w4a8_lightx2v",
        "label": "W4A8 + LightX2V4",
        "blurb": "Four-step FL2VA recipe using the W4A8 checkpoint and full LightX2V LoRA.",
        "experimental": False,
        "measured_seconds": 94.44,
        "measured_ssim": None,
        "basis_steps": 4,
        "caveat": "Frame-driven modes only. Measured at 608x352, 124 frames: 94.44s, 22,389 MiB peak VRAM.",
        "requires_nodes": (NODE_LORA_LOADER_MODEL_ONLY,),
        "requires_unets": (FL2VA_W4A8,),
        "requires_loras": (LIGHTX2V_4STEP_LORA,),
        "requires_samplers": ("er_sde",),
        "requires_schedulers": ("simple",),
    },
    "w4a8_lightx2v_trt": {
        "id": "w4a8_lightx2v_trt",
        "label": "Fast Final TRT 5s",
        "blurb": "Validated four-step W4A8 final with TensorRT video decode.",
        "experimental": False,
        "measured_seconds": 63.445,
        "measured_ssim": None,
        "basis_steps": 4,
        "caveat": "FL2VA only. Measured at 608x352, 124 frames: 63.445s, 22,944 MiB peak VRAM. TRT is decode-only; conditioning stays on the standard INT8 ConvRot VAE.",
        "requires_nodes": (NODE_LORA_LOADER_MODEL_ONLY, NODE_TRT_VAE_LOADER),
        "requires_unets": (FL2VA_W4A8,),
        "requires_loras": (FAST_FINAL_4STEP_LORA,),
        "requires_samplers": ("res_multistep",),
        "requires_schedulers": ("simple",),
        "requires_vae_engines": (TRT_VAE_DECODER, TRT_VAE_ENCODER),
    },
    "w4a8_latent2x_refine3": {
        "id": "w4a8_latent2x_refine3",
        "label": "Premium 2× Refine3",
        "blurb": "The verified bear/robots recipe: four-step W4A8, 3D latent upscale 2×, then three-step HD refinement.",
        "experimental": False,
        "measured_seconds": 171.17,
        "measured_ssim": None,
        "basis_steps": 4,
        "basis_width": 640,
        "basis_height": 1152,
        "basis_frames": 124,
        "caveat": "Verified at 124 frames: 169.45s at 640x1152 and 172.89s at 768x1024; ~23.9 GiB peak VRAM.",
        "requires_nodes": (
            NODE_LORA_LOADER_MODEL_ONLY,
            NODE_SEPARATE_AV_LATENT,
            NODE_H3_LATENT_UPSCALER_3D,
            NODE_CONCAT_AV_LATENT,
            NODE_MANUAL_SIGMAS,
        ),
        "requires_unets": (FL2VA_W4A8,),
        "requires_loras": (LIGHTX2V_4STEP_LORA,),
        "requires_latent_upscalers": (H3_LATENT_UPSCALER_3D,),
        "requires_samplers": ("er_sde", "euler"),
        "requires_schedulers": ("simple",),
    },
    "ref2va_vsa": {
        "id": "ref2va_vsa",
        "label": "Ref2VA VSA",
        "blurb": "Four-step Ref2VA Turbo recipe with gated sparse video attention and creator-selectable conditioning.",
        "experimental": True,
        "measured_seconds": 94.299,
        "measured_ssim": None,
        "basis_steps": 4,
        "basis_width": 1344,
        "basis_height": 768,
        "basis_frames": 124,
        "caveat": "Validated on reference RTX 4090 workstation at 1344x768, 124 frames: 94.299s warm, 23,279 MiB peak; cold start 355.448s. References mode only.",
        "requires_nodes": (NODE_LORA_LOADER_MODEL_ONLY, NODE_REF2VA_VSA_PATCH, NODE_H3_SIGMA_SHIFT),
        "requires_unets": (REF2VA_INT8,),
        "requires_loras": (REF2VA_TURBO_4STEP_LORA, REF2VA_VSA_GATE),
        "requires_samplers": ("euler",),
        "requires_schedulers": ("simple",),
    },
    "sage": {
        "id": "sage",
        "label": "Sage",
        "blurb": "Memory-efficient Sage attention patch. Lowers peak VRAM.",
        "experimental": True,
        "measured_seconds": 76.06,
        "measured_ssim": 0.861,
        "caveat": "Experimental. Barely faster than Quality and SSIM 0.861 - use it for VRAM headroom, not speed.",
        "requires_nodes": (NODE_SAGE_PATCH,),
    },
    "sol": {
        "id": "sol",
        "label": "SolAttn",
        "blurb": "Sparse Sol-Attn research patch.",
        "experimental": True,
        "measured_seconds": 82.99,
        "measured_ssim": 0.778,
        "caveat": "Experimental, never a default. Measured slower than Quality (82.0-84.0s) at SSIM 0.778.",
        "requires_nodes": (NODE_SOL_PATCH,),
    },
}

#: Fast Preview EasyCache recipe fixed by CLAUDE.md.
EASYCACHE_DEFAULTS: Final = {
    "reuse_threshold": 0.3,
    "start_percent": 0.2,
    "end_percent": 0.9,
}

#: SolAttn defaults straight from the node contract.
SOL_DEFAULTS: Final = {
    "tau": 1.3,
    "start_percent": 0.2,
    "end_percent": 0.9,
    "min_tokens": 4096,
    "int8_qk": True,
    "sink_conditioning": "exact_kv_and_rows",
    "morton": False,
    "morton_curve": "2d_frame",
    "verbose": False,
    "use_tma": False,
}

SOL_SINK_OPTIONS: Final = ("exact_kv", "exact_kv_and_rows", "off")
SOL_MORTON_CURVES: Final = ("3d", "2d_frame")

OUTPUT_PREFIX_ROOT: Final = "video/H3Studio"
