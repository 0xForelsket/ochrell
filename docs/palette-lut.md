# Prepared forward palette decoder

An opt-in `ochrell::palette_lut::PaletteLut` now accelerates Synthetic Four's
recipe-to-color calculation. The selected configuration is **65 samples per axis
with square-root recipe coordinates**. Material mixing, recipe persistence,
reference coefficients and the root RGB mixer are unchanged. This is a numerical
approximation of the synthetic reference, not measured-paint calibration.

## Use

```rust
use ochrell::{palette::synthetic_four, palette_lut::PaletteLut};

let palette = synthetic_four();
let prepared = PaletteLut::build(palette, 65).unwrap();
let green = palette.recipe([1., 0., 1., 0.]).unwrap();
let display = prepared.decode(&green).unwrap();

let bytes = prepared.to_bytes();
let restored = PaletteLut::from_bytes(palette, &bytes).unwrap();
assert_eq!(display, restored.decode(&green).unwrap());
```

`build` uses `LutMapping::RecipeSqrt`. Resolution is explicit: accepting a smaller
table does not imply it passed the documented error limits. `build_with_mapping`
also exposes `Uniform` and `EdgeFocused` for reproducing the unsuccessful trials.
The reference is always available through `Recipe::decode` and `decode_linear`.

Use `cargo run --release --offline --example prepared_palette` for an in-memory
example. Supply `target/synthetic-four.opl` as its final argument to create a
table file and load that same file on a subsequent run. A mismatched/corrupt file
is rejected, not silently replaced. Table preparation and loading are explicit;
no implicit global cache is added to the core.

## What is accelerated

For recipe proportions c, form z_i=sqrt(c_i)/sum_j sqrt(c_j), then cumulative
coordinates (z0, z0+z1, z0+z1+z2). A uniform grid in these coordinates gives more
samples near every zero-ingredient boundary. At each valid grid node, recover
c_i=z_i^2/sum_j z_j^2 and evaluate the direct spectral reference once.

The table stores raw linear RGB in f32, including negative/out-of-gamut values.
Runtime decoding uses four tetrahedral vertices, followed by the existing gamut
map and sRGB transfer for display. The coordinate transform changes where the
reference is sampled; it never replaces or mutates material proportions.
Repeated decoding therefore introduces no accumulated material-state error.

There are 274,625 dense cube nodes, of which 47,905 are in the ordered recipe
region. Unused nodes are zero and have no positive interpolation weight for
valid queries. Dense indexing is simple but leaves substantial room for a future
storage optimization. Payload: **3,296,020 bytes** including knots (about 3.14 MiB).
The full serialized artifact is 3,296,068 bytes.

## Selection and failures

The [experiment plan](palette-lut-plan.md) records the limits and each new
representation before its screen. Each screen uses 37,914 records. Screen seed:
20261001; selected candidate confirmation seed: 314159. The candidate with the
smallest passing table is chosen before confirmation; budgets were not relaxed.

| Mapping | 17 samples/axis | 33 samples/axis | 65 samples/axis |
|---|---|---|---|
| Uniform cumulative grid | Fail | Fail | Fail |
| Cosine knots near cumulative endpoints | Fail | Fail | Fail |
| Square-root recipe coordinates | Fail | Fail | **Pass** |

Uniform grids under-resolved rapid changes near pure paints and white tints.
Cosine knots improved some edges but did not resolve low ingredient proportions
along interior simplex faces. The component-wise square-root transform targets
those faces as well. The 33-node transformed candidate met some limits but failed
the mean/tail requirements in other families; it was not accepted on its maximum
error alone.

Failures and their exact experiment sources are retained under
`results/palette-lut/uniform` and `results/palette-lut/edge-focused`. They predate
the final artifact layout/API; the current explicit mapping options reproduce
the strategies, while archived sources identify exactly what produced the logs.

## Confirmation errors

Metric: delta E OKLab * 100 on displayed colors. Raw errors are maximum absolute
linear-RGB channel differences. These are differences from the direct synthetic
reference, not CIEDE2000 values or errors against real paint.

| Family | Samples | Mean | P95 | Maximum | Raw channel maximum |
|---|---:|---:|---:|---:|---:|
| Pure paints | 4 | 0 | 0 | 0 | 0.00000002 |
| Pair ramps | 3,078 | 0.00334 | 0.00718 | 0.01582 | 0.000731 |
| Interior recipes | 4,096 | 0.01145 | 0.01852 | 0.03736 | 0.002079 |
| Simplex faces | 4,096 | 0.00774 | 0.01272 | 0.03772 | 0.001803 |
| Tiny ingredient fractions | 2,048 | 0.00936 | 0.03688 | **0.07020** | **0.002676** |
| White tints | 4,112 | 0.00839 | 0.01623 | 0.04507 | 0.001698 |
| 256-step chains | 4,096 | 0.01246 | 0.01627 | 0.02125 | 0.000377 |
| 4,096 tiny updates | 16,384 | 0.00308 | 0.00680 | 0.03229 | 0.001254 |

