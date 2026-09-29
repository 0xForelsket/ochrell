# Mathematical revision: decisions and evaluation contract

The v0.1.0 release and its comparison datasets are the frozen baseline. This revision may change the model; no Mixbox or Spectral.js implementation, spectra, coefficients, or outputs will be used as fitting targets. External outputs remain observational comparators only.

Goals declared before model selection:
- improve the dark blue/yellow, cyan/magenta and red/white diagnostic failures;
- preserve exact source endpoints and nonnegative physical quantities;
- eliminate or reduce inverse-recipe discontinuities and steep local trajectories;
- test broad perturbed color families and independent random RGB inputs;
- measure residual size, gamut interventions, tint luminance behavior, precision and throughput;
- retain negative findings and make the old model available for comparison.

Candidate families: (1) retain the finite pigment palette and improve its independently colorimetric fitting/inversion; (2) reconstruct spectra with a smooth independently generated basis and normalize per-material optical strength; (3) reconstruct spectra and impose bounded per-wavelength absorption/scattering priors. None is claimed to identify actual paints from RGB.

## Selected architecture

Fit three bounded, logit-smoothed reflectance primaries to CIE-projected RGB anchors, derive complements, and use an explicit continuous linear-RGB simplex recipe. Assign K and S through the β=0.5 geometric-mean optical prior, with neutral-white strength 2. This removes the nonlinear inverse and its encoder LUT. Select 10 nm for the fast path after measuring 20/40 nm mixture outliers.

## Retained negative findings

- Constant S with the fitted low-reflectance black gave an almost black half black/white mix (see `first_candidates.json`). An isolated spectrum does not identify optical strength.
- A per-band K+S budget (β=1) gave grayish yellow/blue mixtures. It was rejected as the default.
- Refitting the eight physical-palette spectra alone still gave cyan/teal blue/yellow and a black/white midpoint [35,35,35]. These outputs remain in `refitted_palette.json`.
- Larger logit smoothing sacrifices saturated-anchor reconstruction. All tested settings remain in `basis_sweep.csv`.
- The selected β=0.5 is a compromise. β=0.25 gives more green-dominant family results; β=0.5 better preserves tint hue. No real-paint optimum is asserted.
- New red/blue is less saturated than the legacy dark purple; hue direction alone does not prove an improvement in artistic preference.
- A fixed arbitrary bound of 2 ΔEOK100 per 0.001 step failed at pure black. Endpoint refinement confirms continuity; the OKLab cube root makes the metric highly sensitive there. The revised tests separate continuity, finite bounded output and tint-luminance monotonicity. The large measured endpoint step is explicitly reported.
- New latents are substantially larger and uncached full RGB mixing is slower than the legacy LUT. Caching still provides millions of samples per second on the measured host.
