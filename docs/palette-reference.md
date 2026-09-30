# Palette reference: first implementation

This stage implements the independent Synthetic Four reference selected in
[starter-palettes.md](starter-palettes.md). It adds an opt-in module; the root
RGB mixer, compact state, frozen experiments and renderer are unchanged.

Subsequent stage: an opt-in [forward LUT](palette-lut.md) now uses this unchanged
reference. The contract and initial measurements below describe the direct
reference stage; prepared decoding is a separate API and artifact.

## Contract declared before validation

- Four named paints: yellow, red, blue and white. Recipes contain four normalized
  f64 proportions in relative synthetic material units, with no RGB residual.
- Direct homogeneous, infinite-thickness K-M at 81 samples, 380-780 nm at 5 nm.
  Mix K and S separately before computing reflectance. Use existing attributed
  CIE 1931 2-degree / D65 data with trapezoidal, neutral-normalized linear sRGB
  projection. Expose raw linear RGB separately from gamut-mapped display color.
- Accept finite nonnegative quantities with a positive total, including finite
  values whose naive sum would overflow. Reject invalid ratios instead of
  silently clamping them. Grouped mixtures carry group quantities explicitly.
- Bind a recipe to its palette. Save an explicit format version, a generated
  palette content fingerprint and exact f64 proportions. Reject incompatible
  or invalid saved states, preserving valid recipe bits through reloads.
- Keep the reference independent of LUTs and RGB-to-recipe optimization. Neither
  is implemented in this stage. A public arbitrary-palette import format also
  remains future work; this API initially exposes only the built-in reference.

## Independent material definition

`data/palettes/synthetic-four-v1.json` declares four original reflectance curves.
Each starts with a positive floor and adds rising or falling cubic smoothstep
transitions. For t clamped to [0,1], H(t) = t*t*(3-2*t). Wavelengths, transition
endpoints and gains are explicit in the definition; white is constant at 0.94.

For each paint and wavelength, infer q=(1-r)^2/(2*r), S=strength/sqrt(1+q),
K=q*S. Chromatic strengths are 1; white strength is 2. These are declared
synthetic choices, not manufacturer data or fits to another mixer. The shapes
are new definitions, not a subset of the frozen legacy palette or a decode/
re-encode of the v0.2 anchors. No measured Old Holland data is used.

`python tools/generate_palette.py` generates only the new palette's coefficients,
projection and manifest. `--check` verifies bytes without rewriting files.
The generator uses the Python standard library and the existing CIE CSV. It
does not invoke v0.2's generation pipeline or regenerate a paper.

The palette fingerprint covers the definition, CIE subset, generator source and
exact generated optical/projection values. Display uses the crate's existing
gamut mapping and sRGB transfer. Identical storage does not imply bit-identical
display math on every platform; cross-host execution still needs verification.

## Validation plan

Use analytic optical cases and an independently evaluated Python reference to
check decoding, not just agreement between Rust functions sharing one kernel.
Check pure paints, all simplex boundaries, canonical yellow/blue and red/blue
mixtures, white-tint luminance, finite positive optics and raw/display outputs.
Recipe tests cover quantities at numeric extremes, invalid values, grouping,
permutation, 4,096 tiny updates and exact persistence of future mixtures.
Storage tests include unknown format/palette, malformed lengths and invalid
proportions. Existing tests must continue to pass on stable and Rust 1.75.

These are model and implementation tests, not physical paint validation or
evidence of a renderer speedup. The Old Holland source and its 21/24 measured
fit/holdout split remain untouched. Record visual limitations instead of
claiming this first synthetic palette is artist-approved or physically accurate.

## Use the reference

```rust
use ochrell::palette::{synthetic_four, Recipe};

let palette = synthetic_four();
let yellow = palette.paint("yellow").unwrap();
let blue = palette.paint("blue").unwrap();
let white = palette.paint("white").unwrap();
let green = yellow.interpolate(blue, 0.5).unwrap();
assert_eq!(green.decode().to_srgb8(), [0, 162, 119]);

// Carry group amounts: 3 parts of the green mixture and 1 part white.
let tint = Recipe::weighted(&[(green, 3.0), (white, 1.0)]).unwrap();
let saved = tint.to_le_bytes();
let restored = palette.recipe_from_bytes(&saved).unwrap();
assert_eq!(restored.proportions(), tint.proportions());
```

