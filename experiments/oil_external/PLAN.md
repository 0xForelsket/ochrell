# First external measured-palette test

Declared 2026-09-30 after file/metadata validation and before any fitted-model
error is calculated for this dataset. Source: Grillini, Thomas and George,
Comparison of Imaging Models for Spectral Unmixing in Oil Painting (2021),
DOI 10.3390/s21072471. Retrieved public supplementary archive SHA-256:
6d8cec6fb4fff5d4c24d18d1783422da8ef955d3e7ba7263179a84ed6c9b683e.

The user selected existing public measurements. This is a transfer test of the
unchanged model family/optimizer on different materials, not validation of the
Old Holland coefficients. There will be one prespecified palette and no tuning,
candidate sweep, alternative red selection or second attempt based on results.

## Source and representation

- The archive supplies 175 matching sample labels, seven concentration rows and
  186 reflectance bands from 405.37 to 995.83 nm. The paper removes ten bands at
  both ends for noise. Follow that removal: retained support 437.29-963.91 nm.
- Select Y=Naples Yellow 43125, C=Carmine 23403, B=Ultramarine Blue 45030 and
  W=Kremer White 46360. Selection uses identities and coverage, not model scores.
  These are Kremer pigments combined with linseed oil. Published proportions
  describe pigment mass before binder addition, unlike tube-paint mass in the
  Old Holland study. Keep that domain difference explicit.
- Use stored spreadsheet fractions (including 0.33/0.67) for fitting. The source
  labels describe nominal 1:1 and 2:1 ratios. Group by those nominal recipes so
  rounding to two decimals cannot separate a parent from its white addition.
  Do not substitute exact nominal fractions into the fitter.
- Interpolate linearly within measured, edge-trimmed support onto 31 bands
  440,450,...,740 nm. This keeps the existing 31-band model and 300 nm span.
  No extrapolation, tail fabrication, negative/above-one clipping or smoothing.
- Spectral RMSE on that grid is the primary metric. Any D65/2-degree DE00 uses
  only 440-740 nm with its own truncated white and is a secondary diagnostic,
  not full-visible color accuracy or numerically comparable to Old Holland DE00.

## Fixed splits and fitting

The selected subset contains 34 samples: four pure, nine single-chromatic white
tints, nine chromatic pairs and twelve three-material mixtures. The 13 pure/tint
rows remain calibration anchors. The primary training pool has 22 rows (anchors
plus nine pairs); the twelve ternaries are never fitted.

Group all other 21 rows by nominal Y:C:B ratio after excluding W. There are
twelve groups: nine parent-plus-white-addition groups and three Y:C:B groups.
For every group, train on the 22-row pool minus the entire group. This yields
nine 21-row fits and a shared 22-row fit (ten unique fits), frozen before scoring.
The 13 anchors' generalization is not tested. Related physical batch identity is
unknown; grouping is by recipe only.

Reuse the exact `oil_parallel/interaction/run.py` implementation: 93 K-M
parameters and at most 24 bounded empirical controls, sequential fitting,
unchanged V1 spectral objective, priors, bounds, starts and stopping criteria.
Use the fold's own K-M base as the comparison. Keep pure endpoints fixed. No
existing Old Holland coefficients are transferred. Any failed fit stops scoring.

Primary comparison: grouped twelve-ternary mean spectral RMSE, empirical versus
fold-matched K-M. Also report p95/max spectral and windowed color errors, nine
pair assessments, pooled 21, per-group means, per-row regressions and optimizer
metadata. Compare parent-available and grouped results on the same twelve rows.
Do not call an improvement on one subset universal, or tune on observed failures.
Do not impose Old Holland color screens on this different spectral window.

Check alignment and label/recipe consistency, rounding-aware grouping, train/test
disjointness, anchors, complete assessment coverage, no extrapolation, preserved
source/dependency hashes, numerical scalar prediction parity, exact pure
endpoints, bounded spectra, and unchanged fit coefficients after perturbing
excluded targets. Preserve raw data and coefficients under ignored target/;
retain original code, results and reports in this experiment. No runtime,
renderer, paper implementation or default change is authorized by the outcome.
