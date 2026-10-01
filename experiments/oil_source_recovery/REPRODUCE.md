# Reproducing the inferred source recovery

This checkpoint preserves the investigation completed on 2026-10-01. The mapping
is inferred using the paper's aggregate results. It is not an author correction
or an independent accuracy test. The source archive and all older experiments
remain unchanged. `mapping.json` is the frozen input to later studies and must
not be overwritten when rerunning exploratory solvers.

## Inputs

Cache the following original files under `target/measured-oils/public-audit/`:

| File | Source | SHA-256 |
|---|---|---|
| `grillini-data.zip` | [Publisher supplement](https://mdpi-res.com/d_attachment/sensors/sensors-21-02471/article_deploy/sensors-21-02471-s001.zip) | `6d8cec6fb4fff5d4c24d18d1783422da8ef955d3e7ba7263179a84ed6c9b683e` |
| `grillini-paper.pdf` | [Author PDF](https://jbthomas.org/Journals/2021bSensors.pdf) | `cb49f755727a8b437f54dc55042b81b4b311b0e24848eacd3faf56cb34080a4e` |

The optional photograph for the initial geometry search is
`sensors-21-02471-g002.jpg`, Figure 2 of Grillini, Thomas and George (2021),
[Sensors 21, 2471](https://doi.org/10.3390/s21072471). Obtain the original JPEG
from the [Europe PMC supplementary bundle](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC8038140/supplementaryFiles).
It is needed only by `solve_pair_flips_column.py` / `align_photo.py`, not by fixed
map verification or the ambiguity audit. Photography is supporting evidence, not
a calibrated reflectance measurement.

The fixed map SHA-256 is
`9e31ac91fcaa334b8bc56e9d3ae501d7ebe79de932ca066dba84ba276f9d6a22`.
The unchanged importer verifies the ZIP hash before loading it. The PDF extractor
also checks its source hash. No source spectra or fitted coefficients are bundled.

## Commands

From the repository root, with Python, NumPy 2.3.5, SciPy 1.17.0,
colour-science 0.4.6 and Pillow installed:

```powershell
.\target\measured-oils\venv\Scripts\python.exe experiments/oil_source_recovery/verify_reconstruction.py
```

This evaluates the fixed map, checks the permutation, pures, reference means,
counts and independent scalar equations. It does not search labels.

The reference JSON was extracted with pdfplumber from the original vector PDF.
Run `extract_reference.py` with a Python environment containing pdfplumber to
repeat that extraction. No OCR or visual estimation of bar endpoints is used.

To repeat recovery, run `solve_pair_flips_column.py`, then
`check_reconstruction_ambiguity.py`, then `audit_pair_ambiguity.py`. These commands
overwrite their corresponding search JSON files, but not `mapping.json`.
Equivalent solver witnesses may differ between SciPy/HiGHS versions. Recorded
example alternatives are full coupled permutations, not instructions to flip
each pair independently. The audit tests conditional feasibility, not unrestricted
uniqueness. The selected seven pure indices and panel geometry are hypotheses
developed during the investigation, not automatically rediscovered by the solver.

`verification.json`, `mapping.csv`, and `comparison.csv` preserve the full original
study summary. Its confidence-interval widths remain unreproduced.
