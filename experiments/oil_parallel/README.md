# Parallel oil-palette experiments

Completed 2026-09-30 from baseline commit `16de957`. Three GPT-6.1 Sol agents
independently investigated physical-model assumptions, fitting objectives, and
empirical mixture interactions. This is an exploratory research round.

Read the [combined report](REPORT.md) for the comparison, regressions and next
research recommendation. Each direction's report links its own method and
reproduction commands. With the saved local fit artifacts available, rerun the
independent coordinator checks and regenerate the figure from the repository root:

```powershell
& target/measured-oils/venv/Scripts/python.exe experiments/oil_parallel/validate_comparison.py
& target/measured-oils/venv/Scripts/python.exe experiments/oil_parallel/plot_comparison.py
```

## Shared comparison contract

- Preserve v1, v2 and v3, all existing source files and frozen artifacts. Each
  agent owns only its named subdirectory here and its matching directory under
  `target/measured-oils/parallel/`. Runtime, paper and renderer changes are out
  of scope. The coordinator owns this index, any combined report, manifests and
  Git operations.
- Use the existing checksum-verified source and the 31 measured 400–700 nm bands.
  Preserve paint identities, recorded mass fractions and row alignment. No
  invented spectral tails or undocumented clipping before color-error scoring.
- The standard comparison is the declared v3 protocol: 29 calibration rows
  (original 21 plus eight chromatic pairs), 16 three-/four-paint assessment rows,
  and three whole-pair-family-exclusion refits for the eight pairs. Reuse
  `tools/measured_oils_chromatic.py::design` where useful. V1 and v3 must be
  rescored on the identical assessment rows. An optional original 21/24 comparison
  must be labelled separately and must use the same predeclared candidate.
- All 24 non-calibration samples were previously exposed. Fold exclusion
  prevents direct fitting leakage, but every new result remains exploratory.
  No claim of new independent validation is allowed.
- Write assumptions, equations, parameter bounds, objective weights, fixed
  starts and stopping rules before real fitting. Choose at most one main model
  and one explicitly declared diagnostic ablation per direction. Select starts
  on training loss only. No unreported evaluation-driven retuning.
- Report spectral RMSE/MAE/tails, truncated-D65 CIEDE2000 mean/median/p95/max,
  pure-paint drift, per-family results and regressions, numerical validation,
  model complexity, training/runtime cost and limitations. Failed fits and
  regressions are results, not reasons to omit a case.
- Validate equations/derivatives on independent or synthetic cases and verify
  baseline scores before drawing conclusions. Keep raw measurements and fitted
  coefficient artifacts under ignored target output; publish original code,
  declared methodology and error reports here. This storage arrangement is not
  a claim that legal permission is necessarily required for the fitted model.

## Directions

| Directory | Question |
|---|---|
| `physical/` | Can a constrained physical model of finite opacity/backing or surface response explain discrepancies better? Unknown physical inputs must stay explicit assumptions. |
| `objective/` | Does uniform spectral least squares sacrifice the color accuracy needed for painting? Keep the optical model fixed and test a predeclared color-aware objective. |
| `interaction/` | Can a small, bounded empirical spectral interaction model predict mixtures better while retaining recipes and pure endpoints? Distinguish its empirical behavior from physical K/S or paper fidelity. |

The existing Python environment is `target/measured-oils/venv/Scripts/python.exe`.
The source archive is `target/measured-oils/source/spectralDatasets.zip` and the
frozen v1 coefficients are `target/measured-oils/v1/fitted-model.json`. Baseline
metrics and reusable numerical helpers are in `results/measured-oils-*` and
`tools/measured_oils*.py`. Limit BLAS/OpenMP threads to one for concurrent runs.
