# One constrained revision after calibration diagnosis

Baseline: commit `e109f3f`, frozen v1 model SHA-256
`11f40f621328b52b158326e849ce3f40823941dbbbc04e75ea724dd0bbdb0175`.
Declared 2026-09-30 after the training-only diagnosis and before any v2 fit.

## Diagnosis and scope

The 21 calibration samples comprise four singles and 17 white tints. Holding
their pure spectra fixed, a separate scalar search fitted scattering at each
wavelength without regularization. It used 513 equally spaced log-S probes,
refined every sampled local minimum, included both bounds and the original v1
solution, and retained the smallest spectral loss. This is a bounded numerical
diagnostic, not a proof of a global optimum for all possible input data.

Removing smoothing and the weak amplitude prior reduced calibration squared
spectral error by only **0.00258%**. The existing smoothing therefore explains
essentially none of the observed calibration error. Five adjacent tint-sequence
comparisons reverse the expected per-band monotonic direction by more than 0.001
reflectance (two yellow, one red, two blue). Three tints exceed their measured
pure-ingredient envelopes. These diagnostics do not estimate measurement noise
or establish the physical cause. The unsmoothed curves are not tested on the 24
exposed mixtures and are not an additional candidate selected on those results.

Test exactly one revision: softly anchored pure-paint spectra. Preserve positive,
homogeneous, infinitely thick K-M, normalized recorded tube-paint mass, all 21
calibration rows, and the 31 measured 400–700 nm bands. No surface/substrate/
thickness or per-mixture correction is added. No measured row is removed or
downweighted after inspecting its error. This revision cannot generally cure
nonmonotonic tint sequences; its purpose is to test sensitivity to exact pure
anchors, not to explain away every discrepancy.

## Constrained pure-spectrum adjustment

For each paint use `R'_j(lambda)=R_measured_j(lambda)+B(lambda)*a_j`.
B is a five-control clamped cubic B-spline basis, knots
`[400,400,400,400,550,700,700,700,700]`. Its nonnegative weights sum to one.
Twenty controls replace 124 independent per-band adjustments, limiting freedom
to smooth, broad corrections.

Each control is bounded to at most +/-0.02 absolute reflectance, tightened per
paint so every corrected band remains in [0.0001,0.9999]. Because B is a convex
combination, these bounds also bound every wavelength's change. This 2 percentage
point cap is an engineering experiment constraint, not measured uncertainty.

Infer q from each corrected pure spectrum; jointly fit three log-S curves
(93 parameters) and the 20 pure controls. White S=1 remains a per-wavelength gauge.
Total free parameters: 113, versus v1's 93.

The objective is the same mean squared reflectance residual over all 21x31
calibration observations, plus v1's `1e-4*mean(D2(log S)^2)` and
`1e-8*mean((log S)^2)`, plus **`mean((B*a)^2)`** as an additional pure-anchor
penalty. Pure observations remain in the data residual too: their aggregate
effective weight is 6.25 times that of an equal number of ordinary calibration
observations. There is no per-band noise weighting.

Use analytic derivatives, SciPy TRF, the same three starts S=1,0.1,10 with all
pure shifts initially zero, and the same tolerances (1e-10) and maximum 2,000
evaluations per start. Variable scales are 1 for log-S and 0.02 for controls.
Choose the lowest converged **calibration objective only**. Settings are fixed
in [the v2 configuration](../config/measured-oils-v2.json). Preserve all starts,
boundary counts, pure shifts, solver outputs and the frozen coefficient hash.

## Evaluation and claims

Before fitting real data, verify the analytic Jacobian, the zero-shift reduction
to v1, spline bound guarantees and recovery on synthetic calibration data. After
fitting, verify the frozen parameters with independent scalar K-M evaluation.

Report pure colors and the 17 tints separately, including maximum pure DE00 and
per-paint wavelength shifts/boundary hits. A predeclared pure-color screen is
maximum DE00 <=1.0; this is evaluated after fitting and is not a constrained
optimizer condition. Report any failure rather than changing its budget.

Then evaluate exactly once on the **24 previously exposed mixtures**, using the
same truncated D65/2-degree colorimetry and spectral metrics. Compare against v1
per row, family, mean, median, p95 and maximum. Report improved/worsened cases and
all five original quality-screen thresholds unchanged. These comparisons are
**exploratory development evidence**, never a new independent holdout success.
No retuning follows this comparison in the current experiment.

If the revision helps, stronger validation still requires fresh independent
mixtures or measurements. If it fails or trades mixture fidelity for pure-color
drift, retain that result. This experiment makes no runtime, paper or default
change. The source archive and coefficient files stay in local research output
as an artifact-management choice; no legal permission requirement is asserted.
