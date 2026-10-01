# Target colors and custom palette packages

Palette mode supports loading owned optical definitions and finding recipes for
requested colors with **1-16 paints**. Both remain opt-in. The existing RGB model
is unchanged. The original four-paint API below remains source compatible.

```rust
use ochrell::{Color, palette::Palette, palette_lut::PaletteLut,
    palette_match::ColorMatcher};
# fn example() -> Result<(), Box<dyn std::error::Error>> {
let palette = Palette::from_bytes(&std::fs::read("my-palette.opp")?)?;
let table = PaletteLut::from_bytes(&palette, &std::fs::read("my-palette.opl")?)?;
let matcher = ColorMatcher::new(&palette)?;
let found = matcher.match_color(Color::srgb8(80, 170, 120))?;
println!("{:?}, error {}", found.recipe.proportions(), found.error_ok100);
let displayed = table.decode(&found.recipe)?;
# Ok(()) }
```

`Palette::from_optics` takes four named materials, K and S arrays on the fixed
81-band 380–780 nm grid, an amount basis (relative, mass or volume) and provenance.
The caller supplies coefficients in a consistent convention; RGB swatches do
not provide those measurements. This version uses the existing CIE/D65 projection.
It rejects other grids/projections, invalid text, duplicate names and nonfinite
or unsafe numerical ranges. The amount label records the convention; it does not
convert mass to volume. `paint_names()` now returns `[&str; 4]` by value to support
owned names in this experimental API.

OPP1 stores the optical definition: magic, grid and amount codes (u32 little
endian), six length-prefixed UTF-8 strings (id, provenance, four names), K, S and
RGB projection arrays (f64 little endian, row-major), then SHA-256 of the body.
Packages are bounded to 65,536 bytes. Custom identity is the body hash, covering
metadata and exact coefficient bits. Exact copies of the built-in palette retain
its published identity so existing OPR1 recipes and OPL1 tables continue to load.
Checksums detect corruption; they do not authenticate the source or its rights.
The LUT remains a separate prepared artifact. Equivalent independently loaded
palettes interoperate; different identities fail explicitly.

The matcher prepares 165 coarse simplex seeds, chooses six starts in stable order,
then uses damped finite-difference Gauss–Newton and component-transfer refinement.
The budget is at most 24,000 direct forward evaluations per request. It minimizes
displayed, gamut-mapped OKLab distance and reports the actual achieved color,
recipe, error (OKLab ×100) and evaluation count. No residual is added, no unique
inverse is assumed and no certified global optimum is claimed. Matching uses the
direct spectral reference; final LUT decoding has its separately measured error.
Create a matcher once per palette and use it while authoring, not per pixel.

Renderers can use `with_cbrt` and `match_linear` with their portable color/math
conventions. `into_owned` on matcher and LUT supports long-lived host adapters.
Repeated search is deterministic for the same arithmetic implementation; the
default standard-library cube root alone is not a cross-platform bit guarantee.

## Evidence and reproduction

```text
cargo test --release --offline
cargo run --release --offline --example palette_workflow
```

The example writes two synthetic OPP1 packages, 65³ OPL1 tables and fresh matching
CSV results under `target/palette-workflow`. The custom palette doubles white K
and S: pure white stays the same, but its tinting strength changes. This is
synthetic input, not measured titanium white. No Old Holland data is redistributed.

An initial coordinate-only solver stalled at a gamut-map crease (error 0.837 on
development seed 314159). Simultaneous refinement fixed that regression. The
regression suite covers 512 reachable colors plus pure and unreachable targets.
After solver selection, fresh seed 271828 tested 1,024 targets per palette:

| Palette | Maximum error | Mean forward evaluations | Total time / 1,024 |
|---|---:|---:|---:|
| Synthetic Four | 0.00000184 | 300.8 | 153.60 ms |
| Strong-white example | 0.00000177 | 297.1 | 151.57 ms |

