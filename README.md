# Ochrell 0.2

**Open-source pigment mixing for digital painting.**

An independent Rust library for RGB-in, pigment-like mixing, RGB-out. It uses smooth spectral reconstruction and Kubelka–Munk absorption/scattering, with no proprietary Mixbox implementation data and no Spectral.js coefficients.

**Research release:** mathematically improved, reproducible and suitable for integration experiments; not calibrated to a specific real paint. Version 0.2 improves the earlier blue/yellow, cyan/magenta and white-tint failures. The full evaluation, tradeoffs and negative findings are in the [revision report](docs/revision-report.md) and [paper](paper/paper.md).

Previously distributed as `pigment-mix`. Update the dependency name and Rust imports to `ochrell`; the mixing API and numerical model are unchanged by this rename. Frozen experiment logs, external comparison captures, and archived papers retain their original names for provenance.

## Product direction

The next direction is [palette-based painting](docs/product-direction.md): choose
virtual paints, load or generate an accelerated mixer, and paint with persistent
recipes through code or a host application's UI. Agents can specify paint
proportions directly or ask the library to match a target color within the palette.
An experimental [Synthetic Four reference](docs/palette-reference.md) now supports
named paints, persistent recipes and checked save/load. An opt-in
[prepared forward LUT](docs/palette-lut.md) accelerates recipe decoding, with
measured generation time and approximation errors. Target-color matching and
renderer integration remain planned. The current
spectral mode remains supported and the library default is unchanged. A future
painting-app default would use a bundled prepared palette only after quality,
performance and saved-state compatibility are verified.

The selected [starter research palettes](docs/starter-palettes.md) are a
four-tube Old Holland oil subset and an independent synthetic baseline. The
measured candidate still needs data-rights clarification and model validation.

Try the opt-in reference with `cargo run --release --offline --example palette`.
Its materials are independently synthetic, with no claim of real-paint calibration.

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

For memory-sensitive storage, the opt-in `ochrell::compact::CompactLatent`
retains 24 nonuniform K/S samples and a residual in **204 bytes**, compared
with the default's 340 bytes. It supports persistent mixing and checked byte
serialization. This is lossy, model-specific compression; its measured errors,
slower decode cost, API example and reproduction commands are in
[optimization round 2](docs/optimization-round2.md). The default model and
existing renderer state format are unchanged.

## What changed

The unreleased [first optimization round](docs/optimization-round1.md) separates
independent optical calculations from RGB accumulation. It preserves the v0.2
model and recorded output bits while improving core CPU throughput in alternating
local benchmarks. Raw candidates, rejection and reproduction commands are kept
separate from the frozen v0.2 paper and integration measurements.

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
| `src/compact.rs` | Opt-in compact material storage, interpolation and serialization |
| `src/palette.rs` | Opt-in Synthetic Four recipe API and direct spectral reference |
| `src/palette_lut.rs` | Explicit forward LUT preparation, decoding and checked artifacts |
| `src/palette_match.rs`, `src/palette_package.rs` | Bounded target matching and custom optical palette packages |
| `tools/generate_palette.py`, `tools/check_palette.py` | Independent palette generation, numerical verification and swatches |
| `tools/optical_model.py` | Independent coefficient generation and Python reference |
| `docs/research.md`, `docs/math.md` | Literature, equations, assumptions |
| `docs/architecture.md`, `docs/coefficients.md` | API design and parameter provenance |
| `docs/revision-report.md`, `docs/benchmarks.md` | Measured improvements and tradeoffs |
| `docs/revision-decisions.md` | Candidate selection and failed approaches |
| `docs/product-direction.md` | Agreed palette workflow, code-driven painting, compatibility and delivery plan |
| `docs/starter-palettes.md` | Selected starter palettes, dataset audit and first reference experiment |
| `docs/palette-reference.md` | Experimental recipe API, synthetic definitions, persistence and measured checks |
| `docs/palette-lut.md` | Forward decoder selection, accuracy, preparation cost and timings |
| `docs/palette-workflow.md` | Target matching, custom palette loading, package format and validation |
| `docs/measured-oils-results.md` | First Old Holland fit and held-out evaluation, reuse audit and limitations |
| `docs/measured-oils-revision-results.md` | Training-only diagnosis and a rejected constrained revision; exploratory comparison |
| `docs/measured-oils-v3-results.md` | Chromatic-pair calibration and whole-family exclusion; conditioning versus prediction |
| `experiments/oil_parallel/REPORT.md` | Three independent agents compare finite layers, color-aware fitting and empirical spectral interactions |
| `experiments/oil_grouped/REPORT.md` | Grouped recipe validation withholding each chromatic ratio and all its white additions |
| `experiments/oil_red_blue/REPORT.md` | Frozen-model red/blue correction diagnosis and calibration-coverage sensitivity |
| `experiments/oil_public_data/REPORT.md` | Public measurement source audit and source-consistency checks |
| `experiments/oil_external/REPORT.md` | Original header-paired external test; superseded for accuracy interpretation by the inferred-mapping study |
| `experiments/oil_source_recovery/REPORT.md` | Frozen inferred 175-sample mapping, near reproduction of published baselines and quantified label ambiguity |
| `experiments/oil_white_split/REPORT.md` | Frozen pair-component diagnosis: binary corrections fail to transfer into three chromatic pigments |
| `experiments/oil_reconstructed/REPORT.md` | Unchanged model evaluation under inferred labels: robust spectral gains, white-mixture dependence and mapping sensitivity |
| `experiments/oil_source_trace/REPORT.md` | Initial seven-model source audit and bounded ordering checks, preceding the inferred reconstruction |
| `data/README.md` | Dataset/license attribution and checksums |
| `results/revision/` | Raw current results, environment, fit and ablations |
| `paper/paper.md`, `.tex`, `.pdf` | Revised scientific paper |
| `paper/figures`, `paper/tables`, `paper/supplementary.md` | Reproducible evidence |
| `paper/legacy`, `docs/legacy` | Previous version's findings |

## Scope and licensing

The model is a synthetic optical prior. It cannot identify an actual paint from RGB. White strength is not measured titanium white. Some mixtures remain muted, and perceptual speed near black can be steep despite continuity. Thickness, glazing, granulation, gloss, fluorescence, transport and drying are not implemented. No human preference or measured paint validation is claimed.

The core has no OS dependency, unsafe code or external crate dependencies. A
renderer-owned native bridge now exercises it from Python. SIMD/GPU, browser
execution measurements and production deployment of compact storage remain future work.
A WASM compile check is configured in CI.

Original code: **MIT OR Apache-2.0**. Attributed CIE data and derived numerical assets: **CC BY-SA 4.0**. This is a mixed-license open-source distribution; see `data/README.md`, `docs/coefficients.md` and retained third-party notices. No proprietary mixing artifact is required by the engine.
