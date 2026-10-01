# One comparison: add multicolor calibration, exclude complete recipe families

Declared 2026-10-01 before fitting or scoring this comparison. The user requests
this one comparison now and has not capped future research. Reuse the unified
Old Holland Eight model structure and all settings. Change only the calibration
pool. This study produces comparative evidence, not a replacement runtime model.

## Data and exact family definition

Use the unchanged 286-row Old Holland source and native 31-band 400-700 nm spectra.
Keep normalized recorded tube-paint mass proportions and source paint identities.
The 8 pures and 45 single-chromatic white tints are shared anchors (53 rows).
The other 233 rows contain at least two chromatic paints. Group them by their
seven chromatic proportions after removing white and normalizing, rounded to
12 decimal places, as in the earlier grouped experiment. Verify that rounding
does not merge distinguishable recorded ratios. This is a recipe grouping,
not a claim about shared physical preparation batches.

There are 107 families: 99 include multicolor rows and 50 have binary parents.
Group sizes are 1-4. Every group's parent and all its recorded white additions
are excluded together, including parents that would otherwise enter base fitting.
Keep other ratios of the same paint combination available; this assesses transfer
to excluded ratios, not exclusion of an entire pigment combination or batch.

## Paired fits

For each family, fit both procedures to their own permitted rows:

- **Binary-only:** the original 103 pure/binary rows minus the whole excluded
  family. Each distinct pool contains 102 or 103 samples; 51 unique fits.
- **Expanded:** all 286 rows minus the whole excluded family. Each pool contains
  282-285 samples; 107 unique fits. This adds measured multicolor recipes to both
  the base stage and the correction stage.

Both procedures use the exact imported `oil_unified_eight/run.py` fitter:
217 base parameters with measured-pure K/S, white S=1, the three original starts,
bounds, regularizers and stopping rules; then the existing 112 possible bounded
pair controls. Controls absent from a pool stay inactive as before. No new
interaction term, reweighting, attenuation, hyperparameter search or target-based
selection. The original mean-error and mean-prior normalization stay unchanged;
the expanded sample distribution can change the compromise between recipe types.

Reuse identical training masks within an approach. Fit all 158 models, preserve
failures, freeze their bundle, verify it, then score. Never combine coefficients
across folds into a supposed deployable palette.

## Outcomes declared before scoring

Primary: paired change in mean windowed DE00 on the same 183 multicolor samples,
using each sample's excluded-family fit. Companion: mean spectral RMSE and
equal-family means over the 99 families containing multicolor assessments.
Report medians, p95/max, counts of improvements/regressions, white/no-white and
ingredient-count groups, and the largest regressions. Also report all 50 excluded
chromatic binary parents and the full 233-row assessment. Retain base-only results
for both pools to distinguish base changes from correction changes.

Compare the two procedures within this common split. The packaged unified model's
earlier 183 scores had binary parents available; they are a historical reference,
not the matched comparator here. Existing source observations and earlier scores
informed development, so do not claim an untouched final test or independent
cross-batch validation. These same-source measurements remain valid evidence for
the declared recipe-exclusion question. No eight-ingredient mixture is measured.

Do not turn average gains into a blanket accuracy claim if tails or individual
families worsen. No model or package is promoted automatically from this study;
all fold results describe a calibration procedure rather than one final fit.

## Verification and reproducibility

- Test family scale/white invariance, all-row coverage, train/test separation,
  anchor retention, exact pools and all 183 primary/50 secondary rows scored once.
- Freeze source, method, settings, protocol and group hashes. Reproduce the
  archived full binary-only fit before the fold run and check its old scores.
- Refit every distinct pool after perturbing excluded measurements; require all
  optical and pair coefficients unchanged. Check every fit's convergence/bounds.
- Independently scalar-decode each model on its scored recipes, pures and dense
  controls. Check exact pure endpoints and finite bounded predictions on 257
  additional all-eight recipes, including the equal mixture.
- Require both approaches to cover the complete assessment before claiming a
  complete primary result; retain failed statuses and never drop difficult rows.
- Keep original runtime packages, coefficients, source and previous experiments
  unchanged. Raw measurements and new coefficient bundles remain under ignored
  target/. Commit original scripts, split metadata, numerical results and report.

No renderer or Rust code changes are needed for this comparison.
