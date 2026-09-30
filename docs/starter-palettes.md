# Starter palettes: selected research tracks

Decision date: 2026-09-30. The user accepted the research recommendation to start
with the four-tube Old Holland oil subset and an independent synthetic baseline.
This refines the [product direction](product-direction.md). Neither is a shipped
palette yet; preparation, validation and a default change remain separate steps.

Implementation update: [Synthetic Four](palette-reference.md) has a direct
reference and recipe persistence. The first [measured oil study](measured-oils-results.md)
has now fitted the 21 designated samples and evaluated the 24 holdouts without
retuning. It improved predictions but failed its predeclared quality screen.
Dataset redistribution terms remain unresolved; no measured preset is bundled.

## Selected candidates

| Priority | Working name | Materials | Role |
|---|---|---|---|
| 1 | Modern Oils Four | Old Holland Scheveningen Yellow Lemon, Scarlet Lake extra, Cobalt Blue, Mixed White | First measured research candidate for a four-material reference and accelerated decoder |
| 2 | Synthetic Four | Independently specified yellow, red, blue and white materials | Baseline for recipe APIs, generation, persistence and performance without depending on the measured dataset |
| Later | Monet-inspired Modern Oils Eight | The full eight-tube Old Holland study palette | Larger-palette research after the four-material workflow is validated |

These are working names, not public format identifiers or manufacturer
endorsements. The synthetic materials must have their own declared optical
properties, without claiming to reproduce the named Old Holland products.
Measured spectra, fitted coefficients or outputs must not leak into the
independent synthetic fit. The existing legacy palette's failures remain
acceptance cases; synthetic does not mean automatically restoring that palette.

