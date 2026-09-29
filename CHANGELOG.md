# Changelog

## Unreleased - optimization round 2

- Add opt-in `compact::CompactLatent`: 24 nonuniform f32 K/S samples plus
  residual, 204 bytes, persistent interpolation/weighted mixing, checked
  import, full-state expansion and explicit little-endian serialization.
- Retain 26 screened representations, failed positivity/error gates, frozen
  selection and independent Rust holdout. Maximum compact/full difference on
  that holdout is 0.029 delta E OKLab * 100; this is model agreement, not paint
  calibration. See docs/optimization-round2.md.
- Record the cost as well as the saving: state memory falls 40%, while compact
  mixing/decoding is slower. Default 340-byte latents, coefficients, reference,
  renderer integration and existing wire formats remain unchanged.

## Unreleased - optimization round 1

- Separate independent per-wavelength optics from ordered RGB integration in
  the fast and reference kernels. No equation, coefficient, state format or API
  changes. The fast path is bit-identical on the retained screening and holdout.
- Record eight candidates, an alternating baseline/candidate confirmation,
  rejected algebraic decoder and all raw evidence. See docs/optimization-round1.md.
- Add an extreme-scale component-import regression test. State size remains
  340 bytes; this round addresses CPU cost, not memory compression or transport.

## Unreleased - oil-paint integration

- Add checked `Latent::try_from_parts` and `ReferenceLatent::try_from_parts`
  for exact component storage and language bridges. Optical equations and
  coefficients are unchanged; the core remains dependency-free and unsafe-free.
- Add a separated brush-workload benchmark, storage tests and integration
  documentation for the sibling Python/Rust renderer.
- Retain matched brush images, raw performance/quality data, reference checks,
  float16 candidate evaluation and RGB-roundtrip losses under results/integration.
- Keep full f32 states in the initial integration; compressed storage is not
  silently enabled. No new real-paint calibration or thickness claim is made.

## Project rename - 2026-09-30

- Rename the project and Rust crate from `pigment-mix` / `pigment_mix` to `ochrell` (display name **Ochrell**).
- Update imports, usage examples, paper title and author metadata, and release packaging. The release remains version 0.2.0; no mathematical model, fitted coefficient, or recorded measurement changed.
- Preserve historical papers, external comparison captures, and raw experiment records with their original names.


## 0.2.0

- Replace the default finite-palette inverse/LUT with continuous independently fitted spectral reconstruction and a declared K/S strength prior.
- Improve the documented dark blue/yellow, cyan/magenta and red/white cases; reduce uncorrected source error and input sensitivity on the recorded datasets.
- Use 41-band f32 optics and an 81-band f64 reference. Add `Latent::weighted`, absorption/scattering accessors and normalized weighted reference mixing.
- Breaking latent API: root `Latent` now stores wavelength-wise K/S and residual. Import `ochrell::legacy` for old concentrations, LUT APIs and behavior. Pair mixing usage is unchanged.
- Retain v0.1 implementation, paper, results and reproduction workflow. New experiment records are under `results/revision`.
- Add independent holdout diagnostics, tint analysis, spectral/strength ablations, full reproduction, a revised paper and observational Mixbox/Spectral.js comparisons.
- Tradeoffs: larger latent, slower full/cached mixing, some more-muted saturated mixtures, nonuniform trajectory-tail improvement, and no real-paint calibration.
