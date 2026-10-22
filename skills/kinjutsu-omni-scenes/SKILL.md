---
name: kinjutsu-omni-scenes
description: Use when creating new reference-driven scenes with FastH3 Omni in Kinjutsu, separate from Character Swap.
---

# FastH3 Omni · Escenas

Use only on a generation/installation request. Reading this skill does not authorize a GPU render or model download. For replacement on an existing acting video use `kinjutsu-character-swap` instead; do not combine that LoRA chain with Omni.

Read `docs/FASTH3-OMNI.md` for full recipe, evidence and limits. The model is optional in `models/manifest.json`, not bundled in Git. Reuse hash-verified encoder/videoVAE/audioVAE from authorized roots; download only missing artifacts through the license-confirmed size+SHA-verified manager. Never guess a missing weight is safe from its filename or size alone.

Omni uses its own pinned native Comfy core/environment on loopback8237 (`H3_OMNI_COMFY_URL`), not the historical Character Swap core. Do not upgrade or patch the latter to make Omni load. Check all GPU owners and queues before inference; no stopping other work, global Python kills or unconditional `/free` of a warm engine.

Recipe: method `fast_h3_omni_8step`, preset `fasth3-omni-scenes`, native references/ref2va, standard encoder and INT8 Omni; Euler/simple8, BasicGuider guidance1, denoise1, MiniMaxH3SigmaShift12/3 before guider AND scheduler. No extra LoRAs, aligned guide, performance mode or automatic continuity split. Preset image detail `max`,124frames/24FPS, aspect-appropriate multiples32. A photo is generative identity conditioning, not exact first-frame locking.

Write six H3 prompt sections (`subject_definitions`, `summary`, `retention_analysis`, `detailed_description`, `overall_soundscape`, `non_diegetic_music`). Map only attached Picture/Video/Audio ordinals. Ask for one attainable action and brief dialogue if desired; generated speech is not a cloned identity voice.

Upload through Studio `/api/assets`, verify source-byte readback, validate via `/api/validate`, then submit once `/api/jobs` and retain nested job.id. Require capability/model/native-core support before claiming available. Poll only own job, inspect `/api/jobs/{id}/workflow` for actual Omni checkpoint, shifts, eight steps and correct independent backend. Save exact prompt/seed/versions/stage/wall/VRAM evidence; no duplicate submission after an ambiguous timeout.

Require ffprobe, full AV decode, dense opening/full contact review and native face/hand/prop inspection. ASR supports exact speech text checks but is not listening or lip-sync proof. Measured warm5.17s single-image cases took86–123s; this is not an SLA, HD/long-context proof or comparison against Character Swap. Stop only an owned Omni engine at the requested batch boundary and verify other services remain healthy, unless user explicitly requested keeping it warm.
