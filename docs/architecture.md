# Architecture, v0.2

`PigmentMixer` / `FastPigmentMixer` now use a continuous reconstructed-spectrum model. The simple RGB API is unchanged; the latent representation is a breaking change appropriate to the 0.2 release. `ReferenceSpectralMixer` evaluates the same equations with 81 samples and f64, while the default evaluates 41 samples with f32 optical arithmetic. Neither default encoder uses an iterative inverse or 3D LUT.

## Modules

- `color` / `conversion`: checked bounded sRGB, transfer functions, OKLab and gamut mapping.
- `optical`: new reconstruction recipe, separate K/S inference, latent interpolation, pair and weighted APIs.
- `compact`: optional 204-byte, 24-knot approximation of full optical material,
  with persistent mixing, full-state expansion and versioned byte payloads.
- `optical_generated`: immutable independently fitted spectra and quadrature generated from `config.toml` and attributed CIE data.
- `legacy`: explicit re-exports of the frozen v0.1 finite-palette mixer and concentration latents.
- `pigment`, `latent`, `lut`, `spectrum`, `mixing`, `generated`: retained legacy implementation, used by the baseline reproduction and comparison experiments.

The naming of the older public modules is retained for source compatibility where possible. Root-level mixer and latent exports refer to v0.2. Applications using `with_lut`, `lut`, `encode_trilinear` or `concentrations` must import their mixer from `ochrell::legacy` to keep the old behavior. New latents expose absorption, scattering and residual. They deliberately have no public constructor that could inject negative coefficients.

## Runtime contracts

`mix(a,b,t)` returns exact a/b at the endpoints, clamps t, and interprets NaN as zero. `try_mix` rejects nonfinite and out-of-range t. `mix_weighted` accepts nonnegative finite f32 weights, normalizes their f64 sum, and rejects empty/all-zero input. `Latent::weighted` performs the same operation on preserved optical states. No heap allocation occurs in the new pair/weighted kernels. The mixer is a zero-sized stateless Copy type; there is no lazy table parse or runtime model-generation startup. The legacy mixer still owns a shared LUT.

A `Color` is unassociated encoded sRGB with no alpha. Hosts handle profiles, alpha compositing and storage. Store latents when repeated mixing should retain the inferred material state. A decoded RGB color does not identify its previous spectrum. Keep group mass separately if composing weighted batches.

## Build and reproduction

`tools/optical_model.py` fits three colorimetric anchors, derives complements and writes `data/optical_basis.csv` plus `src/optical_generated.rs`. It records optimizer convergence and a basis checksum. Runtime Rust has no dependencies; Python/SciPy is an offline authoring dependency. The fixed root TOML is the source of model and experiment settings. Rust's optimized kernel explicitly supports β=0.5; unsupported configuration is rejected, never silently ignored.

`tools/reproduce.py` regenerates the v0.2 experiment and manuscript suite. `tools/reproduce_legacy.py` is the preserved v0.1 workflow. Frozen comparator outputs are observational only; external engine code is not required to build or run the crate. Versioned old papers and docs remain under `paper/legacy` and `docs/legacy`.

## Performance and integration

The unreleased kernel separates per-band optical evaluation from the ordered RGB
projection, allowing compiler auto-vectorization of independent bands while
retaining the original reduction order. See `optimization-round1.md` for exact
output checks, CPU measurements and retained losing candidates. This does not
change the latent layout, numerical model or reference wavelength grid.

Caching saves two spectral encodes per operation. A fast latent occupies 340 bytes; its memory cost may be unsuitable for every canvas pixel. Tile-level caches, brush-color caches or opt-in compact storage can be more appropriate. The original 44-byte legacy state remains available, with different numerical behavior.

`Latent::try_from_parts` and its reference counterpart now validate imported
K/S/residual arrays for storage and bindings (finite values, K >= 0, S > 0).
The host must also check model version and wavelength grid. These are not
measured-paint validation or a promise of Rust struct layout. Existing accessors
export components without quantization.

The sibling renderer owns a small C ABI bridge; the core still has no unsafe
code or ABI dependency. See `integration.md` for measured native brush workloads.
No explicit SIMD, parallelism, JS binding or GPU kernel is claimed. Fixed arrays,
read-only coefficients and no OS calls in the optical kernel provide a path to
WASM/SIMD. Existing WASM CI remains a compile check; browser execution was not
measured here.

## Optional compact storage

`compact::CompactLatent` is a separate type; root `Latent` remains 340 bytes.
Its 24 K/S knots are sampled from the full state, and missing wavelengths use
nonnegative linear interpolation. A one-time residual adjustment during packing
preserves immediate linear RGB. The residual cannot restore discarded optical
shape, so future mixtures can differ. Selection used only this model's own
synthetic states; see `optimization-round2.md` for holdout errors and failures.

The compact type maintains f32 optical state through interpolation and weighted
mixing. It has no alpha, thickness, amount or renderer dependency. `to_full`
expands the approximation, not the original state. Its checked little-endian
payload contains K, S and residual arrays (204 bytes), with `FORMAT_ID` stored
and validated by the host. Do not serialize Rust struct memory or interpret old
renderer snapshots using this format. Full hot material caches and compact cold
storage are a possible host policy; no automatic eviction/conversion is hidden
inside the library. Current compact decoding is slower than full decoding.
