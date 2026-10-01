# Unified Old Holland Eight: fitting and local runtime packaging

Declared 2026-10-01 before the new fit or score. The user requests a unified
eight-paint model and usable packages after the 1-16-paint runtime extension.
This is one fixed method application, not a parameter search or a default change.

## Data and split

Use the checksum-verified 286-row Old Holland archive, preserving its eight
column identities and normalized recorded tube-paint mass portions. Work on all
31 measured bands, 400-700 nm at 10 nm, without extrapolation or resampling.
The 8 pure and 95 binary rows (103 total) calibrate both stages. All 183 rows
with 3-7 ingredients remain outside fitting. All 28 pairs have calibration data.
There is no measured eight-ingredient mixture; eight-way predictions therefore
have no direct assessment here. This is same-source exploratory evidence; prior
Old Holland outcomes informed the method. It is not independent validation.

## One fixed fit

Generalize the existing base-then-pair method by dimension only. Fix eight K/S
curves to measured pures and white scattering to one. Fit 7*31=217 log-relative
scattering parameters on the complete pure/binary pool. Keep the original three
starts, log-S bounds, stopping criteria, mean spectral squared residual,
curvature weight and amplitude prior. Normalize priors by their new parameter
counts, as the original method does for its four-paint count.

Freeze this base. Fit four Bernstein wavelength controls per pair (112 total)
in reflectance-logit space using 4*c_i*c_j activation. Keep the original zero
start, [-0.8,0.8] bounds, mean-error residual, 1e-4 mean-square control prior and
stopping rules. No attenuation, sample deletion, new terms or target tuning.
One optical identity per paint is shared across all recipes; do not stitch the
previous independently fitted four-paint palettes together.

## Checks before interpretation

- Confirm hashes, eight pure endpoints, all pairs, exact split and normalized
  recipes. Check the generalized residual/Jacobian on synthetic inputs and
  numerical agreement with the original four-paint implementation.
- Freeze coefficients before assessment. Refit after perturbing every excluded
  measurement and require unchanged base and pair coefficients.
- Check convergence, bounds, independent scalar decoding, pure invariance,
  finite bounded spectra and random recipes with all eight ingredients.
- Report all 183 target rows, ingredient-count and white/no-white groups, mean,
  median, p95/max spectral RMSE and established windowed D65/2-degree DE00.
- On the original 35-target cohort, compare unified results with the archived
  palette-specific models. The calibration data and shared parameter structure
  differ, so this is a product/model-consolidation tradeoff, not equal-budget
  proof of an improved algorithm.

## Packaging and renderer proof

Export both plain K-M and the empirical candidate as separately identified local
experimental optical packages. Extend the runtime format to explicitly preserve
31-band support, windowed CIE/D65 display projection, model kind and pair controls.
Do not pad missing spectra to the current 81-band format or discard corrections.
Existing OPP1/OPP2 and OPR1/OPR2 identities must remain compatible.

Display uses the existing neutral-normalized RGB projection convention applied
only to this measured window, then the existing gamut map. This is a windowed
preview, not full-visible colorimetry or a relighting model. Evaluation DE00 stays
on the unchanged unclipped windowed XYZ/Lab convention, separate from display.

Independently decode exported packages through Rust and compare every measured
recipe and deterministic dense recipes with Python, including serialization
identity and subsequent mixing. Load the actual eight-paint package in the native
renderer, render explicit recipes and matched targets, save/reload and require
identical canvas planes. Show a swatch/painting preview and record hashes.

Raw measurements, fitted coefficients, runtime packages and measured swatches
remain under ignored target/ as in the established local research arrangement.
Commit original implementation, provenance and numerical reports; do not publish
packages, contact authors, alter the synthetic palette or change defaults. Do
not require a new permission exchange for the authorized local fit/package work.
Failures and limitations must be reported even if the package is usable.
