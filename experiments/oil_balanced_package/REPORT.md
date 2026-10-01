# Balanced Old Holland Eight is packaged and usable in the renderer

The final balanced model is fitted on all 286 source measurements, exported as
native OPP3 packages and verified through the existing eight-material renderer.
**Recommendation: use the balanced corrected package as the preferred local
measured recipe palette, with the previous package retained for comparison.**
The global renderer/synthetic default is unchanged.

This choice follows the earlier excluded-family measured-paint comparison and
successful product checks. It does not follow from a claim that these rendered
images are more physically accurate. The balanced model has a lighter darkest
mixture found by the current search, and slightly worse RGB-target coverage in
this fixed test set. Those differences remain visible and documented.

## Local deliverables

- [Balanced empirical palette](../../target/measured-oils/balanced-eight/old-holland-eight-balanced-empirical.opp):
  6521 bytes, native 31 bands and 28 pair corrections.
- [Balanced K-M base](../../target/measured-oils/balanced-eight/old-holland-eight-balanced-km.opp):
  5618 bytes, diagnostic reference.
- [Local comparison bundle](../../target/measured-oils/balanced-eight/old-holland-eight-balanced-local.zip):
  both new packages, the unchanged previous package, metadata and usage notes.
- [Preferred local palette descriptor](../../target/measured-oils/balanced-eight/preferred-palette.json):
  explicit recommendation and identity; not an automatic global-default switch.

The source-derived packages and preview images remain under ignored target/.
This report, scripts, numerical evidence and renderer example are committed.

## Final calibration and runtime checks

The unchanged tested weighting rule gives each nonpure category equal total
influence. Full-data category sizes are 50, 45, 56 and 127; pure endpoints remain
fixed. The final fit took 9.566 seconds on this host and
reproduced all optical/pair coefficients exactly on a second fit.

The [107-family exclusion study](../oil_balanced_calibration/REPORT.md) remains
the predictive evidence: 16.28% lower multicolor mean DE00 and 16.16% lower mean
spectral RMSE than its paired binary baseline, recovering binary/no-white mean
color regressions while retaining a 25.05% binary spectral penalty. Those are
cross-fitted procedure results, not validation scores of this all-data model.
[fit-verification.json](fit-verification.json) labels final training diagnostics
explicitly; they are not a new accuracy test.

All 2,411 probes pass: 286 measured recipes, 8 pures, all 28 pair ramps including
tiny fractions, 1,024 dense recipes and the equal eight-paint mixture. Rust and
Python spectra agree within 4.44e-16;
linear RGB within 3.33e-16.
Package/recipe round trips and later mixing remain exact.

The renderer loads the new package with its existing Ochrell dependency pinned
to 17c13d0. No library/format or runtime algorithm change was necessary. Each
palette carries a distinct model identity, preserving old saved paintings.

## Identical recipes and paint behavior

The 32 authored recipes cover all pure paints, saturated pairs, dark mixtures,
chromatic neutrals, white tints and eight-ingredient blends. Three strokes per
recipe give 96 strokes. The two packages use identical geometry and amounts.
All four material/height/wetness/coverage planes agree exactly between packages;
only displayed colors change. All eight material slots remain active where used.

![Exact decoded recipe colors](../../target/measured-oils/balanced-eight/decoded-swatches.png)

![Identical recipe painting comparison](../../target/measured-oils/balanced-eight/fixed-recipes-comparison.png)

The pure decoded colors agree exactly. Changes in mixture colors are expected
when replacing fitted coefficients; they are not brush-transport changes.
The usual 94-stroke fixture additionally exercises overlap, pickup, drying,
smudging, scumbling and renderer glaze modes. These software checks do not
validate physical glaze/translucency behavior absent from the optical model.

![Renderer fixture comparison](../../target/measured-oils/balanced-eight/renderer-fixture-comparison.png)

All six jobs save, reload and repaint all five canvas planes bit-identically
on this host. Saved job bytes and future mixtures also reproduce exactly.
The oil-palette suite passes all seven integration tests and one documentation
test; scoped Clippy for the new comparison example passes with warnings denied.
Cross-platform bit identity of empirical logarithms/exponentials was not tested.

## RGB target matching: usable, with a darker-color limitation

Both packages match the same 32 RGB targets: grays, saturated colors, pastels
and muted colors. The search returns achieved color, proportions and residual
error; it does not guarantee a unique recipe or globally optimal match.

| Metric | Previous package | Balanced package |
| --- | --- | --- |
| Mean displayed OKLab x100 target error | 4.6374 | 4.9769 |
| Maximum target error | 25.2942 | 28.5200 |
| Closest found to requested black | #232225 | #292A30 |
| Time for 32 matches (single observation) | 251.3 ms | 318.9 ms |
| Author 94-stroke fixture, including streak variants | 3495.6 ms | 4285.8 ms |

