# Finite-layer KM: reject this candidate

The assumed white-backed finite layer improves calibration spectral fit but
worsens multicolor color prediction. Keep v1 as the research baseline. This is
exploratory evidence on previously exposed rows, not independent validation.
No existing fit, runtime, renderer or paper was changed.

The [pre-fit plan](PLAN.md) declares one model, fixed starts and limits; there
was no diagnostic ablation or assessment-driven retuning. We assumed ideal
white diffuse backing, common application thickness and absent surface
reflection. These are not archive measurements. The effective optical
thickness is expressed in the S_white=1 gauge, never physical millimeters.
Finite-layer K/S is inverted from each measured pure spectrum, so the
four measured endpoints remain exact. The model has 94 fitted parameters,
one more than v1/v3. Its pure constraints cannot validate physical coefficients.

All metrics use identical 31 bands, 400–700 nm, truncated D65/2-degree Lab and
CIEDE2000 with no clipping. RMSE/MAE are means of per-row reflectance errors.

| Assessment / metric | V1 | V3 | Finite layer |
|---|---:|---:|---:|
| Multicolor 16: mean RMSE | 0.026386 | 0.028495 | 0.028161 |
| Mean MAE | 0.023283 | 0.024908 | 0.024469 |
| P95 RMSE | 0.061668 | 0.060696 | 0.060923 |
| Worst single-band error | 0.102395 | 0.102132 | 0.102119 |
| Mean DE00 | 3.6771 | 3.9150 | **4.5300** |
| Median DE00 | 3.0027 | 3.1367 | 3.1135 |
| P95 DE00 | 6.5613 | 7.9419 | **10.2117** |
| Maximum DE00 | 6.9807 | 8.2224 | **12.5868** |
| Whole-family excluded pairs 8: mean RMSE | 0.026685 | 0.033587 | 0.036455 |
| Mean MAE | 0.020459 | 0.024438 | 0.025835 |
| P95 RMSE | 0.049538 | 0.055704 | 0.056988 |
| Worst single-band error | 0.153467 | 0.174309 | 0.181593 |
| Mean DE00 | 4.0123 | 3.7233 | 4.0139 |
| Median DE00 | 3.9014 | 3.7015 | 3.7893 |
| P95 DE00 | 6.5604 | 6.3909 | 6.5727 |
| Maximum DE00 | 7.2240 | 6.9476 | 7.2145 |

Pairs use three separate fits, excluding all five Y/R, one Y/B or two R/B
rows respectively. The pooled pair results are not one deployable palette.
The primary model fitted 29 rows and excluded all 16 multicolor rows.
Calibration mean RMSE improves from v3's 0.017948 to 0.017439, while mean
calibration DE00 worsens from 2.0981 to 2.1576. All five original numerical
screens fail on the 16-row finite-layer assessment, including maximum DE00.

| Family (count) | V1 mean DE00 | V3 mean DE00 | Finite mean DE00 |
|---|---:|---:|---:|
| Y/R, excluded (5) | 3.1448 | 2.8296 | 3.2400 |
| Y/B, excluded (1) | 4.6120 | 4.0113 | 4.5013 |
| R/B, excluded (2) | 5.8812 | 5.8135 | 5.7048 |
| R/B/W (2) | 2.8466 | 2.9283 | 2.8923 |
| Y/B/W (2) | 4.8163 | 4.7913 | 4.8243 |
| Y/R/W (6) | 2.5725 | 2.4219 | 2.3356 |
| Y/R/B (3) | 4.5511 | 6.5305 | **10.1727** |
| Y/R/B/W (3) | 4.8063 | 4.3591 | 4.1720 |

The important regression is chromatic three-paint mixing without white.
Rows 174, 172 and 176 increase by 7.137, 6.730 and 2.999 DE00 versus v1.
White-containing yellow/red and four-paint families improve, but those gains
do not offset this failure. No failing row was removed.

Pure endpoint maximum absolute spectral discrepancy is 3.33e-16; maximum
pure DE00 is 7.64e-14. These errors are numerical, because endpoints are
constraints. Independent black-layer reflectance/transmittance plus white
backing composition reproduces every saved model's predictions over all
45 recipes to <=5.56e-16. An independent matrix exponential of the two-flux
ODE agrees to 2.22e-16. Checks cover thin and opaque limits, exact synthetic
pure endpoints, inversion at optical depth 1e-5 and reflectance 0.999999.
Recorded v1 primary and v3 excluded-pair baseline scores agree within 1e-12.
See [verification](verification.json), [summary](summary.json) and
[per-row errors](errors.csv) for exact values.

All 12 prescribed starts converge in 10–22 evaluations, no active bounds.
Selected effective optical thickness is 11.6304 in the primary fit and
10.7137, 13.3732, 15.0110 in the Y/R, Y/B, R/B exclusions. Total optimizer
wall time across the 12 starts is 1.66 seconds on this host, excluding
startup, evaluation and checks. Reported regularized local Jacobian
condition numbers are 25.4, 23.7, 313.6 and 20.1 respectively. They are
local numerical sensitivities, not measurement uncertainty or physical
identification; the Y/B exclusion is noticeably less constrained.

Only the products of thickness and optical coefficients are observable;
the white gauge removes their global scaling freedom by assumption.
Unknown backing spectrum, differing thicknesses, surface reflection and
mass-to-volume conversion can confound effective K/S. Numerical convergence
and a finite fitted thickness do not establish that actual swatches had
that thickness or backing. This negative result rejects this specific
constrained white-backed model, not all finite-layer theory. The useful
next evidence is controlled thickness and known light/dark backing swatches
with repeats, followed by new independent mixtures. Do not promote this fit.

Reproduce from the repository root, using a fresh output directory for repeats:

```powershell
$env:OPENBLAS_NUM_THREADS='1'
$env:OMP_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
target/measured-oils/venv/Scripts/python.exe experiments/oil_parallel/physical/run.py check
target/measured-oils/venv/Scripts/python.exe experiments/oil_parallel/physical/run.py fit
target/measured-oils/venv/Scripts/python.exe experiments/oil_parallel/physical/run.py evaluate
target/measured-oils/venv/Scripts/python.exe experiments/oil_parallel/physical/verify.py
```

`run.py` accepts `--out` for each phase. The verifier currently checks the
default output directory. Raw measurements and coefficient arrays remain
under ignored `target/measured-oils/parallel/physical/`. The frozen model
records hashes of source, implementation, plan and baseline, plus row splits;
evaluation rejects changes to that manifest. The finite-layer equation follows
[Kubelka (1948), Part I](https://opg.optica.org/josa/abstract.cfm?uri=josa-38-5-448).
