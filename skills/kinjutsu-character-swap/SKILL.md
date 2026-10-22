---
name: kinjutsu-character-swap
description: Use when rendering reference identity over a video guide.
---
# Approved Character Swap HD Turbo8
Use workflows/approved-api.json for Studio and character-swap-turbo8-api.json for the exact Comfy graph. Identity is Picture1; an aligned guide owns motion/clothes/props/environment. Prefix body_swap:. Ref2VA pruned INT8ConvRot, standard32B encoder, videoVAEfp16/audioVAEfp32. Chain Ref2VA Turbo8v1.0 at1.0 THEN Character Swapv1.1 at1.0. Euler/simple8, BasicGuider, match image sizing, continuity off. Do not confuse FL2VA adapters with Ref2VA. Do not replace AddGuide with a normal Video token.

Probe original, retain it unchanged and review source contact sheets. Prepare124frames24FPS at736x1280. Scale aspect-fit into720x1280, then center-pad to736x1280, preserving motion speed. Map video only (-map0:v:0 -an -dn). Review framing. Upload assets through Studio; download exact assets and hash-check. IDs are DB-specific. Validate before one submission, persist receipt, read back exact job and avoid duplicates.

For full duration: ceil source frame coverage at24FPS, round UP to17k+5, clone last frame only to fill the grid, validate guide/output exact dimensions/FPS/framecount, then trim padding at delivery. Approx10s is tested;15–30s need feasibility/VRAM checks. Do not silently shorten or split a requested continuous take.

Do not call /free before a normal warm render unless intentionally testing cold state. Never stop unrelated GPU services. Preserve request, workflow, model hashes, seed, native output and timings per job. Final crop8px/side to720x1280, no upscale. Whole-body complexion ownership in prompt is only a candidate: guide hands may remain. Stronger Swap can change wardrobe. Treat new versions such as1.5 as separate A/B experiments.