At a numerical comparison tolerance of 0.0001 OKLab x100, balanced improves
5 targets, worsens 11, and ties 16.
The mean target error increases 7.32%.
This describes RGB reachability/search behavior, not agreement with real paint.
RGB reachability alone is not a reason to prefer one physical calibration.

![Target and achieved colors](../../target/measured-oils/balanced-eight/target-swatches.png)

![Matched-target paintings](../../target/measured-oils/balanced-eight/matched-targets-comparison.png)

## Performance and the LUT decision

Seven observations after one discarded warmup, alternating package order.
Decode uses the same 4,096-recipe corpus and 100,000 operations per observation.
Paint jobs render 384x480; matching/preparation is outside the paint timings.
Values below are median (min-max); all observations are in [timings.csv](timings.csv).

| Operation | Previous | Balanced | Units |
| --- | --- | --- | --- |
| Recipe to displayed RGB | 988.08 (951.10-1030.98) | 1019.59 (908.77-1062.17) | ns/recipe |
| 96 fixed-recipe strokes | 120.25 (113.34-122.25) | 114.30 (107.51-122.56) | ms |
| 96 matched-target strokes | 113.39 (106.99-120.60) | 112.12 (107.08-130.31) | ms |
| 94-stroke renderer fixture | 224.64 (215.77-236.00) | 223.91 (212.72-238.34) | ms |

Runtime: rustc 1.91.1 (ed61e7d7e 2025-11-07), release workspace build, one calling thread;
shared-host scheduling and clock variation remain. These are small native
fixtures, not a browser/large-canvas throughput claim. Both palettes use the
same decoder; timing differences do not establish an algorithmic speed change.

**No eight-paint LUT is generated in this package.** The current forward LUT
supports four paints/81 bands. Eight proportions have seven independent recipe
coordinates. A naive 65-point dense extension would require
58,826,734,687,500 bytes (58.83 TB)
for RGB f32 payload alone. Even packing just ordered simplex grid nodes would
use 15.96 GB. These
are storage calculations, not quality requirements or proof all LUTs are large.

The direct balanced decoder is about 1.02
microseconds per recipe here. Target matching is much more expensive per call,
but occurs during authoring; painting uses persistent recipes and never solves
the inverse per pixel. The measured fixture authoring time makes repeated-target
caching a concrete next optimization. A small RGB-to-recipe LUT could later
seed/refine matching, but it would not accelerate recipe-to-display painting.

For painting acceleration across 8-16 paints, evaluate sparse/adaptive tables,
factorized approximations or repeated-recipe caching against this frozen direct
model. Preserve all recipe proportions and compare approximation errors on pure,
boundary, dark, white-tint and dense recipes. A 3D RGB lookup cannot in general
replace eight-material state: different recipes can share a displayed RGB and
behave differently when mixed later. The four-paint LUT remains available for
its supported mode; it is not silently applied to this package.

## Reproduction and adoption

Run the final fitter in a fresh ignored output directory, export, run the existing
Rust measured_palette_probe for km and empirical, then verify-runtime. Run the
new sibling renderer example with the old and balanced corrected packages:

```powershell
.\target\measured-oils\venv\Scripts\python.exe experiments/oil_balanced_package/run.py fit
.\target\measured-oils\venv\Scripts\python.exe experiments/oil_balanced_package/run.py export
cargo run --release --offline --example measured_palette_probe -- target/measured-oils/balanced-eight/old-holland-eight-balanced-km.opp target/measured-oils/balanced-eight/recipes.f64 target/measured-oils/balanced-eight/km-predictions.f64
cargo run --release --offline --example measured_palette_probe -- target/measured-oils/balanced-eight/old-holland-eight-balanced-empirical.opp target/measured-oils/balanced-eight/recipes.f64 target/measured-oils/balanced-eight/empirical-predictions.f64
.\target\measured-oils\venv\Scripts\python.exe experiments/oil_balanced_package/run.py verify-runtime
```

From oilpaint-renderer:

```powershell
cargo run --release --offline -p oil-palette --example compare_old_holland -- ../ochrell/target/measured-oils/unified-eight/old-holland-eight-empirical.opp ../ochrell/target/measured-oils/balanced-eight/old-holland-eight-balanced-empirical.opp ../ochrell/target/measured-oils/balanced-eight/comparison
```

Then run experiments/oil_balanced_package/report.py from Ochrell. The original
coefficients, measured source and previous packages remain unchanged.

For code-driven recipe painting, adopt the balanced corrected package as the
preferred local experimental measured palette. Keep the old package selectable
and keep achieved-color feedback for unreachable targets. A universal default
switch and large-palette acceleration are separate product changes.

Frozen final fit: `99cc38cb2751d8a09895e3a78375aabd003c6933c068145334bf604a71d70afc`.
Local ZIP: `db8361a957060bcdd64c2bb444280e6f4585f6be754dc2070847fbb7f679338c`.
See [workflow-verification.json](workflow-verification.json) for source/artifact
hashes, matching results, timing aggregates and exact-replay evidence.
