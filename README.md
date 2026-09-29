# Ochrell 0.2

**Open-source pigment mixing for digital painting.**

An independent Rust library for RGB-in, pigment-like mixing, RGB-out. It uses smooth spectral reconstruction and Kubelka–Munk absorption/scattering, with no proprietary Mixbox implementation data and no Spectral.js coefficients.

**Research release:** mathematically improved, reproducible and suitable for integration experiments; not calibrated to a specific real paint. Version 0.2 improves the earlier blue/yellow, cyan/magenta and white-tint failures. The full evaluation, tradeoffs and negative findings are in the [revision report](docs/revision-report.md) and [paper](paper/paper.md).

Previously distributed as `pigment-mix`. Update the dependency name and Rust imports to `ochrell`; the mixing API and numerical model are unchanged by this rename. Frozen experiment logs, external comparison captures, and archived papers retain their original names for provenance.

## Use

Rust 1.75 or later; no runtime dependencies.

```toml
[dependencies]
ochrell = { path = "../ochrell" }
```

```rust
use ochrell::{Color, PigmentMixer, mix};
let yellow = Color::srgb8(255, 220, 0);
let blue = Color::srgb8(20, 70, 255);
let green = mix(yellow, blue, 0.5);
assert_eq!(green.to_srgb8(), [101, 152, 94]);

let mixer = PigmentMixer::default();
let tint = mixer.mix_weighted(&[
    (yellow, 0.25), (blue, 0.25),
    (Color::srgb8(255, 255, 255), 0.50),
]).unwrap();

// Cache optical states to avoid encoding the same brush colors repeatedly.
let a = mixer.encode(yellow);
let b = mixer.encode(blue);
let sample = mixer.decode(a.interpolate(b, 0.5));
```

`Color::srgb` checks finite unit-range channels. Pair mixing clamps t, treats NaN as zero and returns the supplied endpoints exactly; `try_mix` rejects invalid t. Weighted APIs reject empty, all-zero, negative or nonfinite weights. `Latent::weighted` mixes preserved optical states. Colors have no alpha. The host owns compositing and profile conversion.

Preserving K/S states retains the inferred material; an RGB decode/re-encode round trip loses it. Grouped latent mixtures agree when outer weights carry group amounts. RGB-only repeated mixing is not generally associative.

## What changed

The new default replaces nonlinear palette inversion and the 33³ encoder LUT with an explicit continuous spectral reconstruction. Three independently fitted primary spectra generate complementary anchors; a declared optical-strength prior controls absorption/scattering and white behavior. The reference uses 81 bands/f64; the default uses 41 bands/f32 optics. Both use stack arrays. Default construction has no table parse.

On the recorded host, complete mixing reaches about 1.4 million operations/s and cached mixing about 4.4 million/s. The new default is slower than the legacy LUT, and its latent is larger (340 versus 44 bytes). See [measured benchmarks](docs/benchmarks.md) rather than treating these figures as cross-platform guarantees.

The old implementation remains available under `ochrell::legacy`. Root mixer/latent exports now refer to v0.2. Users of `with_lut`, `lut`, `encode_trilinear` or `concentrations` should explicitly import the legacy mixer. The old paper and docs are archived under `paper/legacy` and `docs/legacy`.

## Reproduce

```bash
cargo test --release --offline
cargo run --release --example basic
cargo bench --bench mixing

python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python3 tools/reproduce.py
```

The last command fits the basis, compiles/tests Rust, runs 10,000 reconstruction and 10,000 mixture samples, canonical/random/tint trajectories, independent holdout probes, ablations and timings, then regenerates figures, tables and manuscript. PDF generation additionally requires Pandoc and TeX. `CARGO` may identify a custom toolchain wrapper. The Python packages must be installed before offline Rust execution. `tools/reproduce_legacy.py` preserves the previous study.

Edit **`config.toml`** to change model/experiment settings; rerun generation and recompile after model changes. The optimized Rust kernel supports the documented β=0.5 prior. Unsupported reproduction configurations fail explicitly. The Python model supports the broader ablation family. No pigment measurements or network access are needed for model generation.

Frozen Mixbox/Spectral.js comparison outputs and acquisition metadata are included under `comparisons/external-baseline`; new comparisons are under `results/revision/external`. They are observations after model selection, not fitting targets. Reacquiring a changing web demo is intentionally separate from the reproducible default workflow.

## Project map

The existing oil-paint renderer now has a native integration through a local
path dependency, with persistent optical state, separate paint amount and
coverage, exact saved states, and matched brush comparisons. See
[integration and measured results](docs/integration.md) and the
[implementation plan](docs/integration-plan.md). The renderer is separate;
the Rust library still builds and runs without Python or renderer code.

| Path | Contents |
|---|---|
| `src/optical.rs` | Default continuous spectral model, fast and reference kernels |
| `tools/optical_model.py` | Independent coefficient generation and Python reference |
| `docs/research.md`, `docs/math.md` | Literature, equations, assumptions |
| `docs/architecture.md`, `docs/coefficients.md` | API design and parameter provenance |
| `docs/revision-report.md`, `docs/benchmarks.md` | Measured improvements and tradeoffs |
| `docs/revision-decisions.md` | Candidate selection and failed approaches |
| `data/README.md` | Dataset/license attribution and checksums |
| `results/revision/` | Raw current results, environment, fit and ablations |
| `paper/paper.md`, `.tex`, `.pdf` | Revised scientific paper |
| `paper/figures`, `paper/tables`, `paper/supplementary.md` | Reproducible evidence |
| `paper/legacy`, `docs/legacy` | Previous version's findings |

## Scope and licensing

The model is a synthetic optical prior. It cannot identify an actual paint from RGB. White strength is not measured titanium white. Some mixtures remain muted, and perceptual speed near black can be steep despite continuity. Thickness, glazing, granulation, gloss, fluorescence, transport and drying are not implemented. No human preference or measured paint validation is claimed.

The core has no OS dependency, unsafe code or external crate dependencies. A
renderer-owned native bridge now exercises it from Python. SIMD/GPU, browser
execution measurements and production state compression remain future work.
A WASM compile check is configured in CI.

Original code: **MIT OR Apache-2.0**. Attributed CIE data and derived numerical assets: **CC BY-SA 4.0**. This is a mixed-license open-source distribution; see `data/README.md`, `docs/coefficients.md` and retained third-party notices. No proprietary mixing artifact is required by the engine.
