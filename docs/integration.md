# Using Ochrell in the oil-paint renderer

This is a working native CPU integration with the sibling `oilpaint-renderer`
project. The independent Ochrell library has no Python, renderer, FFI or runtime
crate dependencies. Its mathematical model and fitted coefficients are unchanged.
The [measured report](integration-results.md) covers quality, mixing, rendering,
memory, Mixbox comparison, failures and next steps. The research paper and its
earlier measurements remain a frozen study, not an account of these additions.

## Setup and run

Keep the two source directories side by side:

```
projects/
  ochrell/
  oilpaint-renderer/
```

Rust and a native Rust linker must be installed (tested with Windows MSVC,
rustc 1.91.1). Python 3.12 was tested. From `oilpaint-renderer`, in PowerShell:

```powershell
uv venv .venv
uv pip install --python .venv/Scripts/python.exe -r requirements-ochrell.txt
.venv/Scripts/python.exe -m oilpaint render scenes/storm_v3.py --size 600x750 --plan-width 320 --mixer ochrell --no-layers --out out/ochrell-storm
.venv/Scripts/python.exe -m oilpaint relight out/ochrell-storm --bump 0.95 --shade-blur 0.002
```

On POSIX use `.venv/bin/python`. Standard `python -m venv` and `python -m pip`
work too. The Python adapter runs an offline Cargo release build once per native
library per process. The path dependency is `../../../ochrell` from the bridge
crate. `CARGO` can select a toolchain wrapper. No C compiler is needed for this
backend. There is no automatic installation of Mixbox.

Existing layers, planning, replay, crop, relight and timelapse interfaces remain.
For replay, use the same mixer as the saved file:

```powershell
.venv/Scripts/python.exe -m oilpaint render scenes/storm_v3.py --size 600x750 --plan-width 320 --mixer ochrell --strokes out/ochrell-storm/strokes.npz --no-layers --out out/ochrell-replay
```

The existing planner is still RGB-guided and can decode/reconstruct palette
choices when authoring a stroke. Once that stroke enters the brush kernel, its
optical material survives pickup, lane mixing, deposition and saved canvas
round trips. Old seven-component stroke files are not silently converted into
Ochrell states: regenerate strokes from the authored scene/RGB colors.

## Architecture and quantities

Python scene/planner -> cached stroke states -> renderer-owned Rust C ABI ->
existing bristle kernel -> Ochrell -> sRGB albedo + independent surface planes
-> existing Python relighting -> PNG/video.

The bridge lives in `oilpaint-renderer/native/ochrell-brush`. It compiles the
existing Rust `spikes/oilcore/src/kernel.rs` and `math.rs`; it does not port or
replace the renderer. Conditional branches leave the original C and Rust
paths available. No GPU execution or browser performance is claimed.

| Quantity | Representation and use |
|---|---|
| Material | K[41], S[41], linear-RGB residual[3], 85 f32 values; linear combinations of inferred optical states |
| Exposed paint amount | Separate f32 plane in relative units; determines mixture proportions |
| Brush load / depletion | Existing heuristic brush controls; amount available per covered pixel, not measured volume |
| Coverage | Existing footprint/pressure/opacity calculation; linear-light RGB compositing after material mixing |
| Cover plane | Accumulated stroke coverage diagnostic; may exceed 1, not a bounded alpha plane |
| Wetness | Existing [0,1] availability heuristic, controlled by layers' `dry_after` |
| Height | Existing hgain, flatten, bristle ridges, levees, scumble and smudge rules; not optical thickness |
| Appearance | Existing weave, normals, shading, gloss and display code; independent of Ochrell |

For a deposited pixel, incoming amount is coverage times brush load (or carried
tip amount for smudge). Accessible old amount is stored amount times wetness.
The mixture fraction is incoming / (accessible + incoming). The decoded result
is then composited over the previous visible RGB using coverage in linear light.
Ground has zero material amount and does not dilute the first paint. Dried paint
remains visible beneath partial coverage, but its old material is inaccessible.

Pickup averages exposed states weighted by amount and footprint. Its acquired
amount also uses wetness and `pickup`; lane tips carry their own material amount.
`release` replenishes paint tips toward their fresh load, including over bare
areas. Two-color loading and signed streaks remain; signed streaks are limited
before they make K or S invalid. Smudged paint remains wet for further pickup.

This is a **single exposed-material approximation**, not a mass-conserving paint
transport simulation. Pickup copies paint without subtracting volume from the
source, brush depletion is distance-based, buried material is not recoverable,
and partial subpixel coverage is not stored as separate layers. These choices
belong to the renderer and are not Ochrell physics.

