# Fixed-method evaluation under inferred labels

Declared 2026-10-01 before fitting or scoring reconstructed data. This follows the
user's approved three steps: preserve recovery, repeat the frozen comparison,
and assess plausible mapping alternatives. The source recovery is committed at
`352312f`. It used the paper's aggregate means/counts; therefore this study is
conditional on inferred labels, not independent ground-truth validation.

## Unchanged method

Import `oil_external/run.py` and its dependencies without editing them. Check
every hash in its original result manifest. Retain the same Y/C/B/W subset,
rounded dry-pigment fractions, 31 wavelengths at 440-740 nm, 13 pure/tint anchors,
22-row training pool, 12 recipe groups, and 21 scored rows. Exclude each complete
chromatic-ratio group, including its white addition, from calibration. The twelve
ternaries never enter fitting. This produces ten fits per mapping before reuse
of identical training inputs. No Old Holland or previously mispaired coefficients
are reused. No fitting bounds, priors, objectives, starts or stopping settings
change. The empirical model is compared with its own fitted K-M base.

Primary endpoint: mean spectral RMSE over the twelve grouped ternaries. Also
report nine held-out pairs, all 21 assessments, p95/max errors, per-group and
per-row changes, parent-available ternaries, and windowed D65/2-degree DE00.
Windowed DE00 is not full-visible color error and is not comparable numerically
to the Old Holland study. This is recipe-based exclusion, not known batch-based
exclusion. The anchors are not a generalization test.

## Mapping sensitivity declared before model scores

Start with the frozen `oil_source_recovery/mapping.json`, SHA-256
`9e31ac91fcaa334b8bc56e9d3ae501d7ebe79de932ca066dba84ba276f9d6a22`.
Use the same paired-scan family, seven fixed pures, and published best/worst
counts as the completed ambiguity audit. At each diagnostic absolute mean-MSE
tolerance (2e-6, 5e-6, 1e-5), enumerate all orientation combinations of pairs
identified as mutable by that audit which intersect the selected 34 samples.
For each combination, solve for a full 175-sample witness satisfying all seven
mean constraints and the counts. Other mutable pairs remain free to compensate;
do not independently flip an assignment without a feasible full witness.

The completed per-pair audit resolved all 81 mutable-pair checks. It establishes
that other pairs cannot differ at the specified tolerances within this family.
Enumeration therefore covers every distinct selected-subset mapping in that
restricted family, provided every enumeration solver case resolves. Stop if a
case is unresolved; do not call a timeout infeasible. Directly verify every
witness against original spectra, means, counts, pure identities and permutation.
Deduplicate mappings by their full selected-subset spectrum assignment. Freeze
all variants and their tolerance membership before any optical-model fit.

These tolerances are sensitivity settings, not estimated uncertainty or
probabilities. Report the complete range and direction of the empirical-versus-
K-M difference; do not select the most favorable map. Include the stricter
5e-6 analysis and looser 1e-5 stress case separately. At 5e-6 the affected recipes
are Bw, By and Wcy; at 1e-5 they also include wCy and Cy.

## Execution and verification

Prepare and freeze provenance and variants, then fit calibration-only inputs,
then verify, then score. Reuse a fitted model only if recipe names, concentrations
and measured calibration spectra match byte-for-byte. Each unique training set
gets the unchanged multistart fit. Freeze all coefficients under ignored target/
before scoring. Preserve model hashes and optimizer diagnostics in the report.

Check no extrapolation, fixed split compatibility, complete coverage, unchanged
dependencies, independent scalar prediction parity, exact pure endpoints,
finite bounded spectra, and identical coefficients after excluded-target
perturbation and refitting for each unique calibration set. Abort on a failed
model fit. Report failed individual starts separately if another start converges.
Require frozen-input hashes to match at every phase. Preserve all original
experiments, raw source data, runtime, renderer and defaults. No measured preset
or physical-accuracy claim follows automatically from these conditional results.
