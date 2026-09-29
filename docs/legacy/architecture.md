# Architecture and integration

## Two models, one generated palette

`ReferenceSpectralMixer`: direct deterministic constrained inversion, 81-band f64 K–M and colorimetric projection. This is a reference **for this synthetic mathematical model**, not ground truth for real pigments. `ReferenceLatent` preserves f64 concentrations and residuals.

`FastPigmentMixer` / `PigmentMixer`: an embedded 33³ encoder LUT, tetrahedral lookup, and 21-band f32 decoder. `Latent` stores eight weights and three linear-light residuals. The core has no external crates, unsafe code, file access, network access or per-call heap allocation. `Default` parses the embedded table once through `OnceLock`, then shares it using `Arc`. Initial construction allocates approximately 1.1 MiB. Retain a mixer in an application rather than repeatedly constructing defaults.

An RGB mix encodes both colors and decodes their blended latent. That evaluates the spectral decoder three times (two residual computations, one result). An already-encoded mix evaluates it once. Cache source paint latents in a brush; for a pigment-aware canvas, retain latent pixels and material amounts. Convert to RGB only for display. An RGB canvas cannot preserve metameric recipe identity across repeated operations.

## Module boundaries

| Module | Responsibility |
|---|---|
| color | Checked finite sRGB values, display output, explicit weight errors |
| conversion | sRGB transfer functions, OKLab, display gamut map |
| kubelka_munk | Stable opaque-layer equations |
| pigment | Names and deterministic concentration prior |
| spectrum | f64 reference and f32 fast optics; analytic Jacobian |
| latent | Latent state, interpolation, constrained inversion |
| lut | Validated binary loading, generation, tetrahedral/trilinear lookup |
| mixing | Public pair, checked pair, weighted and cached APIs |
| generated | Reproducibly generated palette and integration arrays |

`generate-lut` is a separate offline tool. `experiments` emits raw measurements. Python tools perform exploratory optimization, independent color differences, analysis and figure generation. Runtime Rust does not call Python.

## API contracts

* `Color::srgb8` and checked `Color::srgb` take ordinary, unassociated sRGB. No premultiplied channels, alpha, HDR, spectral input or color-profile conversion is inferred.
* `mix(a,b,t)` clamps finite t to [0,1], maps NaN to 0, and returns endpoints exactly. `try_mix` rejects nonfinite and out-of-range t instead.
* `mix_weighted` returns `Result`; negative, nonfinite, empty, or all-zero weights fail. It normalizes in f64 to avoid ordinary f32 weight-sum overflow.
* Latent internals are private, so callers cannot accidentally inject negative concentrations. Accessors expose copies for inspection. The raw spectral helper functions assume a valid nonnegative nonzero recipe and are intended for numerical work.
* Gamut mapping returns bounded display channels. Raw linear decode remains available for diagnostics. `from_linear_gamut_mapped` maps nonfinite input to black; use checked `Color::srgb` for untrusted color input.
* Table loading validates structure but does not authenticate palette identity. Load only tables generated for the compiled palette. The file format is versioned but no stable model interchange contract is promised at version 0.1.

## Portability and optimization

The core uses standard Rust arithmetic, fixed-size arrays, immutable data and `std` synchronization, with no OS dependencies. It is designed for wasm32-unknown-unknown, but this delivery's measurements are native x86_64. A CI build job covers WASM; no JavaScript, C ABI or graphics-engine bindings are implemented. Cross-target floating-point bit identity is not promised.

Twenty-one bands were selected as an explicit approximation and evaluated against 5 nm. No hand-written SIMD, GPU kernel, Rayon, neural approximator or polynomial decoder is claimed. They are future options after the scalar implementation. Outer-loop batching is trivially parallel for independent pixels, but thread startup and scheduling would distort a one-operation microbenchmark. Benchmarks therefore use one thread and no target-specific CPU flags.

## Reproduction and configuration

Run `python3 tools/reproduce.py` from a clone after installing `requirements.txt` and Rust >=1.75. Configuration resides in root `config.toml`, with comments and validation. Model edits require regenerating arrays/LUTs and rebuilding the crate; experiment settings apply at the next run. The script preserves user edits and uses standard `tomllib`, not an ad-hoc TOML parser. `CARGO` may override the cargo executable path. Artifacts are offline-reproducible from the bundled CIE subset; network downloads are not needed by Cargo.

The build is a research release, not evidence of production deployment. Its most important remaining quality risk is the chosen spectral/scattering prior and significant residual corrections, not arithmetic throughput alone.
