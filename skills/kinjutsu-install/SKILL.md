---
name: kinjutsu-install
description: Use when installing the Kinjutsu Windows RTX4090 stack.
---
# Install reproducibly
Read START_HERE_AGENT.md and docs/INSTALLATION-TECHNICAL.md. Inspect live OS/GPU/driver/RAM/disk/ports. Use a dedicated install directory and Python environment; no global GPU-package upgrades. Follow dependency pins and the model manifest, not latest. Keep bundled LoRA separate from base downloads. Verify each SHA256 before use; resumable .part downloads prevent corrupt complete filenames.

Install the pinned Comfy core plus AddGuide's node-and-core compatibility layer. Node registration alone does not establish temporal guide packing. Keep optional TRT/experimental attention paths absent. Install the sanitized Studio and build frontend. Start only loopback listeners, no scheduled task/autostart. Verify owning PIDs, API capability/catalogs, frontend and tests. Stop only the processes this install owns, after idle checks.

Never put credentials into commands, chat, tracked files or test reports. Resolve authentication interactively or via the user's approved secure mechanism. Do not bypass UAC. Preserve working installations and report blockers honestly. Offline/dry-run verification is not a full clean-machine install or GPU smoke.
