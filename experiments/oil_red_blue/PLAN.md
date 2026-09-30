# Frozen-model red/blue diagnosis

2026-09-30. Follow-up to the grouped recipe study. This is a post-hoc diagnosis,
not a new candidate, fit, optimization, benchmark or independent validation.
Retain all frozen artifacts and implementation bytes. No runtime/paper/default
change, source-row removal or re-estimation of any coefficient is permitted.

Compare three already-fitted empirical models: the 29-row model with both
red/blue parent ratios, the fold excluding red/blue 1:1 (only 9:1 available), and
the fold excluding 9:1 (only 1:1 available). Their K-M bases also differ, so
model-to-model disagreement combines base-fit and correction sensitivity.

Probe red fraction t=R/(R+B) from 0 to 1 in increments of 0.001 at white mass
fractions w=0, 0.5 and 0.95. Each recipe is [Y,R,B,W]=[0,(1-w)t,(1-w)(1-t),w].
Report maximum pairwise DE00 and spectral RMSE between frozen predictions at
each recipe, their peaks, and base-only disagreement for comparison. These are
model-disagreement diagnostics, not actual prediction errors, calibrated
uncertainty, noise estimates, evidence of instability or new measurements.
Do not select a better fitted model from these comparisons.

At the four measured red/blue recipes (source rows 112-115), decompose the
additive logit correction into RB, RW and BW terms. Report original K-M,
RB-only, white-pair-only and full predictions with measurement error and each
row's fit/assessment status for that model. Component removal is solely a
post-hoc explanatory counterfactual; do not adopt a component-disabled model.
DE00 and reflectance effects are nonlinear and cannot be added like logit terms.

Check the full 286-row source for all red/blue/white-only recipes and exact
normalized duplicates. Do not assume that recipes with yellow/other paints can
act as extra red/blue observations, or that related recipes share a physical
preparation batch. Preserve actual support counts.

Analytical check: RB weight=4(1-w)^2*t*(1-t); RW=4(1-w)*t*w;
BW=4(1-w)*(1-t)*w. At 1:1, RB weight is 1, 0.25 and 0.0025
for the three white levels. At 9:1 without white it is 0.36. The ratio
1/0.36 is amplification of a logit multiplier, not a reflectance/color error
ratio and not a proof of causation. Pure R/B endpoints of an unwhitened path
remain fixed. Whitened endpoints are mixtures with W, so need not be unchanged.

Before reporting, reproduce the relevant frozen fold scores, verify all artifact
hashes and preserved upstream manifests, independently decode grid spectra,
verify component recombination and the analytic pair weights, and check bounded
finite spectra and pure endpoints. Raw spectra/grid predictions stay ignored
under target/measured-oils/red-blue-diagnosis. Track aggregate results, errors,
plots and code only. No new error threshold will be used to label a curve valid.

Propose a fixed measurement matrix, if physical acquisition is possible:
R:B=1:9,1:3,1:1,3:1,9:1 crossed with W=0%,50%,95% by recorded mass.
These 15 conditions provide 11 currently missing combinations and four repeats.
Use three independent preparations per condition, plus three independent pure
swatches each of R, B and W (54 swatches total). Repeated readings of one swatch
are not independent preparations. Relative parts are not absolute gram amounts;
batch size must suit the actual balance and the smallest ingredient. Preserve
thickness/application, substrate, drying, measurement geometry and repeated
readings as metadata. Keep fresh assessment targets separate from model tuning.
This is a proposal, not a claim to have obtained physical measurements.
