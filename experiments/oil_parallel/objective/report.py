"""Normalize inherited comparison labels and render the compact report."""
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
s=json.loads((HERE/'summary.json').read_text())
old=json.loads((ROOT/'results/measured-oils-v3/summary.json').read_text())
for section in ['calibration29','calibration_pure4','folds','families_multicolor16']:
    entries=[s[section]] if section.startswith('calibration') else s[section].values()
    for item in entries:
        item['hybrid']=item.pop('v3')
    if section.startswith('calibration'):
        s[section]['v3']=old[section]['v3']
    else:
        for name,item in s[section].items():item['v3']=old[section][name]['v3']
s['pair_family_macro_mean']['hybrid']=s['pair_family_macro_mean'].pop('v3')
s['pair_family_macro_mean']['v3']=old['pair_family_macro_mean']['v3']
s.pop('note')
(HERE/'summary-normalized.json').write_text(json.dumps(s,indent=2)+'\n')
lines=['# Color-aware objective: useful multicolor tradeoff, worse pair extrapolation','',
'The declared hybrid improves multicolor mean DE00 from 3.915 (same-protocol v3) to 3.163, but mean spectral RMSE rises from 0.02849 to 0.02880 and worst spectral RMSE rises from 0.06121 to 0.07033. Withheld pairs worsen in both mean metrics: DE00 3.723 to 4.335; spectral RMSE 0.03359 to 0.03728. Retain v1 as the research baseline. This experiment supports objective misalignment as a contributor on these multicolor recipes, not as a sufficient general fix. All assessment rows were previously exposed; this is exploratory development evidence.', '',
'## Declared model and objective','',
'One candidate, no ablation or sweep: unchanged fixed-pure opaque homogeneous K-M, 93 log-S parameters, mass recipes and white gauge. The objective is 0.5 spectral MSE + 0.5 (0.02/3)^2 mean squared Lab Euclidean distance + unchanged v1 regularization. The mean color term is across rows, summing its three channels. The 3-unit scale is a declared engineering normalization inspired by the original color screen; it does not equate DE76 with DE00. Lab distance is a smooth fitting surrogate; all reported color errors are truncated-D65 CIEDE2000. No clipping, gamut mapping, extrapolated spectral tails, or corrected pure spectra.', '',
'Plan/config were written before real fitting; implementation/config/plan and shared dependencies were hashed in the partition. Four fits used primary29 or complete pair-family exclusions, each with the three original starts and bounds/tolerances; successful starts were chosen only by training loss. All four models were frozen before evaluation. One sequencing deviation: archived baseline score reproduction was verified during evaluation, after fitting, rather than before fitting as planned. It passed within 1e-12. No settings were changed after evaluation.', '',
'## Same-row assessment','', '| Set/model | RMSE mean | RMSE p95 | RMSE max | MAE mean | DE00 mean | median | p95 | max |','|---|---:|---:|---:|---:|---:|---:|---:|---:|']
for role in ['primary_multicolor16','pair_family_cv8','cross_fitted24']:
    for name in ['v1','v3','hybrid']:
        x=s[role][name];r=x['spectral_rmse'];d=x['delta_e_2000']
        lines.append(f"| {role}/{name} | {r['mean']:.5f} | {r['p95']:.5f} | {r['max']:.5f} | {x['spectral_mae']['mean']:.5f} | {d['mean']:.3f} | {d['median']:.3f} | {d['p95']:.3f} | {d['max']:.3f} |")
lines+=['','The pooled 24 diagnostic combines 16 primary-model and eight fold predictions; it is not one deployable artifact. On primary16 the hybrid still fails the original mean spectral RMSE, p95 spectral RMSE and mean DE00 screens; p95/max DE00 pass. Calibration29 mean DE00 and spectral RMSE are '+f"{s['calibration29']['hybrid']['delta_e_2000']['mean']:.3f} and {s['calibration29']['hybrid']['spectral_rmse']['mean']:.5f}.",'','## Family results and regressions','', '| Family | n | v1 DE00 | v3 DE00 | hybrid DE00 | hybrid RMSE | hybrid DE00 max |','|---|---:|---:|---:|---:|---:|---:|']
for section in ['families_multicolor16','folds']:
    for family,item in s[section].items():
        h=item['hybrid'];lines.append(f"| {family}{' (excluded pair)' if section=='folds' else ''} | {h['count']} | {item['v1']['delta_e_2000']['mean']:.3f} | {item['v3']['delta_e_2000']['mean']:.3f} | {h['delta_e_2000']['mean']:.3f} | {h['spectral_rmse']['mean']:.5f} | {h['delta_e_2000']['max']:.3f} |")
lines+=['','Versus v3, 12/16 multicolor colors improve and four worsen; 9/16 spectra improve. Only 3/8 excluded-pair colors and 1/8 spectra improve. Full per-row metrics including MAE and band-error maxima are in errors.csv; no failed case was removed.','', 'Largest color regressions against v1:','']
for role in ['primary_multicolor16','pair_family_cv8']:
    for x in s['changes'][role]['worst_color_regressions']:
        lines.append(f"- {role}, row {x['source_row']} ({x['family']}): {x['v1']:.3f} to {x['v3']:.3f}, +{x['increase']:.3f} DE00.")
lines+=['','## Numerics, preservation and cost','',f"All 12 starts converged (10 to 13 evaluations), no bound variables; optimizer-only total {s['total_fit_seconds']:.3f} seconds, excluding interpreter startup/checks/reporting. Parameter count remains 93. Pure-paint maximum absolute reflectance drift is {s['calibration_pure4']['hybrid']['spectral_max_abs']['max']:.3g}; this is a hard construction constraint, not predictive validation.", '',
'Central-difference residual Jacobian max error 1.32e-11; Lab agreement with colour including the dark linear branch 8.35e-14; independent scalar synthetic K-M error 5.41e-16. Smooth noiseless synthetic recovery using declared regularization has maximum reflectance error 4.60e-6. An initial jagged random-S recovery fixture showed 0.00731 error because curvature penalizes the known jagged truth; that fixture was replaced with smooth known curves before real fitting. This observation is regularization bias, not an optimizer failure or candidate retuning. Real saved-model scalar checks and pure constraints pass. V1/v3 same-row mean DE00 reproduces archived results within 1e-12.', '',
'summary-normalized.json uses unambiguous hybrid/v3 names; summary.json retains the original helper labels in nested sections, as documented there. The frozen implementation and model remain intact. checks.json, errors.csv, partition hashes and complete optimizer records make the result auditable.', '',
'## Reproduce','', 'Run in repository root with OPENBLAS_NUM_THREADS=1, OMP_NUM_THREADS=1 and MKL_NUM_THREADS=1. Use target/measured-oils/venv/Scripts/python.exe experiments/oil_parallel/objective/run.py check, then prepare, fit, evaluate, each with the same fresh --out target/measured-oils/parallel/objective/repeat. Existing frozen fits are refused. Finally run report.py. Raw measurements and coefficient artifacts remain under ignored target output; no runtime, renderer or paper changes.', '',
'The archive cannot establish which physical assumptions cause residuals. One excluded yellow/blue sample is especially weak family evidence. Lab weighting can sacrifice spectral or alternate-illuminant fidelity. These results justify a documented color/spectral tradeoff but require new swatches for independent validation; they do not support promoting this hybrid as a universal palette.']
(HERE/'REPORT.md').write_text('\n'.join(lines)+'\n')

