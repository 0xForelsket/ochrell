# Benchmarks and numerical results, v0.2

Generated from `results/revision/`. Both versions use the same current-run samples and machine; historical v0.1 timings remain in `paper/legacy`. No results are real-paint accuracy measurements.

| Operation | Median ns | Million/s |
| --- | --- | --- |
| sRGB | 15.6 | 64 |
| linear RGB | 148 | 6.75 |
| OKLab | 272 | 3.67 |
| v0.1 RGB | 572 | 1.75 |
| v0.2 RGB | 719 | 1.39 |
| v0.2 cached | 229 | 4.37 |
| v0.2 reference | 1.87e+03 | 0.534 |
| v0.1 cached | 182 | 5.5 |

AMD EPYC 9V74 80-Core Processor; rustc 1.75.0 (82e1608df 2023-12-21) (built from a source tarball); release, single thread, LTO off, codegen-units=1. Seven repetitions of 100,000 operations. Complete RGB timings include two encodes and one display decode; cached timings omit encodes. Full new RGB mixing is slower than the old LUT model, while the new reference avoids nonlinear inversion.

## Reconstruction (CIEDE2000)

| Reconstruction | Mean | Median | P95 | P99 | Max |
| --- | --- | --- | --- | --- | --- |
| v0.2 corrected | 1.27e-06 | 4.91e-07 | 4.84e-06 | 7.45e-06 | 1.79e-05 |
| v0.2 raw | 0.072 | 0.0341 | 0.272 | 0.517 | 0.85 |
| v0.1 raw | 11.5 | 9.2 | 28.6 | 35.7 | 42.1 |

Corrected accuracy follows from the residual identity and does not validate inferred material. Raw error is substantially smaller, but the spectral floor still limits dark colors.

## Fast/reference approximation

| Spacing (nm) | Mean | P95 | Max |
| --- | --- | --- | --- |
| 1 | 0.026 | 0.0861 | 0.268 |
| 5 | 0 | 0 | 0 |
| 10 | 0.00352 | 0.013 | 0.0999 |
| 20 | 0.087 | 0.341 | 2.35 |
| 40 | 0.849 | 2.84 | 10.5 |

This table changes wavelength sampling in f64 while holding the fitted spectra fixed. The 1 nm row interpolates the 5 nm spectra. Actual f32 fast/reference mean, P95 and max: 0.00352, 0.013, 0.0999 ΔE2000. Same-grid float32/Python mean: 5.83e-06. Promoted decoder max channel error: 3.44e-07.

## Quality diagnostics

Held-out green-dominant fraction: 38.4% → 80.8%. Common-set tint hue P95: 35.6° → 10.4°. Random max adjacent ΔEOK100: 1.59 → 1.17; P99 did not uniformly improve. Pure-black first tint step remains 10 at Δt=.001, comparable to linear RGB 10.

## External comparisons

Mean difference from 39 Mixbox JPEG observations: 13.5 → 6.92 ΔE2000. Mean difference from 5,213 Spectral.js 3.0 API samples: 13.1 → 6.49. These are similarity measures only. No external outputs were fitting targets.

## Reproduce

`python3 tools/reproduce.py`. Raw repetitions, exact seeds, configurations, inputs, outcomes and environment are bundled. The new default has no runtime LUT parse; construction is a zero-sized value. Its 340-byte latent is larger than the 44-byte legacy latent.