`palette.recipe([yellow, red, blue, white])` accepts amounts directly in that
order. Names are lowercase and checked. `interpolate` rejects nonfinite or
out-of-range fractions, unlike the clamping behavior of the existing root API.
Weighted mixing rejects empty/all-zero, negative or nonfinite amounts and a
different palette even if that recipe has zero weight. Scaling before summing
handles large finite amounts; unrepresentably tiny ratios can still round to
zero in f64. Grouping agrees within floating-point precision, not necessarily
bit for bit after a different arithmetic order.

`Recipe` stores four f64 proportions and a borrow of its palette (40 bytes on
this x64 host). This is a correctness reference, not the proposed final f32
canvas format. Persistent bytes use the following 68-byte payload:

| Byte offset | Meaning |
|---|---|
| 0 | Four-byte ASCII `OPR1`, recipe format version 1 |
| 4 | 32-byte SHA-256 fingerprint of the exact built-in palette artifact |
| 36 | Four little-endian f64 proportions in declared paint order |

Loading checks exact payload length, format, palette identity, finite values in
[0,1] and a sum within 1e-12 of one. It preserves accepted bits rather than
renormalizing. The fingerprint is not an integrity checksum for the proportions;
hosts need their own checksum if they require detection of storage corruption.
Hosts retain the compatible palette and store amount/coverage separately.

## Initial results and limitations

The first yellow used a rise from 430 to 510 nm. Its yellow/blue midpoint was
`[0,166,164]`, too close to cyan for the intended green diagnostic. A small
analytic-definition screen produced the following RGB8 values; these are model
outputs, not measurements of paint or a perceptual preference study.

| Yellow transition | Pure yellow | Equal yellow/blue |
|---|---|---|
| 430-510 nm | [239,249,125] | [0,166,164] |
| 450-530 nm | [246,244,50] | [0,165,132] |
| 450-540 nm | [249,240,35] | [0,163,129] |
| **460-540 nm, selected** | **[251,238,0]** | **[0,162,119]** |
| 470-550 nm | [255,229,61] | [3,159,108] |

The selected transition retains a yellow source and separates green from blue
at the midpoint. It is an explicit artistic prior; this screen does not prove
an optimal palette. Red/blue remains a muted purple `[92,81,125]`, red/white is
pink `[238,127,141]`, and the source blue is visibly cyan-leaning. These are
limits of this first engineering baseline, not fidelity claims.

The independent checker reads the JSON/CIE inputs directly. It uses an expanded
smoothstep, an algebraically different S expression, the subtractive K-M
reflectance form, and XYZ integration before RGB conversion. It never reads
the generated Rust coefficient arrays. Actual Rust results include four pure
paints, six 65-step pair ramps and 1,024 seeded random recipes: 1,418 samples.

| Maximum absolute difference, Rust vs independent Python | Result |
|---|---:|
| Spectral reflectance | 2.43e-15 |
| Raw linear RGB | 2.84e-15 |
| Display sRGB, including Rust f32 output | 2.98e-8 |

100 of these samples have at least one raw RGB component outside [0,1]. The
existing neutral-axis map is used for display only. This baseline does not fit
surrogate pigments to stay within gamut as in the paper; the difference is
explicit and must be considered before choosing a final palette model.

All 41 tests, including three documentation examples, passed locally on Rust
1.91.1 and the minimum Rust 1.75.0. The library compiled for wasm32, but this is
not browser execution or cross-host determinism evidence. Generated-byte checks
and independent numerical checks are included in CI. No throughput comparison
or rendering integration is claimed in this stage.

The [recorded summary](../results/palette-reference/summary.json) includes exact
errors, source hashes and environment. The [swatch sheet](../results/palette-reference/swatches.svg)
uses actual Rust display outputs and was visually inspected.

## Reproduce

```powershell
python tools/generate_palette.py --check
cargo test --release --offline
cargo +1.75.0 test --release --offline
cargo check --lib --target wasm32-unknown-unknown --offline
cargo run --release --offline --example palette
python tools/check_palette.py
```

The numerical checker writes its summary and SVG under `target/palette-reference`
by default. Use `--out results/palette-reference` to replace the retained summary
and swatches after an intentional model/reference change. The generator writes
only the new palette assets when run without `--check`. Preserve the frozen
v0.2 study; generation of one palette does not regenerate the rest of Ochrell.

Next: choose error budgets and compare forward-decoder acceleration candidates
against this reference. Keep target-color matching and the measured oil-paint
fit as distinct tasks with their own evidence.
