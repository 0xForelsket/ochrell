# Frozen diagnosis of source rows 205, 197 and 199

Declared 2026-10-01 after the 35-row assessment. The user approved diagnosing
row 205's correction-induced regression separately from rows 197/199's large
K-M errors. These are exposed cases selected for their failures, not a new test.

Use the exact frozen 25-palette bundle from `oil_ternary_transfer`, SHA-256
`ddc0e552df366ed4c0e00bdfeb581ca03f48f3ab1f71501808bc2ec778b94fbb`.
Retain source row identities, concentrations, pure endpoints and fitted
coefficients. No fitting, relabeling, parameter search, hybrid coefficient model,
runtime change or model revision is part of this diagnosis.

1. Replay the three saved errors with independent scalar decoding. Check raw
   source rows using a second text-table reader and the original archive hashes.
   Inspect documented preparation/measurement metadata without inferring missing
   thickness, substrate spectra, batch identity or repeat measurements.
2. For row 205, decompose the six additive logit pair terms. Evaluate all subsets
   of active terms and exact Shapley allocations of spectral MSE change, plus
   pair-only/removal counterfactuals. Distinguish spectral error from windowed
   color error, and report wavelength contributions and direction/overshoot.
3. For rows 197/199, separate existing K-M residuals from the small added
   correction. Audit calibration ratios, same-ratio white additions, inferred
   relative scattering contributions and spectral regions. White additions are
   diagnostic observations only; do not turn them into new training data or an
   independently selected benchmark.
   As a follow-up algebraic diagnostic, use their common Scarlet:Viridian=3:1
   blend and calibration row 138 as an effective binary endpoint. Compare the
   two independently implied blend/yellow scattering ratios using both the
   observed and frozen-model blend endpoint; do not deploy the inferred ratios.
4. Test a model-independent necessary condition of this fixed-pure opaque K-M
   family: with positive scattering, reflectance must remain between the minimum
   and maximum constituent pure reflectances at every wavelength. Quantify any
   violation and its lower bound on attainable RMSE. This condition is specific
   to the assumed homogeneous opaque model; real finite films can differ.
5. Check binary calibration support and the per-wavelength scattering ratio
   algebraically implied by observed binaries. Report infeasible bands and
   disagreement with fitted ratios. The inferred ratios are diagnostic inversions,
   not replacement coefficients. Inspect the frozen model's data Jacobian to
   assess local sensitivity without fitting another model. If useful, compare
   predictions for a shared binary across already-frozen palettes; model
   disagreement is not measured uncertainty or evidence for choosing a fit.

Keep training errors, selected target errors and neighboring diagnostic samples
clearly separated. Preserve all source/dependency/model hashes. Verify scalar
parity, component recombination, MSE identities, attribution sums, and the
positive-scattering envelope. Dense source-derived spectra remain under ignored
target/; version derived tables, figures and the report. End with supported
findings and unresolved causes; do not propose a physical explanation as proven.