These are one local release run, not throughput promises or paint accuracy
measurements. Raw per-target rows are in `results/palette-workflow`. The separate
0.10 acceptance threshold was fixed before the fresh holdout. Black returns an
error of about 46.94 and achieved sRGB [98,79,121], honestly exposing this palette's
limited dark gamut. Package tests cover round trips, preserved identity,
incompatible recipes/tables, malformed lengths, grid, projection, coefficients
and checksums; SHA-256 includes standard known-answer tests.

Native renderer support is developed in the sibling oilpaint-renderer repository.
Browser/TypeScript exposure and changing the default remain separate milestones.
A [unified Old Holland Eight model](../experiments/oil_unified_eight/REPORT.md)
is now fitted and packaged locally as an experimental native-window palette.

## Palettes with up to sixteen paints

`PaletteN<N>`, `PaletteMetadataN<N>`, `RecipeN<N>` and `ColorMatcherN<N>` support
1-16 materials. N is the host's compile-time paint count; state arrays contain
exactly N components. `Palette`, `PaletteMetadata`, `Recipe` and `ColorMatcher`
remain aliases for the original four-paint types. The existing built-in spectrum
definitions, fingerprint, default mixer and four-paint LUT are unchanged.

```rust
use ochrell::{palette::PaletteN, palette_match::ColorMatcherN, Color};
# fn example(bytes: &[u8]) -> Result<(), Box<dyn std::error::Error>> {
let palette = PaletteN::<8>::from_bytes(bytes)?;
let mixture = palette.recipe([1., 2., 0., 0., 1., 0., 0., 4.])?;
let shown = mixture.decode();
let saved_recipe = mixture.to_bytes();
let restored = palette.recipe_from_bytes(&saved_recipe)?;
assert_eq!(shown, restored.decode());
let matcher = ColorMatcherN::new(&palette)?;
let matched = matcher.match_color(Color::srgb8(80, 170, 120))?;
println!("{:?}, error {}", matched.recipe.proportions(), matched.error_ok100);
# Ok(()) }
```

To create such a package, call `PaletteN::<N>::from_optics` with N distinct
material names and `[81][N]` K/S arrays. The same coefficient bounds, grid,
amount-basis declaration and exact CIE/D65 projection apply. A larger recipe
does not provide missing optical measurements. The eight-paint measured model
uses the subsequent native-window extension below.

For N != 4, OPP2 inserts a little-endian u32 count after the magic, followed by
the existing package fields with N names and N columns in each optical array.
OPR2 stores magic, u32 count, 32-byte palette fingerprint and N f64 proportions;
its size is `40 + 8*N` bytes. Four-paint packages and recipes still write OPP1
and OPR1, including the old fixed-size `to_le_bytes` API. Loaders reject the wrong
count, identity, malformed lengths and invalid coefficients or proportions;
they never pad, truncate or reinterpret slots.

The matcher keeps the exact original 165 seeds for N=4. Other sizes use N pure
seeds, three ratios for each pair, the equal mixture and 32 deterministic interior
seeds: `N + 3*N*(N-1)/2 + 33` seeds (409 at N=16). Search still uses six starts
and at most 24,000 refinement evaluations, returns the achieved color and error,
and makes no promise of a unique recipe or global optimum. The sampled regression
checks exercise reachable colors and unmatched black with 8, 10 and 16 materials.

`PaletteLut` remains four-paint only. Larger palettes decode their known recipes
directly through K-M. No 7D/15D table is allocated, no RGB residual is added and
no ingredient is dropped. Speedups measured for the four-paint LUT do not apply
to this direct path; larger-palette acceleration remains future work.

The sibling renderer exposes `PaletteMixerN::<N>::direct(palette)` and
`PaletteJobN<N>` for direct recipe painting. `RecipeLoadN<N>` preserves every
component through pickup, deposition and streaks. OPJ2 embeds the optical package,
explicit direct-decoder tag, stroke geometry and all N-component loads. Legacy
`PaletteMixer`, `PaletteJob` and OPJ1 retain their prepared four-paint behavior.
See the renderer's `crates/oil-palette/README.md` for the native API and format.

