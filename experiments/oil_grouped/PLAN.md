# Frozen chromatic-ratio-family validation

Declared 2026-09-30 before fitting. This tests the existing bounded empirical
interaction model; no model, objective, bound or regularization change is made.
All data have previously been exposed. Results are exploratory development
evidence, not fresh independent validation or estimates of measurement noise.

## Question and comparison

Does the empirical model's improvement persist when a chromatic ratio and all
its white additions are excluded together? Compare each empirical prediction
with its own fold's K-M base, fitted on exactly the same training rows. Retain
V1 as a historical 21-row reference; do not treat the old V3 primary model as a
valid withheld-parent baseline.

## Fixed design

- Use the checksum-verified 45-row, four-paint Old Holland subset at 31 measured
  wavelengths. Preserve ingredient identities and normalized mass proportions.
- Retain the original 21 pure-paint / single-chromatic-paint white-tint rows as
  calibration anchors. Generalization of those anchors is not tested.
- Group the other 24 rows by their normalized Y:R:B ratio after removing W.
  Compare ratio components rounded to 12 decimal places, and verify the group
  membership and mass-scaling invariance before fitting. Grouping uses recipes
  only, never measured spectra, measured error, source-row adjacency or an
  inferred common physical preparation batch.
- Use the same 29-row training pool as the previous primary experiment: the
  original 21 plus eight chromatic pairs. For each ratio group, fit on that pool
  minus every member of the group, and assess every member of the group.
- Expected groups (one-based source rows): [60,61,62], [66,67,68], [69,70],
  [71,72], [84,85], [86,87], [112,114,115], [113], [172,173], [174,175],
  [176,177]. These are 11 groups, eight with 28 training rows and three with 29.
- The three Y:R:B groups have no member in the old training pool. They share one
  identical 29-row fit. Fit each unique training-row set once (nine unique fits),
  then freeze all models before any new error assessment. Do not add other
  multicolor observations to training. This controls training-pool expansion,
  rather than performing leave-one-group-out training on all other 45 rows.
- Every one of the 24 assessment rows receives exactly one prediction from a
  model that saw none of its chromatic-ratio group. No pooled CV model is a
  single deployable palette. Whole paint-pair-family exclusion is a different,
  earlier experiment; this study excludes exact chromatic ratios and their tints.

## Unchanged candidate and optimizer

Reuse `experiments/oil_parallel/interaction/run.py` without editing it. Its first
stage fits the fixed-pure opaque K-M model (93 parameters) using V1's three
starts, bounds and spectral priors; start selection uses training loss only.
The second stage fits four cubic-Bernstein wavelength controls per paint pair,
24 possible controls in total, as a bounded reflectance-logit correction.
Bounds remain +/-0.8, ridge weight 1e-4, one zero start, maximum 2000 evaluations
and all tolerances 1e-10. Absent training pair interactions remain exactly zero.
The base is fitted once per split and shared by both compared predictions.

Record every optimizer start, nonconvergence and active bound. Any failed fit
halts scoring; no dropping a failed fold, retries with changed settings, ablation,
hyperparameter sweep or assessment-driven model change is allowed.

## Checks and reporting

Before fitting: test grouping, complete coverage, train/test disjointness,
preserved anchors, missing-pair activation and mass-scaling invariance; reproduce
the frozen previous primary16 KM/empirical aggregate metrics and original V1
24-row metrics. Hash the plan, implementation, dependencies, source archive,
settings, colorimetry data, and previous model bundles into the prepared manifest.
Reject overwritten fits or changed provenance at later phases.

After freezing: independently decode K/S and corrections with scalar equations,
check pure endpoints and finite bounded reflectance, and run actual refits after
perturbing all non-training targets to verify both fitted stages are unchanged.
Report metrics separately for the 16 multicolor rows, eight parent pairs, pooled
24, each of 11 groups and equal-group macro means. Preserve per-row improvements
and regressions, spectral RMSE/MAE/max-band error and truncated-D65/2-degree
CIEDE2000 mean/median/p95/max without RGB clipping. Compare the same 16 rows with
the earlier parent-available study, clearly labelling the different protocols.

Original numerical screens remain descriptive: mean RMSE <=0.02, p95 RMSE
<=0.05, mean DE00 <=3, p95 DE00 <=6, max DE00 <=10. No confidence interval from
treating 24 related samples or overlapping training folds as independent.
No runtime, renderer, paper, default or dataset-distribution change is included.
Keep coefficients and raw measurements under ignored `target/measured-oils/`;
retain original code, aggregate metrics, per-row errors and the report here.
