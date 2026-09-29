# Optimization round 1: separate optics from color integration

Baseline commit: `17531c6`. Selected candidate: `split_both`.
The runtime change separates independent wavelength calculations from the
ordered RGB sum in encoding and decoding. Equations, coefficient data,
wavelength counts, residual, gamut mapping, public API and state size are
unchanged. This is a CPU optimization, not a new color model.

## Confirmed performance

Windows 11 x64, Core Ultra 7 258V, rustc 1.91.1/MSVC; one process pinned to
logical CPU 0 (not a claim that it is the fastest core). Release, LTO off,
codegen-units=1, no target-cpu override or fast-math. Four runs per executable
in ABBA then BAAB order, 500,000 operations and nine measured repetitions
per operation/run; each run discards a warmup round and rotates operation
order. Table values are medians of the four run medians. Seed 1907.

| Operation | Baseline ns | Selected ns | Speedup | Time reduction |
|---|---:|---:|---:|---:|
| cached_mix_decode | 244.92 | 142.29 | 1.72x | 41.9% |
| decode | 210.04 | 129.13 | 1.63x | 38.5% |
| decode_linear | 151.05 | 64.37 | 2.35x | 57.4% |
| encode | 248.70 | 159.09 | 1.56x | 36.0% |
| full_rgb | 722.03 | 432.37 | 1.67x | 40.1% |
| interpolate | 44.77 | 48.89 | 0.92x | -9.2% |
| update_stream | 280.17 | 179.43 | 1.56x | 36.0% |

The two balanced four-run blocks separately improve cached mix/decode,
full RGB mixing and streamed updates. Absolute times still vary with CPU
frequency/background activity. The unchanged interpolation control measured
about 9% slower in this sample; that unfavorable result is retained, and no
interpolation improvement is claimed. These results do not predict a renderer
speedup or replace the earlier integration benchmark conditions.

Emitted x86-64 assembly contains packed `divps` and `sqrtps` instructions in
the independent optics loop. The compiler can process several wavelengths
together while the RGB sum keeps its original order. Source remains portable
safe Rust: no intrinsics, architecture-specific code or runtime dependency.

The selected probe executable grew from 237,568 to 240,128 bytes (+2,560).
The material remains 340 bytes. The decoder adds a stack reflectance array
(41 f32 values / 81 f64 values in source); no heap allocation is introduced.

## Numerical acceptance

Both seed 20260930 and independently selected holdout seed 1907 contain 57,611
records: random continuous RGB plus a 16-cubed grid, reconstruction, pair
mixes, white/black addition, weighted/grouped states, full RGB calls, 256
repeated updates, 4,096 tiny pickups, canonical colors and extreme valid
imported K/S magnitudes. All decoded RGB bits and fast-material component
fingerprints match the frozen baseline exactly in both runs. Fast/reference
errors are recorded in each row and unchanged by the selected candidate.

The existing 25 release tests passed for the selected candidate. After the
experiment, a new fast/reference scale-invariance regression test was added;
all 26 release tests pass. The basic example remains `[101, 152, 94]`.
Exact results were verified on this compiler/host; other platforms still
need their own execution measurements. No real-paint accuracy claim changes.

## All screened candidates, including rejection

The initial screening ran sequentially and had substantial timing drift,
including changes in unchanged operations. Its first baseline was unusually
slow. These raw values are for audit, not speedup claims; selection was
followed by the alternating confirmation above.

| Candidate | Existing tests | Exact numerical gate | Cached mix/decode ns | Full RGB ns |
|---|---|---|---:|---:|
| baseline | pass | pass | 398.24 | 1288.52 |
| inline_decode | pass | pass | 239.43 | 662.45 |
| inline_hot | pass | pass | 197.31 | 600.45 |
| split_decode | pass | pass | 165.27 | 647.68 |
| split_encode | pass | pass | 257.48 | 666.47 |
| split_both | pass | pass | 131.79 | 425.20 |
| split_both_inline | pass | pass | 153.18 | 605.58 |
| algebraic_decode | pass | fail | 168.20 | 544.00 |

The one-division algebraic decoder was rejected. It passed the old unit
tests but changed many RGB bits; valid imported coefficient scales caused
product overflow/underflow, with worst reference discrepancy near 100
DEOK100. Small ordinary-color errors would have hidden that domain failure.
The added scale-invariance test protects it explicitly. Inlining variants
were not promoted; broader inlining also increased executable size. Their
screening alone is insufficient to claim they are universally slower.

## Reproduce

From a Git checkout retaining baseline `17531c6`, with Rust and Python:

```powershell
python tools/hillclimb.py --cpu 0 --out target/hillclimb/reproduce-round1
python tools/hillclimb.py --cpu 0 --out target/hillclimb/reproduce-round1 --confirm split_both --iterations 500000 --repeats 9
python tools/hillclimb.py --cpu 0 --out target/hillclimb/reproduce-round1 --holdout split_both
cargo test --release --offline
cargo run --release --offline --example basic
```

The runner reads baseline source from Git, temporarily applies each recorded
transformation, and restores the starting working file in a finally block.
It refuses to overwrite an unexpected concurrent edit. Separate output
directories get separate temporary executables. Omit `--cpu` on platforms
without affinity support; doing so changes benchmark conditions. The new
regression test makes the algebraic candidate fail in a fresh reproduction,
as intended; the retained original screen predates that test.

Raw timing CSVs, compressed numerical records, patches, logs, source/executable
hashes, environment, confirmation and holdout summaries are under
`results/optimization/round1`. `python tools/report_hillclimb.py` regenerates
this report. Frozen integration and paper results were not overwritten.

## Next climb

Keep this as the new CPU baseline. State storage is still the main memory
problem: 340 bytes per material is unchanged. The next separate research
round should compare compact representations and full-precision accumulators
under reconstruction, tint, grouping and tiny-update/reload gates. It must
retain a full-state reference and not repeat the naive-f16 failure. Renderer
transport, appearance and snapshot IO remain in the renderer workstream.
