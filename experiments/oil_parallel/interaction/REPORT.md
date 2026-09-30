# Bounded empirical pair interactions: exploratory result

The chosen surrogate improves multicolor color prediction, with spectral tail regressions. It does not learn unseen pairs. This supports further investigation of mixture-form flexibility; it does not identify a physical cause or establish independent validation. All assessment samples were previously exposed. No runtime, renderer, Rust or paper change was made.

The equation, bounds, regularization, starts and selection rules were frozen in [PLAN.md](PLAN.md) before real fitting. The primary has the unchanged 93-parameter v3 KM base plus 24 empirical controls (six pairs × four cubic Bernstein controls). A normalized mass recipe drives the spectral logit correction; there are no RGB residuals. The correction controls are not optical coefficients. Folds have 20 active empirical controls because their unseen chromatic pair is fixed at zero. Base fitting and empirical fitting are sequential, not joint. No ablation or retuning occurred.

## Same 16 multicolor assessment recipes

All spectra use measured 400–700 nm / 31 bands. Color uses truncated D65/2-degree XYZ/Lab and DE00 without clipping or gamut mapping. RMSE/MAE summaries are across per-sample spectral errors; max-absolute denotes individual sample maximum-band error.

| Metric | v1 (21 fit) | v3 base (29 fit) | Empirical (29 fit) |
|---|---:|---:|---:|
| spectral_rmse mean | 0.026386 | 0.028495 | 0.024603 |
| spectral_rmse median | 0.019062 | 0.021625 | 0.018173 |
| spectral_rmse p95 | 0.061668 | 0.060696 | 0.062361 |
| spectral_rmse max | 0.062423 | 0.061210 | 0.063843 |
| spectral_mae mean | 0.023283 | 0.024908 | 0.020948 |
| spectral_mae median | 0.016370 | 0.018131 | 0.012602 |
| spectral_mae p95 | 0.058493 | 0.057357 | 0.059460 |
| spectral_mae max | 0.061637 | 0.060454 | 0.062920 |
| spectral_max_abs mean | 0.046946 | 0.054231 | 0.047268 |
| spectral_max_abs median | 0.038286 | 0.053973 | 0.039302 |
| spectral_max_abs p95 | 0.092105 | 0.091858 | 0.092527 |
| spectral_max_abs max | 0.102395 | 0.102132 | 0.100873 |
| delta_e_2000 mean | 3.677051 | 3.914976 | 2.782473 |
| delta_e_2000 median | 3.002714 | 3.136681 | 2.668211 |
| delta_e_2000 p95 | 6.561270 | 7.941854 | 5.007314 |
| delta_e_2000 max | 6.980678 | 8.222415 | 6.853006 |

Mean DE00 improves 28.9% against the actual refitted KM base, and 24.3% against v1. Mean RMSE improves 13.7% against its base and 6.8% against v1. Spectral p95/max RMSE worsen against both. Original engineering screen: mean RMSE <=.02 and p95 RMSE <=.05 fail; mean DE00 <=3, p95 <=6 and max <=10 pass. These are exploratory screens, not uncertainty estimates.

| Family | Count | v1 mean DE00 | v3 mean DE00 | Empirical mean DE00 | Empirical mean RMSE |
|---|---:|---:|---:|---:|---:|
| R+B+W | 2 | 2.8466 | 2.9283 | 3.0141 | 0.04512 |
| Y+B+W | 2 | 4.8163 | 4.7913 | 3.3538 | 0.03985 |
| Y+R+B | 3 | 4.5511 | 6.5305 | 4.4680 | 0.01459 |
| Y+R+B+W | 3 | 4.8063 | 4.3591 | 2.5823 | 0.01645 |
| Y+R+W | 6 | 2.5725 | 2.4219 | 1.7722 | 0.02176 |

Against v1, 11/16 colors improve. Color regressions: row 174 (Y+R+B): 5.450→6.853; row 172 (Y+R+B): 1.781→2.159; row 115 (R+B+W): 2.912→3.116; row 114 (R+B+W): 2.781→2.912; row 68 (Y+R+W): 3.335→3.346.

Against v3, 14/16 colors improve. Color regressions: row 115 (R+B+W): 2.892→3.116; row 68 (Y+R+W): 3.309→3.346.

## Entire pair-family exclusions

The absent interaction is zero for every wavelength. Consequently all eight withheld pairs equal their own fold-specific refitted KM base exactly. This is an explicit generalization boundary: empirical correction improves none of these unseen interactions. The pooled score differs from v1 solely because the KM base was refitted on other pair families. No three-/four-paint targets enter a fit. Perturbing all withheld spectra and repeating each fit leaves its fitted base and interaction coefficients exactly unchanged.

