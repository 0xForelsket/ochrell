# Benchmarks and numerical results

All numbers are generated from recorded CSV files; no comparison against real paint is implied.

| Operation | Median ns | Million/s |
| --- | --- | --- |
| sRGB | 19.2 | 52 |
| linear RGB | 160 | 6.27 |
| OKLab | 245 | 4.07 |
| reference RGB | 2.39e+06 | 0.000418 |
| fast RGB | 602 | 1.66 |
| fast cached latent | 226 | 4.42 |
| tetrahedral lookup | 34.8 | 28.7 |
| reference cached latent | 835 | 1.2 |
| trilinear lookup | 34 | 29.4 |

CPU: AMD EPYC 9V74 80-Core Processor. Rust 1.75.0, release, LTO disabled, codegen-units=1; single thread. Seven repetitions. Full RGB timings include encoding and final display conversion; cached latent timings include one decode. Lookup alone is not a complete mix. Startup table parsing median: 0.267 ms.

## Reconstruction (CIEDE2000)

| Model | Mean | Median | P95 | P99 | Max |
| --- | --- | --- | --- | --- | --- |
| Reference + residual | 0 | 0 | 0 | 0 | 0 |
| Fast + residual | 1.19e-07 | 0 | 6.86e-07 | 1.17e-06 | 2.38e-06 |
| Reference palette only | 11.7 | 9.58 | 28.4 | 34.6 | 42 |
| Fast palette only | 11.8 | 9.65 | 28.4 | 35 | 42.3 |

## LUT mixture error against direct reference (CIEDE2000)

| Encoder | Mean | Median | P95 | P99 | Max |
| --- | --- | --- | --- | --- | --- |
| n17 | 0.706 | 0.184 | 2.55 | 10.9 | 43.8 |
| n33 | 0.409 | 0.0918 | 1.19 | 6.48 | 40.1 |
| n65 | 0.265 | 0.0631 | 0.774 | 4.19 | 36.7 |
| tri33 | 0.438 | 0.0994 | 1.38 | 6.93 | 40.5 |

The 33³ maximum discrepancy is 40.1 ΔE00: large outliers remain despite a low median. The raw palette mean error is 11.7 ΔE00. 8.42% of random mixtures require gamut mapping. The largest random-trajectory adjacent step is 6.42 ΔEOK100 at Δt=0.001. Numerical continuity does not imply gentle visual transitions.

## Reference checks

Cross-language f64 maximum linear-channel difference: 1.31e-13. f32-vs-f64 at 20 nm, including weight quantization: 3.2e-07. The 20 nm vs 5 nm fixed-recipe mean and P95 ΔE00 are 0.0826 and 0.149.

## Regeneration

`python3 tools/reproduce.py` runs the declared experiment suite; `cargo bench --bench mixing` runs a smaller standalone microbenchmark. Raw repetitions, generation cost, environment and worst examples are retained under `results/`. Compiler, system load, cache state and frequency affect timing; no cross-platform performance guarantee is made.
