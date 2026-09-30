# Color-aware objective: useful multicolor tradeoff, worse pair extrapolation

The declared hybrid improves multicolor mean DE00 from 3.915 (same-protocol v3) to 3.163, but mean spectral RMSE rises from 0.02849 to 0.02880 and worst spectral RMSE rises from 0.06121 to 0.07033. Withheld pairs worsen in both mean metrics: DE00 3.723 to 4.335; spectral RMSE 0.03359 to 0.03728. Retain v1 as the research baseline. This experiment supports objective misalignment as a contributor on these multicolor recipes, not as a sufficient general fix. All assessment rows were previously exposed; this is exploratory development evidence.

## Declared model and objective

One candidate, no ablation or sweep: unchanged fixed-pure opaque homogeneous K-M, 93 log-S parameters, mass recipes and white gauge. The objective is 0.5 spectral MSE + 0.5 (0.02/3)^2 mean squared Lab Euclidean distance + unchanged v1 regularization. The mean color term is across rows, summing its three channels. The 3-unit scale is a declared engineering normalization inspired by the original color screen; it does not equate DE76 with DE00. Lab distance is a smooth fitting surrogate; all reported color errors are truncated-D65 CIEDE2000. No clipping, gamut mapping, extrapolated spectral tails, or corrected pure spectra.

Plan/config were written before real fitting; implementation/config/plan and shared dependencies were hashed in the partition. Four fits used primary29 or complete pair-family exclusions, each with the three original starts and bounds/tolerances; successful starts were chosen only by training loss. All four models were frozen before evaluation. One sequencing deviation: archived baseline score reproduction was verified during evaluation, after fitting, rather than before fitting as planned. It passed within 1e-12. No settings were changed after evaluation.

## Same-row assessment

| Set/model | RMSE mean | RMSE p95 | RMSE max | MAE mean | DE00 mean | median | p95 | max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| primary_multicolor16/v1 | 0.02639 | 0.06167 | 0.06242 | 0.02328 | 3.677 | 3.003 | 6.561 | 6.981 |
| primary_multicolor16/v3 | 0.02849 | 0.06070 | 0.06121 | 0.02491 | 3.915 | 3.137 | 7.942 | 8.222 |
| primary_multicolor16/hybrid | 0.02880 | 0.06583 | 0.07033 | 0.02504 | 3.163 | 3.219 | 5.109 | 5.213 |
| pair_family_cv8/v1 | 0.02668 | 0.04954 | 0.05434 | 0.02046 | 4.012 | 3.901 | 6.560 | 7.224 |
| pair_family_cv8/v3 | 0.03359 | 0.05570 | 0.05971 | 0.02444 | 3.723 | 3.702 | 6.391 | 6.948 |
| pair_family_cv8/hybrid | 0.03728 | 0.05658 | 0.06098 | 0.02770 | 4.335 | 3.839 | 5.954 | 6.264 |
| cross_fitted24/v1 | 0.02649 | 0.06035 | 0.06242 | 0.02234 | 3.789 | 3.179 | 6.897 | 7.224 |
| cross_fitted24/v3 | 0.03019 | 0.06040 | 0.06121 | 0.02475 | 3.851 | 3.350 | 7.713 | 8.222 |
| cross_fitted24/hybrid | 0.03163 | 0.06383 | 0.07033 | 0.02593 | 3.553 | 3.723 | 5.366 | 6.264 |

The pooled 24 diagnostic combines 16 primary-model and eight fold predictions; it is not one deployable artifact. On primary16 the hybrid still fails the original mean spectral RMSE, p95 spectral RMSE and mean DE00 screens; p95/max DE00 pass. Calibration29 mean DE00 and spectral RMSE are 2.018 and 0.02027.

## Family results and regressions

