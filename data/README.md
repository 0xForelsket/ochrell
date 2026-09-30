# Data, constants, licenses and provenance

No Mixbox implementation artifact or commercial pigment measurement is present.

* `cie_380_780_1nm.csv`: CIE 1931 2° observer and D65 daylight, extracted from **Colour 0.4.6**. Observer values sampled at 1 nm; D65 is the package's 5 nm table linearly interpolated to 1 nm. Truncated to 380–780 nm. This is **not** a byte-identical copy of the current official CIE 1 nm files. `model_manifest.json` records the SHA-256 of our exact subset.
* Observer attribution: CIE 2019, *Colour-matching functions of CIE 1931 standard colorimetric observer*, DOI https://doi.org/10.25039/CIE.DS.xvudnb9b . Official full-file SHA-256, not our subset: `fa663e3535a7e0763a745993a1f0a192eb0275ac46ad2d1befd7626841e713c1`.
* Illuminant attribution: CIE 2019, *CIE standard illuminant D65*, DOI https://doi.org/10.25039/CIE.DS.hjfjmt59 . Official full-file SHA-256, not our subset: `e76f210bffff3d552ef7113025da5f325d5dfec200dd4b878b1a2f3a507032cb`.
* CIE metadata states **Creative Commons Attribution-ShareAlike 4.0 International**, https://creativecommons.org/licenses/by-sa/4.0/ . Retain attribution and change notices when redistributing this subset. `COLOUR-LICENSE` retains the transport package's BSD-3-Clause notice. No endorsement by CIE or Colour is implied.
* `src/generated.rs` contains separately identifiable synthetic absorption/scattering arrays and CIE-derived color integration weights. The latter, generated LUT assets, and derived numerical/figure data are distributed under CC BY-SA 4.0 conservatively as derived data. Source algorithms remain MIT OR Apache-2.0. The entire artifact is therefore not solely MIT-licensed.
* `config.toml [model]`: all synthetic pigment parameters are original design constants, not fitted from measurements. Blue cutoff was chosen from [490,510,530] nm; yellow from [490,510,530,550] nm using recorded canonical trials. Width 22 nm, floor 0.025, ceiling 0.94, red edge 600 nm were initial heuristic choices. S=8 white, S=1 chromatic, S=0.5 black are relative strength priors, not material coefficients with measured units. Their consequences are tested in ablations. There is no source-compatibility claim with any commercial mixer.
* `default.lut`, `lut-*.bin`: generated solely by this repository's Rust solver from the above model. Header `PMX1`, little-endian u32 resolution, then resolution³ records of eight little-endian f32 concentrations. Order: red outer, green middle, blue inner. Generator rejects resolutions outside 2–129. Decoder validates length, finite nonnegative entries, and simplex sums. The format is not a general user-supplied model format: the palette must match the compiled decoder.

The matrix values in `conversion.rs` are the publicly documented sRGB and OKLab definitions, not fitted project coefficients. The reciprocal K–M form is derived algebraically. Solver damping (1e-5), objective improvement threshold (1e-13), line-search cap (16) and near-zero derivative guard (1e-12) are numerical safeguards; their legacy role is described in `docs/legacy/math.md`.

## Version 0.2 additions

`optical_basis.csv` and `src/optical_generated.rs` are produced by `tools/optical_model.py` using only the above CIE-derived quadrature and the declared anchor-fit objective. Primary spectra are fitted independently; complementary spectra and neutral anchors are derived algebraically. `results/revision/generation.json` contains optimizer records and the exact basis checksum. `docs/coefficients.md` explains every new design parameter. These generated data assets retain the CC BY-SA 4.0 attribution/change notice. Original generator/runtime code is MIT OR Apache-2.0.

The earlier LUT assets and synthetic palette remain for legacy reproduction and are not used by the new default mixer. The scattering normalization and white-strength parameter in v0.2 are mathematical priors, not measured paint properties. External engine observations live outside `data/` and are never inputs to model generation.

## Experimental Synthetic Four palette

`palettes/synthetic-four-v1.json` contains original analytic reflectance/strength
definitions for the opt-in recipe reference. They are not measured paints and
are not fitted to the Old Holland dataset, Mixbox, Spectral.js or the legacy
palette. `tools/generate_palette.py` combines these definitions with the existing
CIE CSV to generate `src/palette_generated.rs` and the adjacent palette manifest.

The original JSON definitions and generator code use MIT OR Apache-2.0. The
CIE-derived projection and combined generated data asset retain CC BY-SA 4.0
attribution and change notices, consistent with the existing distribution.
The manifest records source hashes and a palette fingerprint; no new external
measurement is bundled. See [the reference contract](../docs/palette-reference.md).

Prepared forward LUTs generated from this reference use the same combined-data
attribution and CC BY-SA 4.0 terms. No binary LUT is bundled in this stage; the
host can generate and save one through `palette_lut::PaletteLut`. Its payload
retains the exact palette fingerprint; see [format and results](../docs/palette-lut.md).
