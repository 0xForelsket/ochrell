# One predefined comparison: balance four calibration categories

Declared 2026-10-01 before candidate fitting or scoring. The earlier expanded
calibration improved multicolor prediction but worsened binary mean errors and
no-white multicolor mean color error. Test one category-balancing rule, with the
same optical model, regularizers, settings, training pools and complete-family
exclusions. No weight sweep, new model term or deployable palette fit in this pass.

## Frozen design and weights

Reuse all 107 recipe families and the 282-285-row expanded training pools from
`oil_multicolor_calibration`. The original 158 binary/expanded fits and their
reported results are frozen comparators; reuse them without refitting. Pure
endpoints remain hard constraints. Keep the eight pures and 45 white-tint anchors.

The four nonpure categories in the complete source are:

1. Two chromatic paints, without white: 50 rows.
2. One chromatic paint plus white: 45 rows.
3. At least three chromatic paints, without white: 56 rows.
4. At least two chromatic paints plus white: 127 rows.

For each training pool separately, let n be its total rows, m its nonpure rows,
and n_g the number of permitted training rows in category g. Assign each row in
g weight w_i = m / (4 n_g). Pure rows retain weight 1. All four categories must
be present. Only recipes and training membership determine these weights.

In both base and correction objectives, multiply each spectral data residual
and its Jacobian row by sqrt(w_i); retain the existing division by sqrt(n * 31).
Thus the total row weight stays n, and the nonpure spectral objective is
(m/n) times the average of four category mean squared reflectance errors.
Pure residuals are zero apart from floating point noise. Preserve the curvature,
amplitude and pair-control priors exactly, including their original normalization.
This changes the allocation of data weight, not its total relative to priors.

Use the same measured-pure K/S, white S=1, 217 log-scattering parameters, three
starts, bounds and stopping rules. Then use the same 112 possible bounded pair
controls and inactive-control rule. Weight both stages, without changing the
model's prediction function or pure endpoints. Fit exactly 107 candidate models.

## Assessment declared before scoring

Primary: mean windowed DE00 on the same 183 family-excluded multicolor rows.
Companion: mean spectral RMSE and equal-family means over the 99 primary families.
Compare the balanced candidate to both the frozen binary and expanded methods.
Report all three corrected models, and all three bases, under identical splits.

The motivating question is whether balancing recovers binary and no-white
accuracy while retaining multicolor gains. Report the 50 excluded binaries,
56 no-white multicolors, 127 with-white multicolors and all 233 assessed rows;
ingredient-count groups; means, medians, p95/max; improvement/regression counts;
and the largest regressions against each comparator. Do not substitute pooled
gains for adverse subgroup or tail results. No post-result weight changes.

Earlier results motivated this rule: these are same-source development results,
not an untouched final test, unseen pigment combinations or independent batches.
Families exclude a complete normalized chromatic ratio and its white additions;
other ratios using the same paints remain in training. Anchors are not scored as
predictive validation. No measured recipe contains all eight ingredients.

## Verification and artifacts

- Verify the previous frozen bundle, partition, summary, per-row scores and all
  source/method/package hashes; reproduce archived comparator summaries exactly.
- Test category totals and objective scaling, both analytic Jacobians, retention
  of unchanged priors, identical exclusions and fit interfaces receiving only
  selected data. Uniform weights must reproduce one frozen expanded fit exactly.
- Freeze plan, fitter, tests, source and comparator hashes before candidate fits.
  Preserve failures, require complete coverage and freeze all candidates before
  assessing them. Check optimizer convergence and bounds.
- Refit every candidate with excluded spectra replaced; require all coefficients
  unchanged. Scalar-check predictions, exact pure endpoints and finite (0,1)
  reflectance on recorded and 257 additional dense recipes for every model.
- Independently recompute aggregate scores from the exported CSV before reporting.

Keep measurements and coefficients under ignored target/. Commit original code,
weights/split metadata, numerical results and the report. Preserve existing local
runtime packages and defaults. A final deployable model is a separate decision.
