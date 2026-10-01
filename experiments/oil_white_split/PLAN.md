# Diagnose the white / no-white split without refitting

Declared 2026-10-01 after the reconstructed-data evaluation. The user authorized
investigating why the frozen empirical correction helps white-containing
ternaries and harms the three Y/C/B ternaries. These are exposed observations;
this work is explanatory, not a new validation or a model-selection exercise.

Use the exact frozen coefficient bundle from `oil_reconstructed`, SHA-256
`8090dd57ce49b584fcae15cdb85eafbe942a4181c97f53b27a95d22265bc1ced`.
Retain all seven feasible mapping projections and the original grouped fits.
Verify dependency hashes and replay saved errors before interpreting results.
Do not fit, change any coefficient, optimize a scale, alter a mapping, promote
a component-removal variant, or change product/runtime code.

Questions and diagnostics:

1. Inspect calibration coverage and the active pair-feature blocks. Determine
   which interactions are observed separately and which combinations arise only
   in held-out ternaries. Distinguish a structural limitation from a demonstrated
   physical mechanism. Check nominal within-pair ratios against calibration.
2. Decompose the exact additive logit correction into six pair terms. Compare
   K-M, all terms, only chromatic-pair terms, only white-pair terms, individual
   pair additions and individual pair removals. These are counterfactual
   attributions from frozen models, not trained alternative models.
3. Compute exact Shapley allocations of the spectral MSE reduction across the
   active pair terms by enumerating their subsets. This accounts for the
   nonlinear reflectance transform; do not add RMSE or DE00 changes and pretend
   they are additive. Verify allocations sum to the actual MSE reduction.
4. In reflectance space, compare the correction with the displacement from K-M
   to the measured spectrum. Decompose MSE change as
   `mean(d*d) - 2*mean(d*(measured-KM))`. Report direction/alignment and the
   descriptive projection `alpha = dot(d, measured-KM)/dot(d,d)`: a negative
   value means movement in the wrong direction, and 0 < alpha < 0.5 means the
   full correction overshoots enough to increase MSE. This is an explanatory
   statistic using exposed measurements, not a scale to deploy or fit.
5. Report calibration-pair residuals separately from grouped assessment errors,
   explain important wavelength regions, and check conclusions across all seven
   mappings. Store detailed source-derived spectra only under ignored target/;
   version code, derived diagnostics, plots and a candid report.

Checks: source/bundle/input hashes unchanged; all 147 saved assessment records
reproduced; pair terms recombine exactly; independent scalar full predictions
agree; removal of an absent pair changes nothing; pure endpoints are unchanged;
counterfactual predictions are finite/bounded; Shapley sums and squared-error
identities agree numerically. No Rust or renderer test is relevant because this
is an isolated frozen-model diagnosis.

End with the narrowest supported explanation and one proposed future experiment.
Do not run a revision during this diagnosis. Mapping ambiguity, reconstruction
bias, small sample count and truncated colorimetry retain their existing limits.
