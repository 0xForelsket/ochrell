# One constrained ternary attenuation experiment

Declared 2026-10-01 before fitting or scoring this revision. The user approved
the preceding diagnosis's proposal: learn one attenuation strength from two
Y/C/B ternaries and assess the third, rotating exclusions. All observations were
previously exposed, and the rule was motivated by their failures. This is an
exploratory revision, not independent validation or a paper-faithful change.

## Frozen inputs and one fixed rule

Use the existing seven inferred mapping projections and frozen K-M/empirical
models from `oil_reconstructed`. Bundle SHA-256:
`8090dd57ce49b584fcae15cdb85eafbe942a4181c97f53b27a95d22265bc1ced`.
Do not refit any K-M parameter or pair curve. Check all original dependency,
mapping, source and settings hashes. No new ordering search is permitted.

Normalize the four paint fractions to sum to one. Let the original empirical
logit shift be `D_chromatic + D_white`, separated by whether a pair contains W.
Define one symmetric polynomial gate and one scalar strength:

```
h(c) = 27 * cY * cC * cB
0 <= lambda <= 1
new_shift = (1 - lambda*h(c))*D_chromatic + D_white
R_new = sigmoid(logit(R_KM) + new_shift)
```

The factor 27 normalizes the gate's maximum to one at an equal Y/C/B mixture
without white, by the arithmetic/geometric mean inequality. Use total recipe
fractions, not fractions renormalized after removing white. The rule is smooth,
symmetric among the three chromatic pigments, and exactly inactive whenever any
chromatic pigment is absent. Lambda zero recovers the original correction.
No wavelength-dependent scale, pair-specific strength, sign reversal, new basis,
recipe-specific branch, threshold or alternative gate is tested.

All three measured Y/C/B ternaries have 2:1:1 ratios, so h=27/32=0.84375. Even at
lambda=1 the rule retains 5/32=15.625% of their original chromatic logit shift.
This follows from the fixed smooth gate; do not widen the bound or renormalize
the gate to these samples after observing results. On an equal-third Y/C/B recipe,
lambda=1 removes the empirical correction entirely. No measurement at that recipe
is available here, so that property is a mathematical boundary, not accuracy proof.

## Calibration and assessment

For each of seven mappings, use the unchanged 22-row calibration model shared by
the three chromatic ternaries. For each excluded label in Bcy, bCy and bcY, fit
lambda only on the other two measured spectra. The excluded target must not enter
the scalar fitting function. The original binary calibration and all K-M/pair
coefficients remain frozen. This yields 21 scalar fits and 21 excluded-target
assessments, representing three physical recipe labels under seven mappings,
not 21 independent measurements.

Minimize mean squared spectral reflectance error over the two calibration rows
and the existing 31 bands, 440-740 nm. No new regularization or color objective.
Use SciPy bounded scalar minimization on [0,1], xatol=1e-12, maxiter=1000, and
explicitly compare both endpoints. Choose the lowest objective; exact ties favor
smaller lambda. A failed optimizer stops the study. Inspect a fixed 1001-point
calibration-only objective profile as a numerical check, not another model search;
stop if it finds a materially lower objective than the selected solution.

Freeze the plan, implementation, partitions and all scalar fits before scoring.
Primary report: mean excluded-target RMSE over the three chromatic ternaries,
relative to both the original empirical correction and the fold-matched K-M base.
Also report per-row RMSE, spectral maximum error, windowed DE00, calibration loss,
lambda/boundary behavior, and ranges across mappings. Improvement over the original
correction and improvement over K-M are separate findings; do not infer one from
the other. No significance claim or product quality screen is appropriate for
three exposed recipes.

For context, reproduce the original 21 grouped assessments and replace only the
three chromatic-ternary predictions with the new excluded-target predictions.
The nine white ternaries and nine pairs must remain bit-identical under this rule,
using their own original grouped models. This composite score is explicitly a
mixture of the previous grouped protocol and the new scalar exclusion protocol;
it does not retrospectively change the original benchmark or training budget.

## Checks and limits

Verify independent scalar decoding, exact lambda-zero parity, unchanged binary
edges, pure endpoints and faces containing at most two chromatic pigments,
finite bounded spectra, and the gate's [0,1] bounds. Check representative tiny
third-pigment fractions to rule out a discontinuous on/off implementation.
Refit after perturbing the excluded target and require exactly the same lambda
and calibration objective. Replay all 147 original assessment records. Preserve
upstream hashes and both coefficient bundles through verification and scoring.
Keep source-derived coefficients/profiles under ignored target/ and version the
protocol, scripts, derived summaries and report. Do not change runtime, renderer,
defaults, original studies or the paper implementation.

This cannot establish physical third-pigment behavior. The inferred labels used
published aggregate scores, all assessment data influenced the research direction,
and every observed chromatic ternary has the same gate value. Success would show
only whether a restricted, composition-dependent retreat toward the existing K-M
base limits the previously diagnosed harm. Report a boundary solution, failure to
beat K-M, or any regression directly; do not iterate within this experiment.