All sampled families pass mean <=0.03, P95 <=0.10, max <=0.50 and raw channel
max <=0.01; pure paints meet the tighter endpoint limits. White-tint ramps have
no observed luminance decrease. Canonical ramps, pure paints and deterministic
tiny-update controls deliberately repeat between screens; random recipe families
use the separate confirmation seed. These are sampled checks, not a proof of an
error bound for every possible recipe or other palettes.

## Native performance

Windows x64, Intel Core Ultra 7 258V, Rust 1.91.1/MSVC. Same release executable,
one thread, LTO off, codegen-units=1, no CPU affinity pinning or custom RUSTFLAGS.
Ten repetitions of 300,000 operations after a discarded warmup, with operation
order rotated each repetition. Input corpus: 4,096 cached recipes, seed 1907.
Shared-host clock and scheduling variation remain visible in raw timings.

| Operation | Direct reference median ns | LUT median ns | Speedup |
|---|---:|---:|---:|
| Raw linear decode | 411.80 | 35.53 | 11.59x |
| Display decode | 481.15 | 79.59 | 6.05x |
| Recipe interpolation + display decode | 509.08 | 131.49 | 3.87x |

The LUT's display-decode range was 64.26-104.16 ns, compared with 424.37-550.22 ns
for the reference. Mix/decode ranges were 115.01-173.91 versus 452.34-601.73 ns.
An initial run also improved both operations; the table above uses the final
recorded executable and timing procedure.

Ten preparation/load observations: build median **20.33 ms** (19.33-22.47 ms),
in-memory load including checksum/validation **18.93 ms** (16.78-19.84 ms). These
exclude disk IO and serialization. Loading is not dramatically cheaper here
because it verifies the whole table; the benefit measured is repeated decoding.
There is no RGB inverse solver in these preparation times. This does not predict
the cost of an arbitrary palette's RGB-to-recipe table or physical calibration.

This is a CPU mixer experiment. It is not a renderer benchmark, comparison with
current Mixbox, browser runtime measurement or promise of the same speedup on
other hardware. The current painting application does not use this LUT yet.

## Persistence and checks

OPL1 bytes: ASCII magic (4), exact palette fingerprint (32), little-endian u32
resolution (4), little-endian u32 mapping (4: uniform=0, cosine=1, square-root=2),
resolution little-endian f64 knots, then resolution cubed RGB triples of
little-endian f32, then CRC-32/ISO-HDLC (4) of all preceding bytes. Cube node
order is u outer, v middle, w inner. Supported resolution is 2-129.

Loading validates the bounded resolution before allocation, exact length,
palette identity, mapping tag, checksum, increasing finite knots from 0 to 1,
and finite channels. Uniform/square-root mappings also require the declared
uniform knots. CRC is an accidental-corruption check, not authentication or
proof that a supplied finite table matches the reference. Applications should
load artifacts they generated or obtained from a trusted source.

Tests cover affine fields for every mapping, reference grid nodes, preserved
out-of-gamut values, table and recipe round trips, invalid input, cell/face
continuity, a further seeded boundary/interior probe, and exact material after
4,096 repeated updates. Decode entry points reject a different palette object.
No recipes, palette definitions or legacy formats were changed.

All 50 tests, including four documentation examples, passed on Rust 1.91.1 and
Rust 1.75.0. All targets compiled and the library compiled for wasm32. The example
also generated a real OPL1 file and loaded it in a second process with identical
green/tint output. Browser execution and renderer integration were not exercised.

## Reproduce

```powershell
cargo test --release --offline
cargo +1.75.0 test --release --offline
cargo check --lib --target wasm32-unknown-unknown --offline
python tools/evaluate_palette_lut.py --mapping recipe-sqrt
cargo run --release --offline --example prepared_palette -- target/synthetic-four.opl
```

Evaluation defaults to `target/palette-lut`; set `--out` to choose a separate
evidence directory. `--mapping uniform` and `--mapping edge` screen the retained
alternatives. Generation and decoding require no network or external paint
dataset. Rust remains dependency-free and supports the declared minimum version.

Current evidence: [summary](../results/palette-lut/recipe-sqrt/summary.json),
[selection](../results/palette-lut/recipe-sqrt/selection.json),
[confirmation](../results/palette-lut/recipe-sqrt/holdout.json), and
[raw timing repetitions](../results/palette-lut/recipe-sqrt/benchmark.csv).
Compressed per-sample errors and source hashes are stored alongside them.

Next: add target-color recipe search against the palette reference, with achieved
color/error reporting and a policy for ambiguous recipes. Renderer integration
and the measured oil-palette study remain separate work.