`glaze` applies linear-light RGB coverage compositing without changing the
underlying stored material/amount/height. This preserves an artistic renderer
mode; it is not thickness-dependent Kubelka–Munk reflectance or optical glazing.

## Storage, validation and controls

`Latent::try_from_parts` (and the reference counterpart) enables checked import
of saved arrays. It rejects nonfinite components, K < 0 and S <= 0. It does not
validate a real paint or define Rust struct layout. The native wire format is
explicit arrays, versioned as `ochrell-0.2-ks41-f32-v1`. The unsafe trusted-buffer
ABI belongs to the renderer, with shape/type/value checks in Python. A native
failure is reported as an error; discard a partially painted canvas on failure.

Stroke files identify the backend and format. Ochrell canvas snapshots preserve
all planes in float32 (regions in uint8), including amount, blur and wetness.
Saved state and future stroke replay are bit-exact on the tested host. The old
renderer snapshot path retains its old float16 behavior. Switching a global
Python mixer while reusing incompatible strokes is rejected; configure a mixer
before authoring each canvas/stroke set. Concurrent global backend mutation is
not supported.

`--mixer ochrell-roundtrip` intentionally decodes and re-encodes after canvas
material updates and brush pickup/replenishment. `--mixer ochrell-srgb` stores
padded RGB in the same 85-float layout for a matched-transport control. These
are diagnostics, not recommended material storage. Original `mixbox` and `rgb`
backend behavior remains available.

The optional `mixbox-material` control is exposed through Python/reproduction,
not the main render CLI. It reuses the original decoder and seven-component
state, padded to the same 85-float layout, under identical new transport. Its
separate `native/mixer-comparison` crate compiles the existing Mixbox code.
Normal Ochrell builds exclude that decoder and do not depend on that crate.

## Reproduce

From Ochrell:

```powershell
cargo test --release --offline
cargo run --release --offline --example basic
cargo run --release --offline --example brush_workload > results/integration/kernel-benchmark.csv
```

From the renderer:

```powershell
cargo test --release --offline --manifest-path native/ochrell-brush/Cargo.toml
.venv/Scripts/python.exe -m unittest discover -s tests -p test_ochrell.py -v
.venv/Scripts/python.exe tools/check_ochrell.py
.venv/Scripts/python.exe tools/evaluate_ochrell.py --out ../ochrell/results/integration
```

The numerical study records 2,048 samples, fixed PCG64 seed 20260930, an
81-band f64 reference, four-color/grouped weights, white/black addition, 16/64/256
repeated operations, and 128 tiny-update stress cases. It tests f16 storage at
every update, not merely final RGB quantization. The brush study uses saved
authored RGB colors/actions/seeds across methods, checks image determinism and
surface-plane equality, and separates painting, layer preparation and lighting.
Raw inputs, per-sample errors, repetitions, source hashes, environment and images
are in `results/integration`. Conditions and timings are local observations.

Optional Mixbox comparison (the existing non-commercial comparator):

```powershell
uv pip install --python .venv/Scripts/python.exe pymixbox==2.0.0
.venv/Scripts/python.exe tools/compare_mixbox.py
.venv/Scripts/python.exe tools/compare_scene_mixers.py out/ochrell-storm
```

Both native cached mixing kernels are timed in one executable with identical
release flags. Full RGB operations are also timed through the actual Python
adapters at batches 1/64/1024/4096. There is no native Mixbox encoder benchmark:
the renderer's encoder is NumPy. Do not interpret adapter timings as an intrinsic
Rust-versus-Mixbox algorithm comparison. Native and Python results are separate.

Run benchmarks without other CPU-heavy jobs; compare distributions, not a
single fast sample. The original complete harness can be run with
`$env:OILPAINT_KERNEL='rust'; python -m oilpaint test all` when Mixbox is installed.
Its Mixbox-curve gates are not real-paint accuracy evidence or Ochrell thresholds.

## Release boundary

Ochrell remains MIT OR Apache-2.0 code plus the existing attributed CC BY-SA 4.0
data/derived assets. Retain all notices and coefficient provenance. Comparisons
are observations; no comparator output is a fitting target. No Mixbox LUT,
package source, or coefficients are exported into Ochrell. The optional package
is installed in the renderer environment only. The renderer retains its own
existing NOTICE and unresolved original-code licensing status; this integration
does not relicense it. Regenerate the source-distribution manifest with the
existing packaging tool when preparing a new release archive.
