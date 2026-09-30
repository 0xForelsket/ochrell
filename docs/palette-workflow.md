# Target colors and custom palette packages

Palette mode now supports loading owned optical definitions and finding recipes
for requested colors. Both remain opt-in. The existing RGB model is unchanged.

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
Packages are bounded to 16,384 bytes. Custom identity is the body hash, covering
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
Browser/TypeScript exposure, measured palette fitting, more than four paints and
changing the default remain separate milestones.