Verification covers scalar optical agreement, all eight input slots, amount-aware
grouping, matching at 8/10/16 paints, malformed counts and high-index components,
unchanged four-paint tests, and exact native canvas replay at 8/10/16 paints.
Fixtures are explicitly synthetic; these are implementation checks, not a new
physical-paint accuracy result.

## Native measured-window models

`PaletteN<N,B>` and `ColorMatcherN<N,B>` now accept B=31 as well as the default
B=81. B=31 means 400-700 nm at 10 nm; B=81 keeps 380-780 nm at 5 nm. The supported
CIE/D65 projection is fixed for each grid and verified on import. No interpolation,
tail padding or extrapolation is implicit. `spectral_grid()` returns
`(start_nm, step_nm, samples)` and `reflectance()` returns exactly B samples.

`from_optics_with_pair_correction` accepts either no controls (plain K-M), or
four cubic Bernstein controls for every pair, in lexicographic pair order. Each
control is finite and bounded to [-0.8,0.8]. The model applies a reflectance-logit
shift weighted by `4*c_i*c_j`; it vanishes at every pure endpoint. These controls
are an empirical model component, not absorption or scattering measurements.
The package identity includes them and color matching evaluates the full model.

Native-window or corrected models use OPP3: magic, u32 paint count, sample count,
start/step nm, amount basis and model kind (0=opaque K-M, 1=empirical pairs), then
the existing length-prefixed strings, K/S/projection arrays, u32 pair count and
four f64 controls per pair, followed by SHA-256. Every integer/f64 is little-endian.
Plain 81-band packages still write OPP1/OPP2 exactly. Recipes keep their existing
formats, bound to the complete palette/model identity; a grid or model change
therefore cannot silently reuse another recipe's meaning.

The original local Old Holland packages are `target/measured-oils/unified-eight/`:
`old-holland-eight-km.opp` and `old-holland-eight-empirical.opp`. Load with
`PaletteN::<8,31>::from_bytes`; in the renderer use
`PaletteMixerN::<8,false,31>::from_palette_bytes` and `PaletteJobN<8,false,31>`.
The renderer's `old_holland_eight` example renders both explicit and target-matched
recipes, with exact saved replay on the tested host. Cross-platform bit parity
of the empirical logarithm/exponential path has not been established.

The display is explicitly a 400-700 nm windowed preview, using the same
neutral-normalized RGB convention as the original runtime on that window.
The measured assessment separately reports unclipped windowed XYZ/Lab DE00.
These local experimental packages do not change the default, certify real-paint
accuracy, add browser exposure or establish a redistribution decision.

### Preferred local measured package

The [balanced package and renderer comparison](../experiments/oil_balanced_package/REPORT.md)
now supplies `target/measured-oils/balanced-eight/old-holland-eight-balanced-empirical.opp`.
It uses the tested equal-category calibration rule fitted to all 286 source
measurements. The companion `preferred-palette.json` records the recommendation
and exact identity; applications still choose the package explicitly. The local
ZIP includes its K-M base and the previous binary-calibrated package for comparison.
Load it through the same B=31 APIs above; there is no format or runtime migration.

The 2,411 runtime probes and six saved painting replays pass. Fixed recipe
painting preserves identical material transport across the two packages. The
balanced model is preferred for measured recipe behavior, with a lighter
closest-found black and a remaining binary spectral tradeoff. Achieved RGB
feedback stays important for unreachable targets; see the report for the full
comparison rather than treating rendered appearance as physical validation.

There is no eight-paint LUT yet. The direct decoder is about 1.02 microseconds
per recipe on the measured host. A dense seven-coordinate extension of the
four-paint table is impractical; larger-palette acceleration needs a different
representation. RGB-to-recipe lookup/caching would accelerate authoring, while
forward-decoder acceleration would affect painting. Explicit recipe authoring
already avoids the inverse search entirely.
