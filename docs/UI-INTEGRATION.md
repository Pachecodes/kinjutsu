# Friendly UI integration — Pachecodes : Kinjutsu

## Delivered

The packaged frontend now contains the completed Spanish creator UI: curated recipes,
reference tray and guide synchronization, deterministic prompt forms, actionable
validation, advanced controls with contextual help, reorderable LoRAs, an interactive
tour, staged job progress/cancellation, and the mobile Crear / Escenario / Refs /
Galería flow. This is a package update, **not activation of a live installation**.

Package-specific changes retained:

- Central `src/lib/brand.ts`: `Pachecodes : Kinjutsu`, with the reference RTX 4090
  workstation tagline and machine name. HTML uses Spanish and theme `#101112`.
- Available HD Turbo8 is selected once, through a `useRef`-guarded initialization,
  only when there is no existing prompt, title, reference or selected recipe.
  Configuration refetches and composer resets do not reapply it during that mount.
- The anonymized Character Swap playground/winner tests and `test/factories.ts`
  are preserved byte-for-byte from the previous package.
- Existing dependency manifests, lockfile and TypeScript configuration are preserved;
  no dependencies were added or installed. Existing dependencies were linked only
  for verification and the link was removed from the transferable package.
- Tailwind's CTA/radius additions and the optional `H3_STUDIO_API` development proxy
  were merged. Unimported obsolete ModeRail/PresetRail components were removed.
- `dist` was rebuilt from the merged, sanitized package source; it is not the
  source application's branded distributable.

## Verification

Executed from `studio/frontend` after the merge:

```sh
NODE_OPTIONS=--no-experimental-webstorage node node_modules/vitest/vitest.mjs run --pool=threads --maxWorkers=1 --no-file-parallelism --cache=false
node node_modules/typescript/bin/tsc --noEmit
node node_modules/eslint/bin/eslint.js .
node node_modules/vite/bin/vite.js build
```

- **27 test files, 145 tests passed.** This includes the imported UI tests, the
  updated central-brand assertion, and six HD initialization/draft-preservation tests.
- Typecheck, lint and production build each exited **0**.
- Node used for verification: **v26.7.0**. The `NODE_OPTIONS` flag is needed in
  worker threads on this installation: its experimental native Web Storage can
  mask jsdom's localStorage. Without the flag tests fail during setup, not UI logic.
- Build output: `index.html` **0.80 kB**, CSS **38.31 kB**, JS **620.86 kB**;
  gzip **0.45 / 7.91 / 194.52 kB** respectively (Vite-reported decimal units).
- Source and rebuilt distribution scanned case-insensitively for the private
  source character/machine names and private Windows host paths: **zero matches**.
- Full source snapshot, package backup (excluding node_modules), before/after
  inventories and command logs are retained in the merge's external scratch
  workspace, not shipped as private development documentation.

Tests cover recipe confirmation/no implicit rendering, experimental opt-in,
mobile navigation/history/reuse, tour keyboard handling, contextual validation,
aligned-guide timing, LoRA ordering, model license consent/cancellation, and prompt
preview/apply/staleness. These are component/state tests in jsdom, **not a visual
browser-layout certification**.

## Backend contract and limits

- Models and backend prompt forms are capability-gated using `/api/openapi.json`;
  absent routes keep those controls hidden or retain the local prompt template.
- Model catalog hashing remains explicitly requested, not automatic at page load.
  Install still posts only `{ "license_acknowledged": true }` after explicit consent.
- Prompt form tests use a snapshot of the real six-template packaged catalog at
  `src/test/fixtures/promptCatalog.json`, rather than a reduced invented catalog.
  Duration remains native milliseconds, e.g. 124 frames = 5.167 seconds and
  243 frames = 10.125 seconds. Preview does not submit a render.
- Additive model `free_bytes`, `partial_bytes`, `label`, `role`, `required_by` and
  license-text HTTP capability are not yet consumed by this UI. Existing target-based
  model labels and packaged license paths remain the compatible fallback; downloads
  still rely on the backend's disk-space validation and resume behavior.
- No backend code, model manifest, prompting assets, runtime data or live services
  were edited by this frontend integration. No GPU calls, renders, downloads, commits,
  publication or live deployment were performed.
- Final integration additionally exercised a real isolated CPU backend and the browser: OpenAPI capability detection, explicit model catalog SHA verification, actual T2VA prompt build/preview/apply, tour next/Escape and390px mobile layout without horizontal overflow. Comfy was deliberately offline; no jobs or downloads were submitted. The test listener was stopped and its port verified closed. Backend-wide395passed/20skipped and root35passed/1skipped.
- The frontend catalog fixture was synchronized to the backend's three-decimal duration metadata after this run and compared for exact JSON equality. No production UI behavior changed in that fixture-only correction.
- Online Comfy progress/cancellation, clean recipient GPU installation and live deployment remain unverified. The optional PromptChat dialog remains English.