The full eight-paint study includes additional yellow, red, blue and green
materials. Its modern interpretation is described as Monet-based by the authors;
our four-paint subset is neither the full study palette nor Monet's historical
palette. Historical presets need a named period and documentary source. See the
[National Gallery study](https://www.nationalgallery.org.uk/technical-bulletin/roy2007).

## Measured source and audit

Source: Asadi Shahmirzadi, Babaei and Seidel, *A Multispectral Dataset of Oil and
Watercolor Paints* (2020).

- [Author's dataset page](https://www.azadehasadi.net/paintdatasets.html)
- [Author-hosted paper](https://www.azadehasadi.net/publication_files/multispectralPaintDataset.pdf)
- [Dataset ZIP](https://www.azadehasadi.net/publication_files/spectralDatasets.zip)

The oil dataset contains reflectance spectra and weighed ingredient portions,
not ready-made absorption/scattering coefficients. It describes dried oil-paint
swatches on Arches oil paper and specular-excluded X-Rite Color i7 measurements.
Use the paper's full paint names and the archive readme's column order together.
Mixed White contains zinc and titanium white; do not substitute a generic white.

The initial source audit inspected the archive in memory on 2026-09-30. The
subsequent measured-reference study uses ignored local research output; no
measurements or fitted coefficients are bundled. The initial audit verified:

| Item | Result |
|---|---|
| Archive size | 64,147 bytes |
| `oilspectra.txt` | 286 rows, 31 samples per row; 400-700 nm in 10 nm steps |
| `oilmixtureportions.txt` | 286 matching rows, eight ingredient columns |
| Selected columns, one-based | 1, 3, 5, 8 |
| Subset rule | Keep rows whose unselected ingredient portions are all zero |
| Retained rows | 45 |
| Ingredient counts | Four singles, 25 pairs, 13 triples, three four-material mixtures |
| Basic data checks | Finite reflectances in [0,1]; finite nonnegative portions; positive total portions |
| Duplicate normalized recipes | None at 12 decimal places in this subset |

Retain the source row relationship between spectra and portions. Normalize the
recorded mass portions when forming recipes; do not reinterpret them as volume
fractions. The original eight-column order is part of the source identity.

Checksums identify the inspected bytes; they are not a data license or a claim
that later downloads cannot change.

```text
SHA-256 spectralDatasets.zip
cda35e5ab968bb18a05127c1b9fb0b2bd3c4a4bb88d4bf4ae1e4b2bb5de07538

SHA-256 readme.txt
3ae32534a6ac43746f9338190fb182d06e7d9dfdf30d84b4fa55fc3a6ee13ea3

SHA-256 oilspectra.txt
11436afe638351193eef2dbc87167ab0981464e170f4fd7e6106668adf85fc5b

SHA-256 oilmixtureportions.txt
e968f8384f2ee03dcc16d34f87f895bf61cd63a67a4af99550d6144d0b1995ce
```

## Data-rights status

The author page and archive readme do not state a dataset license, and the
inspected archive contains no license-named member. The article's publication
terms alone do not establish the terms for its separate data archive. The
research candidate is selected; redistribution of measurements or fitted
artifacts is unresolved, not approved by that selection.

Explicit terms covering the source data and derived coefficients/LUTs would help
resolve release uncertainty, including commercial use and attribution. The
[subsequent audit and correction](measured-oils-reuse.md) distinguish that
precaution from an established legal requirement: missing terms alone do not
demonstrate that permission is necessary for our independently implemented model.
Keep any eventual clarification with provenance. No author has been contacted.

If the needed terms cannot be established, proceed with the independent
synthetic track and evaluate other measured sources. Do not describe the
synthetic baseline as calibrated to the selected tube paints.

The Wiersma dataset is not selected for an unrestricted bundled preset: its
[data terms](https://github.com/rubenwiersma/painting_tools) are CC BY-NC-SA 4.0,
separate from the code's MIT license. RIT's measured acrylic palette remains an
alternative pending recovery of the workbook and clarification of its terms;
neither alternative replaces the selected oil candidate automatically.

## First measured-reference experiment

The purpose is to assess whether a declared homogeneous K-M model predicts this
subset before accelerating it. The following partition was frozen before the
first fit and is retained here as its design record:

| Role | Source mixtures | Rows |
|---|---|---:|
| Fit | Four pure tube paints | 4 |
| Fit | Yellow + white | 5 |
| Fit | Red + white | 6 |
| Fit | Blue + white | 6 |
| Holdout | Yellow + blue, yellow + red, red + blue | 1 + 5 + 2 = 8 |
| Holdout | Three-material mixtures | 13 |
| Holdout | Four-material mixtures | 3 |
| Total | 21 fitting rows and 24 holdout rows | 45 |

Define positive relative K/S with a documented scale convention and fitting
objective. Opaque reflectance does not identify absolute K and S separately;
do not label fitted values measured coefficients or infer absolute thickness
from them. Treat layer opacity, surface correction and substrate influence as
assumptions to examine, not facts established by the RGB appearance of a swatch.

Declare regularization, stopping criteria and numerical/physical error measures
before running the fit. Tune using fitting data or splits within it. Keep the
24 holdout mixtures out of fitting and candidate selection. If their results
motivate a revised model, retain the failed result and acknowledge that this
holdout is no longer independent for the revision.

Evaluate spectral error on the measured 400-700 nm range and color error under
declared observer/illuminant conventions. Do not silently pad the missing
380-390 or 710-780 nm bands to reuse v0.2's grid. A truncated colorimetric
evaluation or an extrapolation requires its own stated policy and limitations.
Report each mixture family, means, tails and worst cases rather than one score.

The dataset has sparse and uneven ratio coverage, particularly yellow/blue.
Passing these cases would support a limited result for these preparations, not
every mixture, current tube batch, wet paint interaction or historical painting.
Further physical measurements would strengthen validation if needed.

## Synthetic baseline and acceleration sequence

Specify four original synthetic materials with a reproducible generator and
explicit strength/white assumptions. Use the palette reference API and test
the same recipe, tint, grouping, tiny-update and persistence semantics planned
for measured palettes. Maintain the existing CIE attribution where that data
is used. Freeze a synthetic palette version before producing its accelerator.

For each usable palette, compare its direct reference with independently
generated forward-decoder candidates. Declare approximation budgets and use
fresh recipe samples, including boundaries and long update sequences. Measure
generation, validation, load time, artifact size, state size and complete brush
workloads separately. These numerical tests do not replace physical validation.

Start recipe-based painting without an exhaustive RGB encoder table. Add the
optional target-color solver against the selected palette, returning both the
recipe and achieved color/error. Cache compatible prepared mixers. Measure
whether a four-material LUT is the best runtime choice rather than assuming it.

The next implementation plan should make these inputs concrete: data terms for
the measured track, synthetic definitions, reference equations and spectral
range, fit objective, numerical budgets, and versioned palette/state contracts.
The current spectral mode, frozen papers, default API and renderer stay intact
while this separate palette capability is developed.
