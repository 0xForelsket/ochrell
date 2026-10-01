# One base-calibration ablation on the exposed 35-row cohort

Declared 2026-10-01 before any new fit or score. The user approved the preceding
diagnosis's proposal: calibrate K-M on pure paints and white tints, freeze that
base, then calibrate the unchanged empirical pair controls on the original full
pure/binary pool. Compare with the existing all-binary-base method across all
35 ternaries and 25 palettes. No new correction term, gate or tuned parameter.

## Exact intervention

Reuse the cohort and original models from `oil_ternary_transfer`. Original bundle:
`ddc0e552df366ed4c0e00bdfeb581ca03f48f3ab1f71501808bc2ec778b94fbb`.
Check its entire manifest and the unchanged source archive. Keep native 31-band
400-700 nm spectra, normalized tube-paint fractions, original paint identities,
white gauge, assessment rows and exclusion of known controls 172/174/176.

For each palette:

1. Select the original calibration rows which are pure or contain Mixed White.
   Because the original pool contains only pure/binary recipes, this selects
   pure endpoints and white tints only. Exclude all chromatic binaries from this
   first stage. Use the same 93-parameter K-M fit, three starts, objective,
   priors, bounds and stopping criteria. Do not rescale the existing objective
   or priors to compensate for the smaller pool; retain the original mean-error
   normalization. Changing the sample set therefore also changes its weighting
   relative to the unchanged priors, which is part of this intervention.
2. Freeze the resulting K-M coefficients. On the exact original full calibration
   pool, fit the same 24 pair controls with the unchanged imported feature map,
   residual, analytic Jacobian, zero start, [-0.8,0.8] bounds, ridge and optimizer
   settings. White-pair terms are refitted as well as chromatic-pair terms, exactly
   as in the original procedure. No base parameter may move in this stage.

## Comparisons declared before scoring

Report four models: original K-M, original empirical, anchor-calibrated K-M and
anchor-calibrated empirical. Primary endpoint is the change in mean per-sample
spectral RMSE for new versus original empirical on all 35 targets. Companion:
equal-palette mean over 25 palettes. Also report base-only change, incremental
benefit of the new correction over its own base, comparison with original K-M,
per-row/palette regressions, p95/max errors and windowed D65/2-degree DE00.

Rows 205,197,199 motivated the ablation. Report them separately, but do not
select a method based only on those cases or exclude regressions elsewhere.
No attenuation comparator is needed here: the sole new change is K-M calibration.
Do not modify objectives, bounds or row selections after results. Preserve failed
fits and withhold any complete-cohort primary claim if a palette fails entirely.

Prepare protocol/input hashes and partitions, fit all palettes, freeze the new
bundle, verify, then score. Raw measurements and fitted coefficients remain under
ignored target/. Original files and frozen bundles remain unchanged.

## Verification

Verify exact target coverage and disjointness, four pure endpoints and white-tint
coverage in each new base pool, original full pool in stage two, and no ternary
in either fit stage. Before interpretation, refit stage two with every original
archived base and require reproduction of the original pair coefficients; this
checks that the extracted stage is otherwise unchanged.

Repeat each new fit after perturbing excluded targets and require identical
coefficients. Independently perturb chromatic calibration targets and refit only
stage one to verify that they cannot affect the new base. Confirm that stage two
leaves base coefficients byte-identical. Check independent scalar decoding, exact
pure endpoints, finite bounded predictions, replay of all original 35 scores,
and frozen input/bundle integrity. No Rust/renderer checks apply to this research
experiment because production code is unchanged.

This is an exposed-data calibration ablation, not independent validation. Earlier
outcomes motivated its selection; the source dataset and target spectra are
already known. Some white-tint data also violate fixed-pure opaque assumptions,
so the intervention is a test of a calibration compromise, not a demonstrated
physical correction. Report improvements and harms honestly; no default or
measured preset promotion follows automatically.
