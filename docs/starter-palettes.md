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
The subsequent [calibration diagnosis and one constrained revision](measured-oils-revision-results.md)
found negligible smoothing error and rejected the revision after it worsened
performance on the now-exposed evaluation mixtures. V1 remains the baseline.
A [chromatic-pair calibration study](measured-oils-v3-results.md) subsequently
improved conditioning and some pair predictions but worsened the multicolor
assessment. It also remains an exploratory result without runtime promotion.
A [three-agent experimental comparison](../experiments/oil_parallel/REPORT.md)
then found bounded empirical pair interactions most promising on the same
16 multicolor cases. The color-aware objective improved color at a spectral and
excluded-pair cost; the assumed finite-layer model was rejected. The empirical
candidate still fails the spectral screens, and reused samples do not supply
independent validation. No measured model has been promoted to the runtime.
A [grouped recipe assessment](../experiments/oil_grouped/REPORT.md) then excluded
each chromatic ratio and its white additions together. The empirical candidate's
mean color advantage persisted (2.893 versus 3.932 DE00 on the same 16 multicolor
samples), but the red/blue 1:1 group regressed and the spectral screens still
failed. All samples remain previously exposed; the runtime/default is unchanged.
The [red/blue diagnosis](../experiments/oil_red_blue/REPORT.md) separated the
parent correction from white-pair effects. Following the user's preference for
public measurements, a [second-palette test](../experiments/oil_external/REPORT.md)
retained the fixed algorithm but produced poor scores. A subsequent independent
spreadsheet read and source-baseline check raised unresolved consistency concerns;
the result remains provisional, with no relabelling, retuning or runtime promotion.
A [source-to-paper audit](../experiments/oil_source_trace/REPORT.md) checked all
seven published forward equations and 24 declared ordering/preprocessing cases.
None reconciled the reported baseline ranking. A subsequent [ordering reconstruction](../experiments/oil_source_recovery/REPORT.md)
recovered an inferred 175-sample mapping that closely reproduces the seven
published means and exactly reproduces the best/worst counts. These statistics
helped select the mapping, and some assignments vary under looser tolerances;
this is conditional source recovery, not author-confirmed ground truth. The
earlier external scores cannot establish generalization under the released
header pairing. The [frozen-method rerun](../experiments/oil_reconstructed/REPORT.md) now finds
26.9% lower mean spectral RMSE on twelve grouped ternaries. Its advantage remains
26.1-26.9% across all seven feasible selected-palette mappings in the tested
paired-scan family. Gains concentrate in white-containing mixtures: all three
Y/C/B ternaries without white worsen, and the mean windowed color advantage is
small and can reverse under mapping uncertainty. This supports continued research
under inferred labels; no measured preset, renderer or default is changed.
A [frozen component diagnosis](../experiments/oil_white_split/REPORT.md) finds that
calibration observes each pair correction alone, whereas chromatic ternaries
combine three. Two ternaries receive a correction in the wrong overall spectral
direction and the third overshoots, consistently across all seven mappings.
White-containing mixtures benefit from both chromatic and white-pair terms.
No single pair removal fixes all three failures. A proposed future revision would
need explicit ternary calibration; no revision was fitted in this diagnosis.
The approved [single attenuation experiment](../experiments/oil_ternary_attenuation/REPORT.md)
then calibrated one bounded strength on two chromatic ternaries and assessed the
excluded third, rotating exclusions across all seven mappings. Every fit selected
maximum attenuation. Mean excluded-target RMSE improved from 0.024189 to 0.017338,
but K-M remained better at 0.016568. Across mappings, the revision stayed 4.4-5.4%
worse than K-M. Pair and white-ternary predictions were exactly preserved. The
revision is retained as exploratory evidence and is not promoted to the runtime.
A [broader public-data audit](../experiments/oil_ternary_sources/REPORT.md) now
identifies 35 additional no-white Old Holland ternaries across 25 paint triples,
with varied ratios and complete pure/binary calibration support for each palette.
An unscored cohort and next-study protocol are prepared. Another 57 Grillini
ternaries expand pigment coverage but retain the same 2:1:1 recipe shape and
inferred-label caveats. A purported 289-spectrum oil source reproduces all 286
Old Holland spectra and cannot serve as an independent replication.
The [completed 35-ternary comparison](../experiments/oil_ternary_transfer/REPORT.md)
now shows that the original empirical correction improves mean spectral RMSE by
3.83% and mean windowed DE00 by 17.40% over K-M across the 25 additional palettes.
It improves 23 of 35 rows spectrally, while worsening p95 spectral error by 35.5%.
Fixed attenuation reduces that tail but is worse than the original correction in
mean spectral and color error. The earlier three-mixture failure does not justify
universal suppression. All 25 fits and excluded-target perturbation checks passed;
the next research target is the specific correction and base-model failures.
The [selected failure diagnosis](../experiments/oil_failure_cases/REPORT.md) now
traces row 205 mainly to a Scarlet/Alizarin darkening correction learned from a
binary spectrum that falls below both measured pure paints, which fixed-pure
opaque K-M cannot represent. Rows 197/199 require much lower effective red/green
blend weight against yellow than their frozen fit uses, beyond measured binary
ratio coverage. Other frozen palettes give strongly different yellow/viridian
scattering ratios. These are calibration-transfer/model-compatibility findings,
not proof of a physical cause or an optimizer failure. A pure/white-only base
calibration ablation is proposed; no refit was performed during the diagnosis.
The [completed pure/white base ablation](../experiments/oil_anchor_base/REPORT.md)
rejects that proposed global remedy. With the same pair-correction stage and all
35 targets retained, mean spectral RMSE worsens by 9.17% and mean windowed DE00
by 29.31% relative to the original correction. All three selected failures improve
spectrally but worsen in color; 22 of 35 targets regress spectrally. Spectral tail
errors fall, but equal-palette means also worsen. All 25 fits and isolation checks
passed, including exact reproduction of the archived pair controls when supplied
their original bases. The all-binary-base method remains the research baseline;
this exposed-data result adds no independent validation or runtime promotion.
The [unified Old Holland Eight study](../experiments/oil_unified_eight/REPORT.md)
then fits all eight paints jointly on 103 pure/binary samples and assesses the
remaining 183 mixtures. The empirical model improves mean spectral error by
5.04% and windowed color error by 22.01% over its shared K-M base, with residual
tail failures. On the established 35-target cohort it improves over the previous
palette-specific correction by 18.37% spectrally and 5.55% in color, using the
larger unified calibration pool. Both models now have local OPP3 packages on
the measured 31-band grid and verified native painting/replay. No measured
eight-ingredient sample exists in this source, no spectral tails were invented,
and no default or redistribution decision changed.
The [paired multicolor-calibration comparison](../experiments/oil_multicolor_calibration/REPORT.md)
then holds out complete chromatic-ratio families, including white additions and
binary parents, for both calibration approaches. Adding the other multicolor
measurements to the unchanged fitter lowers mean color error by 18.73% and
spectral RMSE by 16.84% on 183 excluded multicolor samples, with better primary
p95/max errors. Gains concentrate in white-containing mixtures: no-white mean
color error rises 3.65%, and the 50 excluded binary parents worsen by 7.33% in
mean color error and 35.02% in mean spectral RMSE. All 158 distinct fits and
excluded-measurement perturbation checks passed. These are pooled fold results;
the existing runtime packages remain unchanged while the calibration tradeoff
is retained explicitly in the research record.
The [balanced calibration follow-up](../experiments/oil_balanced_calibration/REPORT.md)
tests one fixed rule giving equal total fitting weight to four nonpure recipe
categories, with the same family exclusions and unchanged model/regularizers.
It retains 86.94% of expanded calibration's multicolor mean-color gain and
95.96% of its spectral gain. Binary mean DE00 falls from 3.4631 to 3.1725 and
no-white multicolor mean from 3.4828 to 3.2842, both below the binary-only
baseline. Primary multicolor mean DE00 rises from 2.8344 to 2.9197 versus
expanded calibration. Binary spectral RMSE remains 25.05% above binary-only
calibration, with individual and tail regressions retained in the report.
All 107 candidate fits, excluded-data refits and the independent CSV score audit
passed. This is a candidate calibration compromise for painting trials; no
final all-data model was fitted or runtime package changed in this comparison.
The subsequent [packaging and painting comparison](../experiments/oil_balanced_package/REPORT.md)
fits that fixed rule to all 286 measurements and exports local native OPP3
packages. The balanced corrected package is now the preferred local experimental
Old Holland Eight choice for recipe painting; the previous package is retained.
All 2,411 Rust/Python probes, six saved-job replays and fixed-recipe material
transport checks pass. Closest-found black is lighter (#292A30 versus #232225),
and mean error against 32 arbitrary RGB targets rises 7.32%; target reachability
is separate from measured-paint accuracy. Native decoding is about 1.02 us per
recipe and the 384x480 fixture paints in about 224 ms. No eight-paint LUT or
global-default switch is included; see the report's acceleration discussion.

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
