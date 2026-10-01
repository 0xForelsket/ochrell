# Additional public three-paint measurements

**The best immediately usable extension is already in the full Old Holland
archive: 35 additional no-white ternaries across 25 paint combinations.** They
include substantially different concentration ratios, and every combination has
pure, white-tint and chromatic-binary calibration measurements. Their exact rows
and calibration pools are preserved in [next-cohort.json](next-cohort.json).

This audit inspects source coverage and provenance. No new optical model was
fitted or scored. The additional samples are outside our previous four-paint
selection, but come from the same experiment; they are not a wholly independent
external dataset.

## 1. Old Holland provides the missing ratio diversity

The [author's public archive](https://www.azadehasadi.net/paintdatasets.html)
contains 286 oil-paint recipes and matching 31-band spectra. The
[source paper](https://pure.mpg.de/rest/items/item_3285223_1/component/file_3285224/content)
describes weighed tube-paint mixtures on Arches oil paper, measured with an
X-Rite Color i7 and published with the specular component excluded.

The counts below come from directly parsing the numeric recipe file, not from
inferring mixtures from their appearance or counting spectra as distinct recipes.

| Coverage | Count |
|---|---:|
| No-white, exactly three-paint recipes in the full archive | 38 |
| Distinct no-white paint triples | 26 |
| Previously assessed in our selected four-paint palette | 3 rows: 172,174,176 |
| Additional no-white ternaries | **35** |
| Additional paint triples | **25** |
| Calibration rows per additional triple-plus-white palette | 25-39 |
| Distinct values of the previously tested gate, `27*c1*c2*c3`, in the additional set | 18 |
| Gate range in the additional set | 0.00066825-1.0 |

Each of the 25 additional palettes has all four pure paints, white tints, and
measurements of all three chromatic pairs. Binary support is uneven: a few pairs
have one recipe. This must be reported, not treated as equally strong calibration
for every pigment pair. The calibration cohorts include only pure/binary recipes;
all ternaries and higher-order mixtures are excluded from fitting.

Examples of new composition coverage, in the listed paint order:

| Paints | Source rows | Normalized ternary fractions |
|---|---|---|
| Lemon Yellow / Scarlet Lake / Alizarine Lake | 168,169,170 | 50:25:25; 80:10:10; 95:2.5:2.5 |
| Lemon Yellow / Alizarine Lake / Cobalt Blue | 178 | equal thirds |
| Lemon Yellow / Scarlet Lake / Ultramarine Blue | 191,193,195 | 90:5:5; 95:2.5:2.5; 99:0.5:0.5 |
| Cadmium Yellow / Alizarine Lake / Viridian Green | 218,220,222 | 75:12.5:12.5; 95.8333:2.0833:2.0833; 98.9583:0.5208:0.5208 |

The recipes can distinguish behavior near a binary edge from behavior near the
center of the three-paint simplex. That addresses a real limitation of the last
experiment, in which all three recipes had the same gate value. It does not
establish the attenuation rule's accuracy before it is tested.

The table uses archive paint names as aliases; the paper gives the fuller tube
names, including Alizarin Crimson Lake extra and Mixed White. These are three
**tube paints**, not necessarily three chemically pure pigments. A fresh palette
requires its own coefficients; the earlier yellow/red/blue coefficients cannot
be copied into a different selection merely because the paints have similar hues.

Full coverage: [families](old-holland-families.csv),
[individual ternaries](old-holland-ternaries.csv). The archive has no duplicate
normalized recipes at the 12-decimal grouping precision used in this audit.

## 2. Grillini adds pigment combinations, but not recipe shape

The [Grillini supplement](https://mdpi-res.com/d_attachment/sensors/sensors-21-02471/article_deploy/sensors-21-02471-s001.zip)
contains 7 pure recipes, 63 binaries and 105 ternaries. Direct recipe counts give
60 no-white ternaries across 20 chromatic triples. The Y/C/B study used three of
those, leaving **57** other no-white ternaries across 19 additional triples.

Every one has the same sorted fractions, 0.5/0.25/0.25. Thus every recipe has
gate value 0.84375. These observations could test transfer across pigment sets,
but cannot determine whether this gate has the right dependence on concentration.

All sample identities retain the limitations of the
[inferred reconstruction](../oil_source_recovery/REPORT.md). Seventeen of the
60 no-white target labels can change within the earlier 1e-5 conditional ambiguity
audit; calibration labels can change as well. Crucially, the seven projections
previously enumerated for Y/C/B/W do not exhaust alternatives for other palettes.
A new palette needs its own projected feasibility enumeration before scoring.
Do not treat the wider set as 57 author-confirmed new labels. The
[family table](grillini-families.csv) flags affected targets.

## 3. A seemingly new 289-spectrum oil dataset largely duplicates Old Holland

The [Mixed Integer Ink Selection repository](https://github.com/Navid-visual/Mixed-integer-ink-selection)
advertises 289 handmade oil-paint spectra in its
[dataset readme](https://raw.githubusercontent.com/Navid-visual/Mixed-integer-ink-selection/main/Dataset/README.md).
I downloaded its actual MATLAB array, not just the Git LFS pointer.

All **286** original Old Holland spectra have unique matches in this 289-row array,
with maximum spectral difference **1.11e-16**. This is floating-point equivalence,
not an independent 286-sample replication. The three remaining rows are 23,149,150
in the MATLAB array. The inspected repository does not provide an oil recipe
table identifying their ingredients or quantities, so they cannot currently be
used as three new ternary ground-truth observations.

The [row correspondence](duplicate-source-matches.csv) preserves the comparison.
This avoids accidentally presenting a derivative release as external validation.

## 4. Other public leads checked

The search included numeric archives where useful, publication metadata and
sample-preparation tables. It was a targeted search, not proof that no other
usable dataset exists.

| Source | What was checked | Suitability for this next test |
|---|---|---|
| [Pallipurath/Bath](https://researchdata.bath.ac.uk/183/) | Downloaded the reflectance archive and readme. Its 21 sample groups contain 3 pure groups, 14 binary groups and 4 layered groups, with repeated spectra. | No three-pigment mixture group. A paper discussing three colored pigments does not imply ternary recipes. |
| [Cutajar/Old Holland Library 2](https://zenodo.org/records/13359559) | Re-inspected the cached method PDF text and workbook. Mixture 21 combines cobalt, ultramarine and Prussian blue; the exported workbook includes a corresponding BL2 spectrum. | A relevant three-color mixture exists, but quantitative pigment ratios are absent from the inspected method table and workbook. Ageing/preparation differ. Not a calibrated recipe target yet. |
| [Reichert et al. 2025](https://pmc.ncbi.nlm.nih.gov/articles/PMC12283775/) | Inspected the full-text methods/table and [Figshare metadata](https://doi.org/10.6084/m9.figshare.28639103.v3). The raw archive is about 222 MB and was not needed for this screening. | The listed three-pigment system includes lead white, cinnabar and lead-tin yellow, in gum Arabic or egg glair on paper/parchment. It does not add the required oil/no-white chromatic ternaries. |
| [Tricas-Ranchal et al. 2026](https://doi.org/10.1016/j.dyepig.2025.113240) | Checked the primary publication's description of 8421 measured samples and its data-availability statement. | A substantial lead, but numeric data are offered on request, not as an inspected public download. It cannot be counted as available test data. No author was contacted. |
| [AI pigment classification, Sensors 2021](https://pmc.ncbi.nlm.nih.gov/articles/PMC8471921/) | Checked the publication and data-availability statement. | Includes a three-color mockup, but the measurement data are available on request. Not an immediately usable public recipe table. |
| [Wiersma painting tools](https://github.com/rubenwiersma/painting_tools) | Checked the current repository's sample preparation description. | Pure paint and pigment/white tint series; paintings do not supply weighed recipes for individual three-paint pixels. |

Bath's download record labels the inspected files CC BY 4.0. Figshare currently
returns version 3 and lists CC BY 4.0; the paper points to version 1. These are
recorded source facts, not a new decision to redistribute any dataset. Original
files stay in ignored research caches. Existing Old Holland release-term notes
remain in [the earlier reuse audit](../../docs/measured-oils-reuse.md).

## Recommended next test

Use the prepared **35-row / 25-palette Old Holland cohort** to compare the existing
K-M and empirical models, each newly calibrated on its palette's pure/binary data.
Keep all ternaries out of calibration. This directly tests whether the correction's
failure extends beyond the previous three Grillini recipes without first designing
another correction around the next answers.

The [next-study protocol](NEXT-STUDY.md) specifies the comparison, all calibration
rows, handling of known controls, and reporting by both sample and paint family.
The already-tested attenuation at fixed lambda=1 could be a secondary comparator;
its strength must not be retuned on these new targets. Most paint triples have
only one target, so the previous two-calibrate/one-assess scalar protocol cannot
be applied across the full cohort.

Do not merge datasets into one coefficient fit or pool their absolute scores:
Old Holland uses tube-paint masses, 400-700 nm and sphere measurements; Grillini
uses dry-pigment masses before binder, a different window and imaging geometry.
The wider Old Holland set improves coverage within an existing source, while a
truly independent external source remains a separate objective.

## Reproducibility

[audit.py](audit.py) verifies the original source hashes, all 35 unique selected
rows, fit/assessment disjointness and calibration support, the Grillini ratio
counts, the MATLAB duplicate correspondence and Bath group types. It contains
no optical-model fit or accuracy calculation. Pairing spectra across duplicate
archives is a provenance check, not a mixing-model evaluation.

The original source caches retain their prior paths. Additional small downloads
are under `target/measured-oils/ternary-source-audit/`, with URLs, sizes and SHA-256
hashes in [downloads.json](downloads.json). The audit's required additional numeric
inputs are `mixed-ink-oil.mat` and `bath-reflectance.tar.gz`; optional cached source
metadata are hash-checked when present. No multi-gigabyte image cubes were fetched.

```powershell
.\target\measured-oils\venv\Scripts\python.exe experiments/oil_ternary_sources/audit.py
```

[summary.json](summary.json) preserves the counts and provenance. No source table,
previous fitted coefficient, model default, renderer or paper implementation was
changed, and no new accuracy claim is made by this audit.
