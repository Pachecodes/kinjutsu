# Studio validation

Executed against the sanitized copy, not the original application.

- Backend: **353 passed, 20 skipped**, one dependency deprecation warning; 199.27 seconds on the final run.
- Backend skips: six unsupported W4A8/mode combinations, four non-References VSA combinations, ten isolated-runtime profile combinations covered by dedicated tests. Generated-media aligned-guide tests ran (not skipped).
- Warning: the existing Python environment's Starlette TestClient warns that its HTTPX integration is deprecated. No application test failure.
- Frontend: **13 test files / 61 tests passed**.
- `npm run typecheck`: passed.
- `npm run build`: passed (Vite 8.2.0, 1,963 modules transformed).
- Sanitized build: `frontend/dist/index.html`, `assets/index-qA17U0E9.css`, `assets/index-CujNweJt.js`; HTML title confirmed as `Pachecodes : Kinjutsu`.

TDD red/green checks were executed for portable default configuration, Studio-root-relative paths, neutral Prompt Chat guidance and frontend branding. Aligned-guide tests cover API upload/validation/build, correct guide-conditioning edges, schema capability checks, alignment mismatches and split-guide rejection. Their old personal-media dependencies were replaced by generated solid-color 124-frame 576x1024/24fps video and a synthetic PNG.

Backend validation reused the pre-existing source environment's Python interpreter/dependencies read-only. Tests imported this copy's application. Frontend dependencies were installed locally with `npm ci`; source dependencies were not modified. Generated dependencies/caches/test media were removed after validation. The sanitized frontend build was retained as a local verification artifact; the installer should rebuild it.

Sanitization scan covered 134 source/config/test/fixture/build files before this report: no private-person/workstation/character names, no personal absolute paths, no internal IPv4 addresses, no private overlay DNS hosts, and no obvious private-key/API-token prefixes. Only `.env.example` exists; no `.env` was copied. URL hosts were loopback plus public package-registry, dependency-documentation/funding and SVG-standard hosts. Generic malicious Windows-path strings remain intentionally in security tests.

Copied fixture prompts and media filenames were replaced with synthetic examples. Captured unrelated adapter inventory entries were removed from the offline node contract. Model/node identifiers needed for supported and experimental workflows remain intentionally unchanged. Optional historical timing/profile metadata is not proof of availability or local testing; live discovery remains authoritative.

No GPU inference or image/video quality evaluation was performed. No service was started/restarted for validation. No model weights, production database/history, uploads or output media were copied. No protected agent-instruction files were created or copied. Public redistribution remains subject to source/model/node licensing review (see README).
