# Fixed-method transfer to 35 additional Old Holland ternaries

Declared 2026-10-01 before any new fit or assessment. This executes the user's
approved [cohort protocol](../oil_ternary_sources/NEXT-STUDY.md), committed in
`5f86146`. The cohort JSON SHA-256 is
`4e041683aef3205c8f0219d479c5889993486cfa4bb9e6e26450162db3b70247`.
It contains 35 no-white ternaries across 25 paint triples, selected by recipe
coverage rather than model error. The earlier three Old Holland targets
(172,174,176) are excluded from this study's scoring and are not refitted here.

## Data, calibration and unchanged methods

Use the unchanged Asadi archive, SHA-256
`cda35e5ab968bb18a05127c1b9fb0b2bd3c4a4bb88d4bf4ae1e4b2bb5de07538`.
Normalize recorded tube-paint masses. Retain native 31-band reflectance at
400-700 nm: no interpolation, extrapolation, smoothing or relabeling. For each
triple use those three paints in ascending original column order and Mixed White
fourth. The methods treat the first three as generic paint coordinates; they are
not always yellow/red/blue. The white scattering gauge remains attached to the
same physical Mixed White paint.

For each palette, fit exactly the pure/binary rows in `next-cohort.json` (25-39
rows), never a ternary or higher-order sample. Fit fresh coefficients separately
for each palette using the unchanged `oil_parallel/interaction/run.py` procedure:
three-start, 93-parameter K-M fit followed by its bounded empirical pair controls.
Keep the original objective, priors, bounds, starts and optimizer stopping rules.
Do not transfer coefficients from another palette or retune failed examples.

Evaluate three fixed predictions from each palette's fit:

1. Its own fitted opaque K-M base.
2. Its original empirical pair correction.
3. The previously tested smooth attenuation decoder, with lambda fixed at 1:
   chromatic pair shift multiplied by `1 - 27*c1*c2*c3`; white-pair shift unchanged.
   Import the exact archived decoder after fitting is complete. No new strength
   is learned from these assessment spectra and no alternative gate is tried.

The attenuation is a prespecified secondary comparator. This study's primary
question is transfer of the original empirical correction relative to K-M across
more three-paint identities and ratios. Improvement from attenuation relative to
the original correction and improvement relative to K-M are separate findings.

## Freeze, failure handling and reporting

Prepare input/implementation hashes and exact row partitions, fit all 25 palettes,
freeze all results, verify, then score. Preserve every fit's optimizer metadata.
A failed individual K-M start is reported; the unchanged fitter may select a
converged start as before. If an entire palette fit fails, record the failure and
continue attempting the remaining palettes without changing settings. Do not
drop that palette silently or claim a complete 35-row primary result; any score
on a successful subset must be explicitly incomplete.

Primary endpoint: sample-weighted mean spectral RMSE over all 35 assessment rows.
Companion: mean of the 25 within-palette mean RMSE values, with equal palette
weights. Report per-row and per-palette differences, improved/worsened counts,
p95/max errors and secondary D65/2-degree DE00 using the established 400-700 nm
window and its matching white. Do not pool numeric scores with Grillini's different
materials/window. Do not impose the old product quality thresholds on this new
coverage study or treat relative improvement as release readiness.

Report calibration coverage alongside errors, without excluding palettes based
on that coverage after assessment. Any error-versus-gate or paint-family pattern
observed afterwards is descriptive, not a new selection criterion. No confidence
interval or significance claim based on treating overlapping palettes as
independent replicates. The same swatches supply calibration for multiple fits.

## Verification and limits

Check complete unique assessment coverage, exact cohort compatibility, four pure
endpoints, all six binary-pair supports, pure/binary-only calibration and disjoint
fit/assessment row sets. Refit each successful palette after changing excluded
targets and require identical coefficients. This audit must pass before scoring.
Check independent scalar prediction parity for K-M, original correction and fixed
attenuation, finite bounded outputs, pure endpoints, attenuation lambda-zero
parity and bit-identical preservation on binary/white faces. Verify all source,
cohort, method and frozen bundle hashes through each phase.

This is a broader same-source assessment outside the earlier four-paint selection.
The source and method family already influenced research; it is not a wholly
independent external validation. Concentrations are tube-paint masses, not pigment
volume or chemically pure pigment fractions. Keep all raw spectra and fitted
coefficients under ignored target/. Version the experiment and derived evidence.
No runtime, renderer, paper implementation, measured preset or default changes.
