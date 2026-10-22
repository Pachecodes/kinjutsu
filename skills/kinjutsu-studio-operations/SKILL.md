---
name: kinjutsu-studio-operations
description: Use when operating the local Kinjutsu Studio and Comfy.
---
# Studio ownership boundary
Discover configured base URLs and verify health. Defaults: Studio127.0.0.1:8220, Comfy127.0.0.1:8218. GET/api/config,/api/health,/api/capabilities?refresh=true and live/object_info are the source of truth. Require aligned_guides=true and exact model catalogs. A frontend build does not restart a Python backend.

Upload multipart file to POST/api/assets; verify asset byte readback. POST/api/validate requires ok=true. POST/api/jobs returns job.id nested under job. Poll only the owned job, then save /api/jobs/{id}/workflow and download the reported output URL. Never invent asset IDs or send filesystem paths where opaque IDs are required.

Use the package's start/stop scripts and UTF8 logs. Do not use broad Python kills, disable unrelated tasks or expose0.0.0.0. Check all owning queues and exact PID/commandline before lifecycle changes. HTTP200 from /free does not demonstrate VRAM released; measure if release was requested. Do not enable public inference service because the bundled Swap license restricts hosted API/SaaS functionality.
