# Round 2: compact material state

Starting checkpoint: `9937ec4`. The default 340-byte f32 latent and the 81-band
f64 reference remain unchanged. All work is in Ochrell, with no renderer edits.

## Candidate families

- Store a fixed subset of wavelength samples of K and S as f32, reconstruct
  missing bands by positive piecewise-linear interpolation, and retain three
  f32 residual channels. Compare uniform and adaptively selected knots.
- Project K/S onto a smaller linear f32 basis learned from this model's own
  encoded RGB states. Measure negative reconstructed coefficients and the
  consequences of projection/clipping; do not hide them as a valid material.

No Mixbox or Spectral.js implementation, coefficient or output is used. No model
coefficients, physical paint claims or wavelength quadrature are changed. A
source-color residual adjustment is evaluated separately from optical shape:
excellent immediate RGB reconstruction does not prove good future mixing.

## Acceptance declared before candidate selection

The compact type will be opt-in, never a silent replacement for the full state.
Promote the smallest tested representation at most 256 bytes (prefer <=192) that:

- Preserves K >= 0 and S > 0 for supported material operations, without silently
  clamping invalid reconstructed optics. Nonnegative interpolation gives a
  structural positivity guarantee for the sampled-spectrum family.
- Has mean <=0.01, P95 <=0.05 and maximum <=0.20 delta E OKLab * 100 relative to
  the current full state for mixture, tint, black, multicolor and repeated cases.
- Has source reconstruction maximum <=0.002 delta E OKLab * 100, and its own
  grouped-weight error maximum <=0.002.
- Passes those future-mixing gates for 256 ordinary updates and 4096 tiny
  updates at t=0.0001, including full materialization/repacking after every
  update. Byte serialization/reload must preserve compact state exactly.
- Passes an independent seeded holdout, existing core tests, and an actual
  Rust implementation check after the NumPy screening. Failed candidates and
  unfavorable performance results are retained.

These are engineering error budgets against a computational model, not measured
paint accuracy or universal perceptual thresholds. Report error versus the
81-band reference separately. States imported from arbitrary spectra remain
valid full states; approximation-error bounds are empirical for the model's own
encoded colors/mixtures, not promises about arbitrary spectra.

Training: seed 20260930; selection: seed 314159; holdout: seed 1907. Include
continuous random colors, dark-biased colors, near-white colors, saturated cube
faces, the eight corners and a gray ramp. Canonical/control colors may recur;
the random holdout is independent and is not used to fit knots or bases.

Measure size, pack/unpack, compact mixing, complete decoding and coherent state
updates with the same source colors. Keep computation, storage and API tradeoffs
visible. If no candidate passes, retain the full state and report the rejection.
