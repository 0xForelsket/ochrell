# Proposed fixed-method comparison on additional Old Holland ternaries

Prepared from recipe coverage on 2026-10-01. No models have been fitted or scored
for this proposed cohort. The exact selection is in `next-cohort.json`; its 35
assessment rows cover 25 triples of tube paints outside the earlier columns
1/3/5/8 palette. The old three no-white ternaries remain separate known controls.

The next question is whether the diagnosed binary-to-ternary correction failure
persists across other paint identities and ratios. Test the existing method before
inventing another residual correction.

1. For each listed triple, use those three paints plus Mixed White, with white in
   the fourth position. Use all supplied pure and binary rows inside that palette
   for calibration, and none of its ternary or higher-order rows. Every selected
   palette has all four pure endpoints and all six binary pairs represented.
   Counts vary from 25 to 39 calibration rows; some pairs have only one recipe.
2. Retain the unchanged 31-band K-M fitter and bounded empirical pair correction,
   including priors, bounds and starts. Fit coefficients separately for each
   palette. Use native 400-700 nm data: no interpolation, extrapolation or pooling
   with Grillini's different spectral window or dry-pigment mass basis.
3. Compare K-M with its own empirical correction on all 35 held-out no-white
   ternaries. Report sample-weighted mean spectral RMSE as primary, a macro mean
   across 25 paint triples as a coverage-sensitive companion, per-row changes,
   p95/max errors, and native-window DE00 as secondary. Preserve failed fits in
   the report rather than dropping difficult palettes after seeing results.
4. If included, the already-tested attenuation rule is a fixed secondary comparator
   at lambda=1, frozen from the previous study. Do not learn a new lambda from
   these targets or compare a sweep of new gates. This separates transfer of the
   old rule from another fit on assessment data.
5. Freeze all fitted models before assessment. Check fit/assessment disjointness,
   source hashes, complete target coverage, pure endpoints, independent scalar
   parity and excluded-target perturbation. Retain recipe-level and paint-family
   results; do not count reused calibration rows as independent replicates.

The existing three Old Holland no-white targets (172,174,176) can be replayed as
known controls but must not enter the 35-row primary score. They and the same
source dataset already informed model selection. The additional rows provide a
broader same-source challenge, not a wholly independent external dataset.

Most new paint triples have only one target; only three additional triples have
three targets each. Repeating the prior two-train/one-test scalar procedure per
palette would therefore discard most coverage. The proposed initial comparison
uses binary-only calibration and all eligible ternaries as assessments instead.

Grillini's other 57 no-white ternaries are a secondary future pigment-transfer
study. They all have the same 2:1:1 shape and h=0.84375, and other palettes require
their own projected mapping-ambiguity audit. The seven earlier Y/C/B/W variants
cannot be reused as exhaustive alternatives for different palettes.

Runtime, renderer, shipped palettes and the paper-faithful implementation remain
outside this research comparison. No further correction should be chosen from
this cohort and then described as independently validated on it.