| Withheld family | Fit / test count | v1 mean DE00 | Fold KM = empirical mean DE00 | Fold KM = empirical mean RMSE |
|---|---:|---:|---:|---:|
| Y+R | 24 / 5 | 3.1448 | 2.8296 | 0.02610 |
| Y+B | 28 / 1 | 4.6120 | 4.0113 | 0.03599 |
| R+B | 27 / 2 | 5.8812 | 5.8135 | 0.05111 |

| Pooled eight-pair metric | v1 | Fold KM = empirical |
|---|---:|---:|
| spectral_rmse mean | 0.026685 | 0.033587 |
| spectral_rmse median | 0.019635 | 0.033275 |
| spectral_rmse p95 | 0.049538 | 0.055704 |
| spectral_rmse max | 0.054339 | 0.059707 |
| spectral_mae mean | 0.020459 | 0.024438 |
| spectral_mae median | 0.016381 | 0.024410 |
| spectral_mae p95 | 0.036058 | 0.039196 |
| spectral_mae max | 0.037126 | 0.039480 |
| spectral_max_abs mean | 0.064753 | 0.084855 |
| spectral_max_abs median | 0.047084 | 0.078640 |
| spectral_max_abs p95 | 0.138767 | 0.157500 |
| spectral_max_abs max | 0.153467 | 0.174309 |
| delta_e_2000 mean | 4.012308 | 3.723297 |
| delta_e_2000 median | 3.901372 | 3.701547 |
| delta_e_2000 p95 | 6.560412 | 6.390854 |
| delta_e_2000 max | 7.223977 | 6.947562 |

## Verification, bounds and cost

V1 and v3 baseline scores reproduced to 1e-12; independently refitted KM predictions match frozen v3 within 3.33e-16. Pure drift across all four fits is 1.11e-16. Four numerical tests pass: analytic derivative/scalar forward agreement, noiseless synthetic recovery, endpoint/bound/mass invariance and invalid inputs, unseen-pair zero behavior. The separate verification repeats all three real folds with perturbed withheld targets.

Seeded 10,006-recipe simplex corpus is finite, reflectance [0.01964,0.91430]. Empirical spectral correction spans [-0.05114,0.04367], mean absolute 0.01068; 29.7% of bands shift up and 70.3% down. Additional 606 edge recipes and 2,000 seeded face recipes remain finite, reflectance [0.01939,0.91430], correction [-0.05115,0.04531].

Analytically, pair-product sum <=1.5 and each Bernstein curve lies in [-.8,.8], hence absolute logit correction <=1.2 for every simplex recipe. The sigmoid gives bounded finite reflectance with no post-scoring clipping. Pure corrections vanish exactly, and near-pure corrections approach zero continuously. Ingredient-envelope departures are allowed empirical behavior. Negative, nonfinite and zero-mass recipes are rejected; positive total masses are normalized.

All four interaction fits converge in eight evaluations with no bound hits; total correction fitting time 0.0226s. Three-start KM refits total 0.7827s. Forward evaluation of 10,006 recipes ×31 bands averages 0.0710s (ten batches, interpreter/reporting excluded; not a performance guarantee). All 12 KM starts converge without bound hits. Each forward recipe adds pair products, 24-control spectral dot products and 31 sigmoids to KM. No LUT generated.

The low-dimensional basis imposes smooth wavelength behavior; it cannot represent sharp arbitrary spectral residuals. Pair weights assume symmetric bilinear composition dependence. Sparse ratios, especially one yellow/blue measurement and two red/blue measurements, cannot identify or validate whole pair trajectories. Summing pair interactions in three-/four-paint recipes assumes transfer from pair calibration; the exposed 16 mixtures supply exploratory evidence only. Numerical boundedness does not establish realistic appearance or optical physics. New ratios, repeated swatches and independent measurements are required before promotion.

## Reproduce

```powershell
target/measured-oils/venv/Scripts/python.exe -m unittest discover -s experiments/oil_parallel/interaction -p test_model.py -v
target/measured-oils/venv/Scripts/python.exe experiments/oil_parallel/interaction/run.py fit --out target/measured-oils/parallel/interaction-repeat
target/measured-oils/venv/Scripts/python.exe experiments/oil_parallel/interaction/run.py evaluate --out target/measured-oils/parallel/interaction-repeat
target/measured-oils/venv/Scripts/python.exe experiments/oil_parallel/interaction/verify.py
target/measured-oils/venv/Scripts/python.exe experiments/oil_parallel/interaction/write_report.py
```

Run refuses overwriting frozen fits. Verify targets the original experiment directory; repeat fit/evaluate use a fresh directory. BLAS/OpenMP thread limits are set in code before numerical imports. [summary.json](summary.json) includes all calibration and assessment metric quantiles, manifests and optimizer records; [errors.csv](errors.csv) contains every compact row error; [verification.json](verification.json) records invariants. Frozen coefficients remain in ignored `target/measured-oils/parallel/interaction/frozen-models.json`.
