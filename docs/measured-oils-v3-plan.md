# Fixed-pure model with chromatic-pair calibration

Declared 2026-09-30 before fitting v3. Baseline checkout `14b37f4`; v1 and the
rejected v2 remain frozen. This tests whether more relevant calibration data
helps the unchanged v1 model; it does not introduce another optical correction.

## Motivation and local sensitivity diagnostic

White-tint fitting barely changed when smoothing was removed, and the single
soft-pure revision improved tint fit while worsening other mixtures. Its yellow
mixing strength changed sharply despite a tiny pure-color shift. Test whether
chromatic-pair calibration provides useful constraints without freeing the pure
spectra or increasing parameter count.

Before fitting, evaluate the data-only reflectance Jacobian with respect to the
three chromatic log-S coefficients at each wavelength using frozen v1 parameters.
Compare the 21 calibration recipes with those recipes plus the eight available
chromatic pairs. Recipe coordinates alone enter this diagnostic; the added
recipes' measured spectra do not enter the Jacobian. No penalty terms are included.

Initial computation: the median per-wavelength condition number decreases from
7.41 to 2.43, and the maximum from 25.66 to 4.68. At 700 nm the weakest singular
value increases from 0.00878 to 0.07183, and the condition number decreases from
19.37 to 2.91. These are local sensitivities under the assumed model, not empirical
noise estimates, parameter confidence intervals or proof of physical accuracy.
Preserve a per-wavelength CSV and a plot for this diagnostic.

## One fixed calibration protocol

Keep all v1 equations, hard pure constraints, 93 parameters, positive scattering
bounds, priors, three initializations, tolerances and optimizer settings unchanged.
Use the same normalized recorded tube-paint masses and measured 31-band grid.
Do not fit thickness, substrate, surface corrections or per-mixture adjustments.
The normalized data objective now uses the applicable training-row count; the
same regularization weights remain fixed. No row is removed for a large residual.

Primary model: train on 29 rows, comprising the original 21 plus the eight
nonwhite pairs (source rows 60,66,69,71,84,86,112,113). Freeze the resulting model
before evaluating the 16 three-/four-paint rows
(61,62,67,68,70,72,85,87,114,115,172,173,174,175,176,177).
Select among optimizer starts using training objective only.

Also predeclare three leave-one-pair-family-out folds:

| Withheld family | Withheld rows | Training count | Evaluation count |
|---|---|---:|---:|
| Y+R | 66,69,71,84,86 | 24 | 5 |
| Y+B | 60 | 28 | 1 |
| R+B | 112,113 | 27 | 2 |

Each fold trains on the original 21 plus the other two pair families. A fold
cannot see any measurement of its withheld pair family or any three-/four-paint
measurement. Fit all four models before evaluating any new prediction. There is
no hyperparameter selection across folds, no best-fold selection and no retuning
after evaluation. The folds are validation refits of the same model/protocol,
not additional candidate optical models.

## Honest comparisons

These 24 evaluation mixtures were exposed during v1 and v2 analysis. All new
numbers are **exploratory development evidence**, even when the particular
measurement was excluded from a particular fit. Do not call the 16-row remainder
a fresh independent holdout. Do not compare v3 on 16 samples with v1 on all 24 as
if the sets were equal.

Report:

1. Primary-model calibration performance on 29, pure colors separately, and
   generalization to 16 mixtures, with v1 rescored on exactly the same rows.
2. Withheld-pair error per family, pooled over eight rows, and a macro average
   that gives the three families equal weight. Compare each with v1 on the same
   recipes. There is only one yellow/blue evaluation recipe: no broad ratio
   coverage claim follows from its result.
3. A clearly labelled 24-row cross-fitted diagnostic: the 16 primary-model
   predictions plus eight predictions from their respective withheld-family
   models. This is not the performance of one deployable palette artifact.
4. Spectral RMSE/MAE/maximum band error and truncated-range CIEDE2000: mean,
   median, p95, maximum, each family and worsened cases. Keep the original five
   numerical screening thresholds unchanged, applying them to the primary
   16-row assessment and labelling the assessment exploratory.

Verify pure spectra stay exact, all starts converge or failures are retained,
no evaluated row enters its training set, and independent scalar K-M agrees with
saved coefficients. Verify frozen v1 predictions reproduce the recorded result.
Preserve every fit, configuration, row manifest, hash and failure. Synthetic
tests should confirm the split excludes complete pair families and the analytic
data Jacobian matches finite differences for multichromatic recipes.

Even favorable results need new physical mixtures or a genuinely unexposed
dataset for an independent accuracy claim. There is no automatic default change
or runtime integration in this experiment. Source/coefficient artifacts remain
local research files as the existing artifact-management choice.
