# Old Holland four-paint reference: frozen first experiment

Declared 2026-09-30 before fitting or inspecting holdout predictions. The user
requested the existing 21 fitting samples and 24 held-out mixtures. This is an
offline research fit, not a runtime/default change. Reuse terms for the separate
data archive remain unresolved; raw spectra, recipes, fitted coefficients and
measurement-based swatches stay under ignored `target/measured-oils`.

## Data and partition

Use the exact archive hashes in [starter-palettes.md](starter-palettes.md), source
columns 1, 3, 5, 8: Scheveningen Yellow Lemon, Scarlet Lake extra, Cobalt Blue,
Mixed White. Keep only rows with all other amounts zero. Normalize the recorded
paint masses; these are tube-paint proportions, not pure-pigment or volume amounts.

Four singles and 17 chromatic/white tints are the 21 fitting rows. The other
eight chromatic pairs, 13 triples and three four-paint mixtures are the 24 holdout
rows. Record one-based source row IDs and partition checksums before fitting.
The fit function receives only the 21 fitting arrays; evaluation is a separate
command that loads a previously frozen coefficient file. No holdout-driven model,
regularization, initialization or stopping-rule selection is permitted.

## Optical model and identification

Assume a homogeneous, optically thick Kubelka–Munk layer. No surface correction,
substrate, thickness, fluorescence, gloss or wet/dry conversion is fitted. The
source measured dried samples on oil paper with specular excluded; optical
thickness and absence of substrate effects are assumptions, not measured facts.

At each of the **31 measured wavelengths**, compute each pure paint's ratio
`q_j = K_j/S_j = (1-R_j)^2/(2 R_j)`. These four measured pure spectra impose hard
constraints; they are not separately adjustable parameters. Set `S_white=1` at
each wavelength to fix the unidentifiable common scale, and fit the other three
relative scattering curves as `S_j=exp(u_j)`; then `K_j=q_j*S_j`.

This wavelength-wise gauge preserves opaque-mixture predictions. It does not
identify absolute optical coefficients or make white's physical scattering
wavelength-independent. Parameters are effective mass-based mixing coefficients.

For mass proportions c, predict
`q_mix=sum(c_j K_j)/sum(c_j S_j)` and
`R_mix=1/(1+q_mix+sqrt(q_mix^2+2*q_mix))`.

Objective: mean squared reflectance residual across all 21×31 fitting values
(the four pure residuals are zero), plus `1e-4 * mean(second_difference(u)^2)`
over adjacent 10 nm samples and `1e-8 * mean(u^2)`. The small second term regularizes
underconstrained scattering values toward unity. There are 93 fitted parameters.
Bounds are `S_j` in [1e-4,1e4]. Use an analytic Jacobian and SciPy TRF with
ftol=xtol=gtol=1e-10 and at most 2,000 function evaluations per start. Run three
fixed starts: all chromatic S=1, 0.1, 10. Select the lowest **fitting objective**
among converged runs, with stable start-order ties. Preserve all solver outcomes.
Exact settings are [config/measured-oils-v1.json](../config/measured-oils-v1.json).

Also freeze an unfitted `S=1` baseline using the same four pure ratios. Evaluate
both models on the holdout after freezing; the baseline is a diagnostic, not a
candidate selected with holdout scores. No physical accuracy claim is inferred
from fitting the four pure colors exactly.

## Evaluation declared in advance

- Spectral RMSE, MAE, maximum band error per sample, and signed wavelength bias.
- CIEDE2000 from **unclipped** XYZ/Lab, CIE 1931 2-degree / D65, trapezoidal 400–700
  nm at 10 nm. Normalize by the integral of D65*ybar over this interval and use
  the corresponding truncated perfect-diffuser XYZ as the Lab white. This is
  explicitly a truncated colorimetric comparison, not full-visible D65 accuracy.
- No invented tails at 380–390 or 710–780 nm; no interpolation to 81 bands.
  sRGB/gamut mapping is used only for a local visual report, not error scoring.
- Report count, mean, median, p95 and maximum by fit/holdout and mixture family,
  the five worst rows, baseline change and bounds/optimizer diagnostics.
- A predeclared engineering screen for advancing this candidate: holdout mean
  spectral RMSE <=0.02, p95 <=0.05, mean CIEDE2000 <=3, p95 <=6 and max <=10.
  These are project screening choices, not universal perceptual thresholds or
  estimates of instrument uncertainty. Failure is retained, not tuned away.

Test the implementation before evaluation with synthetic known optics: exact
pure reconstruction, analytic-versus-finite-difference Jacobian, recovery from
noiseless tints, amplitude/gauge invariance, checked input/partition behavior,
independent scalar K-M predictions and color-difference reference cases.
No repeat measurements or noise model are provided, so do not attach confidence
intervals or pretend sparse mixture ratios establish all-ratio accuracy.