| Family | n | v1 DE00 | v3 DE00 | hybrid DE00 | hybrid RMSE | hybrid DE00 max |
|---|---:|---:|---:|---:|---:|---:|
| R+B+W | 2 | 2.847 | 2.928 | 2.728 | 0.04249 | 3.395 |
| Y+B+W | 2 | 4.816 | 4.791 | 4.135 | 0.04719 | 4.453 |
| Y+R+B | 3 | 4.551 | 6.530 | 5.035 | 0.02430 | 5.213 |
| Y+R+B+W | 3 | 4.806 | 4.359 | 3.921 | 0.01932 | 5.074 |
| Y+R+W | 6 | 2.572 | 2.422 | 1.668 | 0.02511 | 3.043 |
| Y+R (excluded pair) | 5 | 3.145 | 2.830 | 3.904 | 0.03191 | 5.290 |
| Y+B (excluded pair) | 1 | 4.612 | 4.011 | 3.516 | 0.03507 | 3.516 |
| R+B (excluded pair) | 2 | 5.881 | 5.814 | 5.822 | 0.05181 | 6.264 |

Versus v3, 12/16 multicolor colors improve and four worsen; 9/16 spectra improve. Only 3/8 excluded-pair colors and 1/8 spectra improve. Full per-row metrics including MAE and band-error maxima are in errors.csv; no failed case was removed.

Largest color regressions against v1:

- primary_multicolor16, row 172 (Y+R+B): 1.781 to 4.868, +3.086 DE00.
- primary_multicolor16, row 173 (Y+R+B+W): 2.253 to 2.783, +0.530 DE00.
- primary_multicolor16, row 115 (R+B+W): 2.912 to 3.395, +0.483 DE00.
- primary_multicolor16, row 62 (Y+B+W): 3.804 to 3.817, +0.013 DE00.
- pair_family_cv8, row 69 (Y+R): 1.357 to 3.946, +2.590 DE00.
- pair_family_cv8, row 84 (Y+R): 2.735 to 3.716, +0.981 DE00.
- pair_family_cv8, row 113 (R+B): 4.538 to 5.379, +0.841 DE00.
- pair_family_cv8, row 71 (Y+R): 3.264 to 3.731, +0.467 DE00.

## Numerics, preservation and cost

All 12 starts converged (10 to 13 evaluations), no bound variables; optimizer-only total 0.959 seconds, excluding interpreter startup/checks/reporting. Parameter count remains 93. Pure-paint maximum absolute reflectance drift is 1.11e-16; this is a hard construction constraint, not predictive validation.

Central-difference residual Jacobian max error 1.32e-11; Lab agreement with colour including the dark linear branch 8.35e-14; independent scalar synthetic K-M error 5.41e-16. Smooth noiseless synthetic recovery using declared regularization has maximum reflectance error 4.60e-6. An initial jagged random-S recovery fixture showed 0.00731 error because curvature penalizes the known jagged truth; that fixture was replaced with smooth known curves before real fitting. This observation is regularization bias, not an optimizer failure or candidate retuning. Real saved-model scalar checks and pure constraints pass. V1/v3 same-row mean DE00 reproduces archived results within 1e-12.

summary-normalized.json uses unambiguous hybrid/v3 names; summary.json retains the original helper labels in nested sections, as documented there. The frozen implementation and model remain intact. checks.json, errors.csv, partition hashes and complete optimizer records make the result auditable.

## Reproduce

Run in repository root with OPENBLAS_NUM_THREADS=1, OMP_NUM_THREADS=1 and MKL_NUM_THREADS=1. Use target/measured-oils/venv/Scripts/python.exe experiments/oil_parallel/objective/run.py check, then prepare, fit, evaluate, each with the same fresh --out target/measured-oils/parallel/objective/repeat. Existing frozen fits are refused. Finally run report.py. Raw measurements and coefficient artifacts remain under ignored target output; no runtime, renderer or paper changes.

The archive cannot establish which physical assumptions cause residuals. One excluded yellow/blue sample is especially weak family evidence. Lab weighting can sacrifice spectral or alternate-illuminant fidelity. These results justify a documented color/spectral tradeoff but require new swatches for independent validation; they do not support promoting this hybrid as a universal palette.
