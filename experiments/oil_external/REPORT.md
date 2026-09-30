# External measured-palette test: poor scores, unresolved source compatibility

**The frozen method does not demonstrate useful transfer on the supplied
tables. Both models have large spectral errors. A post-fit source check also
raises an unresolved consistency concern, so this is a provisional compatibility
result, not a clean verdict on generalization to correctly identified paints.**
All scores, failures and source bytes are retained. Nothing was relabelled,
removed, retuned or promoted to the runtime.

The user chose existing public measurements. After a structural audit, we used
the public supplement to [Grillini, Thomas and George (2021)](https://doi.org/10.3390/s21072471).
It contains 175 measured samples and concentration labels. The
[audit](../oil_public_data/REPORT.md) records retrieval, identity and provenance.
The [plan](PLAN.md) froze a single four-material palette, spectral grid,
grouping and unchanged optimizer before this dataset's model-error assessment.

## Protocol

The 34-sample subset uses Naples Yellow, Carmine, Ultramarine Blue and Kremer
White. Published concentrations describe pigment mass before binder addition,
not Old Holland tube-paint mass. Measurement geometry and preparation also differ.
Only the model family and settings transfer; optical coefficients are refitted
separately to the new calibration samples.

Four pure samples and nine white tints are calibration anchors. The training
pool adds nine chromatic pairs. Each nominal chromatic ratio and all its white
additions are excluded together: nine 21-row fits and one shared 22-row fit cover
twelve groups. All twelve ternary samples remain outside every training fit.
Grouping follows nominal label ratios; the fitter retains the spreadsheet's
0.33/0.67 fractions. That avoids accidentally separating nominally identical
parent/tint ratios because the spreadsheet rounds only some of them.

The paper trims ten bands per edge. Its supplied table retains all 186 bands;
we applied the stated trim, then interpolated strictly inside retained support
onto 31 bands at 440-740 nm. **Spectral RMSE is the primary metric.** Color
differences below use only that window with its own D65/2-degree white; they
are not full-visible color errors and cannot be compared numerically with our
400-700 nm Old Holland scores. No missing wavelengths were invented.

## Results using the tables as supplied

Each empirical model is compared with its own fold's K-M base, trained on the
same rows. RMSE is on reflectance 0-1; smaller is better.

| Grouped assessment | K-M mean RMSE | Empirical mean RMSE | K-M p95 RMSE | Empirical p95 RMSE |
|---|---:|---:|---:|---:|
| 12 ternaries (primary) | 0.12257 | 0.12189 | 0.24504 | 0.19627 |
| 9 chromatic pairs | 0.13663 | 0.15202 | 0.36288 | 0.34618 |
| All 21 | 0.12860 | 0.13480 | 0.25856 | 0.20851 |

The primary mean improves only about 0.56%; six ternaries improve and six worsen.
Across all 21, mean RMSE worsens about 4.82%, with ten improvements and eleven
regressions. Some spectral tails improve while means/medians and other cases
worsen. The worst empirical RMSE is 0.43795 for `bC` (nominal B:C=1:2), compared
with its K-M baseline's 0.48045. This is still a very poor prediction.

| Windowed color diagnostic only | K-M mean DE00 | Empirical mean DE00 |
|---|---:|---:|
| 12 ternaries | 16.042 | 14.933 |
| 9 chromatic pairs | 21.830 | 23.439 |
| All 21 | 18.523 | 18.578 |

When all nine parents are available, the same twelve ternaries have mean RMSE
0.12263 for K-M and 0.12426 for the empirical model. Thus the poor result is not
solely introduced by removing each related parent. These numbers do not justify
expanding the correction or loosening bounds against this dataset.

## Source consistency concern discovered after scoring

The labels in the two spreadsheets align, and all data are finite. However,
those checks alone do not establish that the columns semantically represent
the intended physical samples:

- The column labelled pure `W` is 0.11205 reflectance at 548.99 nm, while the
  column `bC` is 0.47529 at the same band. The concentration table marks `W` as
  100% white. This is unusual enough to require further source interpretation;
  it is not, by itself, proof of a mislabeled column.
- An independent `openpyxl` read matches every label, concentration, wavelength
  and reflectance value from our XML reader exactly. The low-white observation
  is present in the published workbook, not introduced by that reader.
- All 30 selected mixtures exceed their ingredients' measured pure spectral
  envelope somewhere by more than 0.001. That cutoff is descriptive, not a
  noise estimate. Preparation/opacity differences can violate our opaque
  fixed-pure assumptions; this check does not uniquely identify a data defect.
- We also reconstructed four parameter-free forward models from the paper
  using all seven labelled pure spectra, the published concentrations and the
  same ten-band edge trim. Our M2 geometric model is slightly worse than M1
  additive, whereas the paper's Figure 6 shows M2 substantially better. M6's
  ordering also differs. This is a comparison of the published graph's ordering,
  not a claim to have reproduced an exact numerical table.

| Source-baseline reconstruction | MSE, all 175 | MSE, 168 mixtures only |
|---|---:|---:|
| M1 additive | 0.022057 | 0.022976 |
| M2 geometric | 0.022949 | 0.023906 |
| M6 LIP additive | 0.021850 | 0.022761 |
| M7 LIP subtractive | 0.022680 | 0.023625 |

Different original endmember extraction, preprocessing, sample identity or
unreported preparation could contribute. We have not isolated the cause.
No permutation search or visually guessed relabelling was attempted. These
post-hoc checks qualify interpretation; they do not erase the recorded negative
result or turn this run into a new prespecified source-screening experiment.
See [source-consistency.json](../oil_public_data/source-consistency.json) and
[independent-reader-check.json](../oil_public_data/independent-reader-check.json).

## Numerical verification

All 30 K-M optimizer starts and ten empirical fits converged. This was much
harder than Old Holland: 108-1491 evaluations per K-M start, and 7-10 K-M
variables at bounds per start. Empirical fits took 10-12 evaluations and had
6-11 of 24 controls at bounds. Recorded K-M optimizer time totals 79.912 seconds;
this says nothing about renderer throughput. Bounds were not relaxed.

Independent scalar decoding agrees within 3.7e-15 reflectance across all ten
models and 34 recipes; pure drift is at most 5.6e-17. Every prediction is finite
and bounded. Actual refits after changing all excluded target spectra reproduce
every fitted coefficient exactly. The truncated perfect-diffuser Lab check and
the rounding-aware red/blue group checks also pass. Source and implementation
hashes are preserved. These checks establish numerical reproducibility, not
correct material identification or applicability of the optical assumptions.

The initial fit ran asynchronously. Early verify/evaluate invocations stopped
before scoring because the frozen bundle did not yet exist. After completion,
evaluation and verification ran against the complete immutable bundle. No
partial fits or numbers from those failed invocations enter this report.

Bundle SHA-256:
`6598ad6eea3288d830c1d301b5e98a1394474cc9d9545a8f9c4a742afa2a9406`.

[Summary and optimizer metadata](summary.json), [per-row errors](errors.csv),
[verification](verification.json).

## Decision and next work

Keep the Old Holland improvement as dataset-specific exploratory evidence.
The external run supplies no robust positive evidence of transfer. Resolve the
external source/baseline discrepancy using public supporting material before
calling its scores an independent real-paint accuracy verdict. Preserve the
existing negative result. Do not tune the model to these columns or pool the
two palettes. No author was contacted; runtime, paper and default stay unchanged.

Reproduction from the repository root (use a fresh output directory for fits):

```powershell
& target/measured-oils/venv/Scripts/python.exe experiments/oil_public_data/fetch.py
& target/measured-oils/venv/Scripts/python.exe experiments/oil_public_data/audit.py
& target/measured-oils/venv/Scripts/python.exe experiments/oil_external/run.py prepare --out target/measured-oils/grillini-repeat
& target/measured-oils/venv/Scripts/python.exe experiments/oil_external/run.py fit --out target/measured-oils/grillini-repeat
& target/measured-oils/venv/Scripts/python.exe experiments/oil_external/run.py evaluate --out target/measured-oils/grillini-repeat
& target/measured-oils/venv/Scripts/python.exe experiments/oil_external/run.py verify --out target/measured-oils/grillini-repeat
& target/measured-oils/venv/Scripts/python.exe experiments/oil_public_data/check_source_consistency.py
```

Raw source, native spectra and fitted coefficients stay in ignored target output.
Evaluation/verification refresh the derived score files but never overwrite a
frozen coefficient bundle. No physical measurement acquisition is required.
