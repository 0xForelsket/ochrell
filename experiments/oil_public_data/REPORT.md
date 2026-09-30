# Public measured-paint source audit

Audited 2026-09-30 after the user chose existing public measurements. Select the
Grillini supplementary tables for a separate fixed-method transfer test. They
provide actual oil-paint mixture observations and recipe concentrations. They
are a different palette and cannot validate or augment the Old Holland
coefficients without changing what those coefficients represent.

**Subsequent qualification:** the first external run produced poor scores, and
post-fit checks raised unresolved source/baseline consistency concerns. The
structural checks below still pass; they do not establish semantic sample
identity. Read the [external results](../oil_external/REPORT.md) before treating
this source as a validated benchmark. No data or labels were repaired.
The [subsequent trace](../oil_source_trace/REPORT.md) confirms that the tested
equations and preprocessing alternatives do not resolve the discrepancy; the
original scan-to-sample mapping and reference endmember inputs remain needed.

## Selected source and inspected files

[Grillini, Thomas and George (2021)](https://doi.org/10.3390/s21072471) studied
Kremer pigments mixed with linseed oil. The paper describes 175 samples, pigment
mass proportions and hyperspectral measurements. Its
[author-hosted copy](https://jbthomas.org/Journals/2021bSensors.pdf) identifies the
materials and acquisition setup. The supplemental tables were obtained through
the [Europe PMC public supplementary-files service](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC8038140/supplementaryFiles).

The supplied archive was inspected, not merely identified from a search result:

- `mockups_concentration.xlsx`: seven pigment-fraction rows and 175 sample labels.
- `mockups_reflectance.xlsx`: matching labels, 186 native bands, 405.37-995.83 nm.
- The concentration row order was recovered from the pure samples and checked
  against every sample label. The tables align exactly; normalized recipes are
  unique, fractions sum to one, and reflectances are finite and inside (0,1).
- Binary 2:1 recipes are stored as 0.67/0.33. Their maximum difference from the
  nominal label ratios is 0.003333. Fitting must preserve stored values while
  grouping nominal parent/tint families consistently.
- The paper omits ten noisy bands per edge, leaving support 437.29-963.91 nm.
  A 440-740 nm, 31-band interpolated grid requires no extrapolation. Color scores
  over that restricted window must not be labelled full-visible color accuracy.

The selected Y/C/B/W subset has 34 samples: four pure, nine white tints, nine
chromatic pairs and twelve ternaries. It uses Naples Yellow 43125, Carmine 23403,
Ultramarine Blue 45030 and Kremer White 46360. This is a metadata/coverage choice,
made before any fitted-model error was calculated for this dataset. The
[audit code](audit.py) and [machine-readable audit](audit.json) retain checksums,
identities and counts; raw spreadsheets remain under ignored target output.

Archived supplementary-data ZIP SHA-256:
`6d8cec6fb4fff5d4c24d18d1783422da8ef955d3e7ba7263179a84ed6c9b683e`.
The outer Europe PMC download includes figures as well as that ZIP; its SHA-256
is `1a412a6b0c76a55db9d70a2a861a43e8c1e69afbb7b60628327454aa3e2187d3`.

## Other inspected sources

| Source | What it offers | Decision for this question |
|---|---|---|
| [Asadi Old Holland archive](https://www.azadehasadi.net/paintdatasets.html) | The current measured tube-paint recipes | Full-file audit still finds only four observations combining our red and blue with optional white; no extra trajectory data hidden outside the four-paint subset. |
| [Cutajar et al., Old Holland Library 2](https://zenodo.org/records/13359559) | Public oil-paint spectra and preparation variations | Downloaded its 6.6 MB workbook and method PDF. The material table has cobalt blue but not the selected Scarlet Lake / Mixed White combination; its listed mixtures do not provide our red/blue ratio series. Different application and ageing conditions also matter. |
| [Wiersma painting tools](https://github.com/rubenwiersma/painting_tools) | Historical pigment oil paintouts, pure and white-tinted samples, with preparation metadata | Useful for separate optical/preparation studies. The described paintouts use pure, 1:1 and 1:2 pigment:white conditions, not a chromatic red/blue mixture series. Data and code have separate license terms. |
| [RIT Artist Paint Spectral Database](https://www.rit.edu/science/sites/rit.edu.science/files/2019-03/ArtistSpectralDatabase.pdf) | Acrylic characterization and a 770-spectrum palette | The palette's mixtures are computationally generated. They cannot serve as independent real-mixture ground truth for choosing between mixing models. |
| [Golden supplied spectra](https://www.realtimerendering.com/golden.html) | Measured pure acrylic paints and K/S data | Useful material references, but not the missing observed red/blue mixtures. |
| [Bath pigment-mixture archive](https://researchdata.bath.ac.uk/183/) | Measured spectra from a separate historical-pigment mixture/layering study | Different target pigments; not a direct continuation of this Old Holland red/blue investigation. Not downloaded or fitted in this audit. |

Cutajar workbook SHA-256:
`d521c918e54b4e0de6ceeec175afe3190d895b41a108f56ff280af67de4467db`.
Method PDF SHA-256:
`a2cf41edb87c5f0e41109c968be48ae4915b5fe97db9c71c8368d86876dc3d90`.
The PDF's material table was visually checked against its extracted text.
No multi-gigabyte hyperspectral image archives were downloaded.

## Boundaries of the selected test

The new source uses pigment mass before binder addition and 45/0 imaging of
paint on prepared canvas, whereas the earlier source records tube-paint mass
and sphere measurements of paper swatches. This audit supports a test of the
same algorithm on a separately calibrated palette; it does not make the spectra
interchangeable or supply the missing physical metadata for Old Holland.

The external test's [plan](../oil_external/PLAN.md) freezes preprocessing,
palette selection, grouping and model settings before scoring. Its
[results](../oil_external/REPORT.md) are separate from this file audit.

Reproduce the audit with the already-downloaded source:

```powershell
& target/measured-oils/venv/Scripts/python.exe experiments/oil_public_data/audit.py
```

No author was contacted and no new data was measured or added to a shipped
preset. Public source files remain research inputs under ignored target output.
