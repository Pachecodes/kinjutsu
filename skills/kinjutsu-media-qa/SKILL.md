---
name: kinjutsu-media-qa
description: Use when reviewing and delivering generated swap video.
---
# Review the real media
Require completed owned job and real nonempty output. Inspect stored workflow to confirm exact checkpoint, ordered LoRA strengths, AddGuide and steps. ffprobe confirms delivery dimensions/FPS/frames/duration; ffmpeg full decode confirms media integrity. A passing decode does not establish visual quality.

Make about6FPS contact sheets across the whole output. Review early and late frames, stable identity, hair, neck, both forearms/hands/fingers, phone/props, clothing ownership and background geometry. Enlarge matched-time crops when skin tone differs; tiny sheets can hide retained guide hands. Compare guide, portrait and output under plausible local light. Do not claim all differences are lighting or all defects are prompt-fixable. Record user corrections in the QA report instead of defending an earlier missed defect.

Listen before asserting speech, original audio, language, lyrics or synchronization. The default guide is audio-free and H3 output audio is generated. Delivery can contain codec/AAC padding: separate frame duration from container duration and do not claim exact subframe timing.

Deliver actual MP4 with a short caption. Record timing as cold/warm end-to-end, not just sampling. Do not infer linear scaling, generic2x speedups or identity perfection from one successful take.
