# Supplementary material and reproducibility index

The complete source, raw CSV files and figure scripts accompany this paper. The study evaluates a synthetic model; there is no measured-paint ground-truth dataset or human-subject study.

## All recorded files

* `results/exploration/initial_midpoints.csv`: first A/B/C comparison, before edge adjustment.
* `results/exploration/initial_reconstruction.json`: initial palette-size trial.
* `results/exploration/failed_530_530_midpoints.csv`: rejected synthetic basis trial.
* `results/exploration/edge_sweep.csv`: 12 synthetic blue/yellow edge combinations.
* `results/exploration/midpoints.csv` and `reconstruction.json`: selected exploratory model, independent Python SLSQP inversion.
* `results/reconstruction/samples.csv`: seeded Rust input colors, f64 reference recipes, uncorrected linear RGB, corrected source reconstructions and fast uncorrected values.
* `results/reconstruction/*_errors.csv`: all per-sample CIEDE2000 and ΔEOK100 values.
* `results/reconstruction/worst.csv`: 20 worst uncorrected reconstructions, selected by error, not appearance.
* `results/mixing/random_pairs.csv`: random endpoints, t, reference and each LUT/interpolation result, and raw fast linear RGB.
* `results/mixing/gradients.csv`: every sample of twelve canonical pairs, six methods, with t, display RGB, raw RGB and latent concentrations. Modes: 0 encoded sRGB, 1 linear RGB, 2 OKLab, 3 fast hybrid, 4 reference hybrid, 5 fast without residual.
* `results/mixing/worst_lut.csv`: the largest default-LUT discrepancies.
* `results/mixing/random_smoothness.csv`: dense random-trajectory summaries.
* `results/reconstruction/precision.csv`: independent f32 precision output at recorded recipes.
* `results/ablations/solver.csv`: direct optimizer objective versus independent SLSQP on 128 shared inputs.
* `results/performance/raw.csv`: all repetition times; modes documented in `tools/analyze.py`.
* `results/performance/generation.json`: table sizes and wall-clock generation durations.
* `results/ablations/*.csv`: common 128-color sample set and palette/scattering ablations, using the independent SLSQP solver.
* `results/summary.json`: generated descriptive statistics; `paper/tables` contains selected machine-readable tables.
* `results/environment.json`: CPU, compiler, release configuration and configuration checksum.

## Interpreting the ablations

The palette subset study uses the same input samples and Python optimizer throughout. It is not silently substituted for the Rust runtime benchmark. The spectral-resolution study holds the recorded Rust concentrations fixed; thus it isolates forward-model sampling from changes in inversion. LUT comparisons use the same random pairs and reference direct inversion, but retain the fixed 20 nm fast decoder, so they include the remaining decoder approximation. Reconstruction with the residual turned on is expected to be near floating-point precision and should never be read as validation against real paint.

## Reproduction commands

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python3 tools/reproduce.py
cargo test --release
cargo bench --bench mixing
cargo run --release --example basic
```

Optional PDF prerequisites: Pandoc and a TeX installation with `pdflatex`, `amsmath`, `graphicx`, `booktabs`, `geometry`, `hyperref`, `longtable`, and `xcolor`. The script creates Markdown and TeX before attempting PDF output. The source code builds offline with Cargo and has no crates.io dependencies. Model generation needs the pinned Python packages; the distributed runtime library does not.

## Derivative and identifiability notes

The separate scattering strengths cannot be recovered from opaque reflectance alone. Multiplying both K and S for a pigment by a positive scalar leaves its isolated opaque color unchanged but changes its influence in mixtures. Consequently a basis made from measured opaque reflectances would still require either mixture calibration or an explicit scattering convention. This study chooses the latter and labels it a prior.

For q>0, differentiating the rationalized K–M expression gives dR/dq=−R/sqrt(q(q+2)). Concentration derivatives follow the quotient rule, dq/dc_i=(K_i−qS_i)/S. The chosen finite reflectance bounds keep q away from zero and infinity within the basis simplex. Endpoint derivative behavior in an unbounded measured model would need additional treatment.

## Deferred investigations

No neural inverse, polynomial decoder, SIMD intrinsics, GPU shader, finite layer, real pigment fit, or brush simulation was implemented. They were not failed experimental approaches. They remain untested proposals and must not be reported as negative findings. The negative findings actually observed are the initial constant-S black-white behavior, palette-gamut errors, the 530/530 nm red-blue failure, and the constrained-Newton solver failure documented in the decision log.
