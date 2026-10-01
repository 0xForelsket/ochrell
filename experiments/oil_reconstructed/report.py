"""Render frozen results; subgroup descriptions are post-evaluation diagnostics."""
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent


def main():
    result = json.loads((HERE/'summary.json').read_text())
    verification = json.loads((HERE/'verification.json').read_text())
    variants = json.loads((HERE/'variants.json').read_text())
    rows = list(csv.DictReader((HERE/'errors.csv').open(newline='')))
    base = result['variants']['base']
    diagnostics = {}
    for key, data in result['variants'].items():
        selected = [r for r in rows if r['variant'] == key]
        groups = {'white_ternary9': [r for r in selected if r['role'] == 'ternary' and 'w' in r['sample'].lower()],
                  'chromatic_ternary3': [r for r in selected if r['role'] == 'ternary' and 'w' not in r['sample'].lower()]}
        assert len(groups['white_ternary9']) == 9 and len(groups['chromatic_ternary3']) == 3
        assert all(float(r['empirical_spectral_rmse']) > float(r['km_spectral_rmse'])
                   for r in groups['chromatic_ternary3'])
        diagnostics[key] = {}
        for label, items in groups.items():
            record = {'samples': [r['sample'] for r in items], 'count': len(items)}
            for metric in ['spectral_rmse', 'delta_e_2000']:
                km = np.array([float(r['km_'+metric]) for r in items])
                empirical = np.array([float(r['empirical_'+metric]) for r in items])
                record[metric] = {'km_mean': float(km.mean()), 'empirical_mean': float(empirical.mean()),
                                  'improved': int((empirical < km).sum()),
                                  'improvement_percent': float(100*(km.mean()-empirical.mean())/km.mean())}
            diagnostics[key][label] = record
    (HERE/'diagnostics.json').write_bytes((json.dumps({'status': 'Post-evaluation descriptive subgroups; no fitting or tuning.',
        'variants': diagnostics}, indent=2)+'\n').encode())

    def table(headers, records):
        return '\n'.join(['| '+' | '.join(headers)+' |', '| '+' | '.join(['---']*len(headers))+' |']+
                         ['| '+' | '.join(map(str, r))+' |' for r in records])

    headline = []
    for role, label in [('ternary12', '12 ternaries (primary)'), ('pairs9', '9 excluded pairs'), ('pooled21', 'All 21 assessments')]:
        data = base['grouped'][role]
        km, emp = [data[m]['spectral_rmse']['mean'] for m in ['km', 'empirical']]
        changes = base['changes'][role]['spectral_rmse']
        headline.append([label, f'{km:.6f}', f'{emp:.6f}', f'{100*(km-emp)/km:.2f}%', f"{changes['improved']} / {changes['worsened']}"])
    sensitivity = []
    for tol, data in result['sensitivity'].items():
        r = data['roles']['ternary12']['ranges']
        sensitivity.append([tol, data['subset_mappings'], f"{r['km'][0]:.6f}-{r['km'][1]:.6f}",
                            f"{r['empirical'][0]:.6f}-{r['empirical'][1]:.6f}",
                            f"{r['improvement_percent'][0]:.2f}-{r['improvement_percent'][1]:.2f}%"])
    variant_records = []
    for key, data in result['variants'].items():
        a = data['grouped']['ternary12']; km = a['km']; emp = a['empirical']
        variant_records.append([key, ', '.join(data['changed_subset_labels']) or '(frozen base)',
            ', '.join(f'{x:g}' for x in data['tolerances']),
            f"{100*(1-emp['spectral_rmse']['mean']/km['spectral_rmse']['mean']):.2f}%",
            f"{emp['delta_e_2000']['mean']-km['delta_e_2000']['mean']:+.4f}"])
    diagnostic_records = []
    for key, label in [('white_ternary9', '9 ternaries containing white'), ('chromatic_ternary3', '3 Y/C/B ternaries without white')]:
        d = diagnostics['base'][key]['spectral_rmse']
        diagnostic_records.append([label, f"{d['km_mean']:.6f}", f"{d['empirical_mean']:.6f}",
                                   f"{d['improvement_percent']:+.2f}%", f"{d['improved']} / {diagnostics['base'][key]['count']}"])
    group_records = []
    for _, group in base['groups'].items():
        km, emp = [group['metrics'][m] for m in ['km', 'empirical']]
        group_records.append([', '.join(group['test']), f"{km['spectral_rmse']['mean']:.6f}",
            f"{emp['spectral_rmse']['mean']:.6f}", f"{emp['delta_e_2000']['mean']-km['delta_e_2000']['mean']:+.3f}"])
    regressions = [r for r in rows if r['variant'] == 'base' and float(r['empirical_spectral_rmse']) > float(r['km_spectral_rmse'])]
    regression_table = table(['Recipe', 'K-M RMSE', 'Empirical RMSE'],
        [[r['sample'], f"{float(r['km_spectral_rmse']):.6f}", f"{float(r['empirical_spectral_rmse']):.6f}"] for r in regressions])
    starts = [r for m in result['optimizer'].values() for r in m['base']]
    fits = [m['empirical'] for m in result['optimizer'].values()]
    a = base['grouped']['ternary12']
    old = base['parent_available_ternary12']
    color_differences = [v['grouped']['ternary12']['empirical']['delta_e_2000']['mean']-
                         v['grouped']['ternary12']['km']['delta_e_2000']['mean'] for v in result['variants'].values()]

    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False})
    fig, ax = plt.subplots(1, 2, figsize=(12.8, 4.7), gridspec_kw={'width_ratios': [1.2, 1]})
    labels = ['Base']+[', '.join(v['changed_subset_labels']) for k, v in result['variants'].items() if k != 'base']
    gains = [100*(1-v['grouped']['ternary12']['empirical']['spectral_rmse']['mean']/v['grouped']['ternary12']['km']['spectral_rmse']['mean']) for v in result['variants'].values()]
    y = np.arange(len(labels)); ax[0].barh(y, gains, color='#21867a', height=.6)
    ax[0].set_yticks(y, labels); ax[0].invert_yaxis(); ax[0].set_xlim(0, 34)
    ax[0].set_xlabel('Reduction in mean spectral RMSE (%)')
    ax[0].set_title('Primary result across all 7 feasible subset maps', loc='left', fontweight='bold', pad=14)
    for i, x in enumerate(gains): ax[0].text(x+.5, i, f'{x:.1f}%', va='center', fontsize=9)
    groups = [diagnostics['base'][x]['spectral_rmse'] for x in ['white_ternary9', 'chromatic_ternary3']]
    x = np.arange(2)
    ax[1].bar(x-.18, [d['km_mean'] for d in groups], .36, label='K-M', color='#53667c')
    ax[1].bar(x+.18, [d['empirical_mean'] for d in groups], .36, label='Empirical correction', color='#21867a')
    ax[1].set_xticks(x, ['9 with white', '3 without white']); ax[1].set_ylabel('Mean spectral RMSE')
    ax[1].set_title('The gain is concentrated in white mixtures', loc='left', fontweight='bold', pad=14)
    ax[1].legend(frameon=False); ax[1].set_ylim(0, .047)
    fig.suptitle('Grillini: unchanged models, inferred recipe-to-spectrum mapping', x=.06, ha='left', fontsize=14, fontweight='bold')
    fig.text(.06, .015, 'Conditional paired-scan analysis. Right panel: descriptive subgroups of the frozen base mapping. Lower RMSE is better.', fontsize=9, color='#555555')
    fig.tight_layout(rect=[.01, .05, 1, .91]); fig.savefig(HERE/'comparison.png', dpi=160); plt.close(fig)

    report = f'''# Frozen models on the reconstructed Grillini dataset

**The empirical correction reduces the primary mean spectral RMSE by 26.9%,
and the advantage survives every feasible selected-palette mapping within the
tested paired-scan family.** Across the looser mapping stress test it remains
26.1-26.9%. This is meaningful evidence for the empirical method under inferred
labels. It does not establish author-confirmed identities or general paint accuracy.

The benefit is concentrated in mixtures containing white. All three held-out
Y/C/B mixtures without white become worse. Color-error improvements are much
smaller than spectral improvements, and one plausible map reverses the primary
mean color advantage. No model, measured preset or default is promoted.

![Frozen comparison and mapping sensitivity](comparison.png)

## Fixed method and independent checkpoints

The [plan](PLAN.md) was written before these fits or scores. The source recovery
was committed at `352312f`, retaining the exact mapping SHA-256
`9e31ac91fcaa334b8bc56e9d3ae501d7ebe79de932ca066dba84ba276f9d6a22`.
Every dependency hash, optimizer setting and recipe split matches the original
[external experiment](../oil_external/PLAN.md). Only the separate loader applies
the frozen inferred permutation. Original source files and older experiments
are unchanged. No Claude result or implementation was consulted.

The palette is Naples Yellow, Carmine, Ultramarine Blue and Kremer White,
specified as dry pigment mass before linseed oil addition. It is not Old Holland
tube-paint mass. Spectra are interpolated within measured support to 440-740 nm
at 10 nm spacing. Four pure endpoints and nine white tints are always calibration
anchors; nine chromatic pairs augment the training pool. Each scored chromatic
ratio and its white addition are excluded together. Twelve ternaries never enter
fitting. There are 21 scored rows, 12 groups and 10 fits per map before reuse of
identical calibration inputs.

The 93-parameter opaque K-M fit and subsequent bounded 24-control empirical
correction are imported unchanged. Every corrected-data model is newly fitted
on calibration inputs; old coefficients are not reused. All 38 distinct fits
were frozen, then verified, before evaluation. Calibration data are shared among
maps only when recipe names, concentrations and measured spectra agree exactly.

## Primary and secondary spectral results

RMSE is measured in reflectance units on a 0-1 scale. The improvement percentage
compares means of per-sample RMSE, not squared error or full-visible color error.

{table(['Assessment', 'K-M mean RMSE', 'Empirical mean RMSE', 'Reduction', 'Rows improved / worse'], headline)}

For the primary twelve rows, p95 RMSE falls from
{a['km']['spectral_rmse']['p95']:.6f} to {a['empirical']['spectral_rmse']['p95']:.6f},
and the maximum falls from {a['km']['spectral_rmse']['max']:.6f} to
{a['empirical']['spectral_rmse']['max']:.6f}. When all chromatic parent pairs are
available for calibration, the same twelve ternaries have mean RMSE
{old['km']['spectral_rmse']['mean']:.6f} for K-M and
{old['empirical']['spectral_rmse']['mean']:.6f} for the correction. Grouped exclusion
is the prespecified primary comparison; the parent-available result is secondary.

The earlier header-paired external result was near zero improvement on these
ternaries and worse overall. Its numerical scores are preserved as a source
diagnostic, but should not be used to reject model generalization: those fits
associated recipes with substantially different inferred spectra.

## Mapping sensitivity

Before fitting, every orientation combination of audited mutable pairs touching
the selected palette was checked for a complete 175-sample witness. Other pairs
could compensate, subject to the seven published means and best/worst counts.
Each witness was directly re-evaluated, including pure identities and permutation
integrity. All 25 feasibility cases resolved: one at 2e-6, eight at 5e-6 and
sixteen at 1e-5. No timeout was classified as infeasible.

{table(['Mean-MSE tolerance', 'Feasible subset maps', 'K-M primary RMSE range', 'Empirical primary RMSE range', 'Reduction range'], sensitivity)}

These ranges cover all distinct selected-palette mappings in the **restricted
paired-scan hypothesis**, using the completed per-pair ambiguity audit. They are
not unrestricted bounds over all possible labels. The seven full-palette pures
and panel structure remain assumptions; the tolerances are diagnostic choices,
not measured uncertainty bounds or probabilities.

{table(['Map', 'Changed selected recipes', 'Feasible tolerances', 'Primary RMSE reduction', 'Primary DE00 change'], variant_records)}

Negative DE00 change means improvement. A row naming one changed selected recipe
can contain compensating changes outside this palette. Only complete feasible
witnesses were admitted; no isolated guessed swap was scored. The selected
34-sample projection is sufficient for these fits and scores, so full mappings
with the same projection share a result.

## Where the model still fails

The following subgroups were inspected after evaluation to explain the primary
result; they are descriptive, not additional prespecified success criteria.

{table(['Ternary subgroup', 'K-M mean RMSE', 'Empirical mean RMSE', 'Reduction (+) / increase (-)', 'Rows improved / total'], diagnostic_records)}

All three no-white ternaries (`Bcy`, `bCy`, `bcY`) worsen under every feasible
subset map. The empirical correction's evidence is stronger for interpolation
among white-containing mixtures than for mixing three chromatic pigments. The
largest spectral regression in the base mapping is `bCy`, whose RMSE nearly
triples. The base map has these five spectral regressions:

{regression_table}

Mean primary windowed DE00 moves only from
{a['km']['delta_e_2000']['mean']:.3f} to {a['empirical']['delta_e_2000']['mean']:.3f}:
six samples improve and six worsen. Across mappings, its empirical-minus-K-M
difference ranges from {min(color_differences):+.4f} to {max(color_differences):+.4f};
the mean color advantage therefore is not robust at the looser tolerance.
Primary p95 windowed DE00 falls from {a['km']['delta_e_2000']['p95']:.3f} to
{a['empirical']['delta_e_2000']['p95']:.3f} in the base map, but absolute errors
remain substantial. These values use D65/2-degree colorimetry truncated to
440-740 nm with a matching white; they are not full-visible DE00 and should not
be compared numerically with the Old Holland scores.

## Per-group base-map results

{table(['Held-out recipes', 'K-M mean RMSE', 'Empirical mean RMSE', 'Mean DE00 change'], group_records)}

Full per-row metrics for all seven maps are in [errors.csv](errors.csv).

## Verification and remaining limits

- All {len(starts)} K-M starts converged, using {min(r['nfev'] for r in starts)}-{max(r['nfev'] for r in starts)} evaluations; none hit a bound.
- All {len(fits)} empirical fits converged in {min(r['nfev'] for r in fits)}-{max(r['nfev'] for r in fits)} evaluations, with 0-1 active bound controls.
- Independent scalar predictions differ by at most {verification['scalar_max_abs']:.3g}; pure endpoints differ by at most {verification['pure_max_abs']:.3g}.
- Every distinct calibration set was refitted after replacing excluded targets. All coefficients were exactly unchanged.
- Predictions for all 34 recipes under every fitted model are finite and strictly within (0,1). Frozen bundles remained byte-identical during verification and evaluation.
- Original source, fitter, settings and partition hashes match the prior experiment. No extrapolation or spectral clipping was introduced.

The frozen coefficient bundle is retained under ignored
`target/measured-oils/grillini-reconstructed/frozen-models.json`, SHA-256
`{result['model_bundle_sha256']}`. Provenance, environment versions and optimizer
records are in [summary.json](summary.json); checks are in
[verification.json](verification.json). The [variants](variants.json) preserve
complete feasible witnesses and explicit infeasible pattern results.

The mapping was inferred using aggregate statistics that include these samples.
Consequently, held-out optical fitting does **not** make the entire reconstruction
and evaluation pipeline independent of the assessment observations. Sensitivity
shows stability within the tested ambiguity, not freedom from reconstruction
bias. The study remains small, batch identity is unknown, calibration anchors
are not independently assessed, and the paper's confidence intervals remain
unreproduced. This is evidence for continued research, not a physical-accuracy
certification or permission to ship a measured preset.

The useful next scientific question is why the correction helps white-containing
mixtures while harming all three no-white ternaries. Diagnose that split using
frozen predictions before proposing one constrained revision; do not tune this
study further and relabel its scores as fresh validation.

## Reproduction

Use the cached, checksum-verified source ZIP described in
[source recovery](../oil_source_recovery/REPRODUCE.md), and the scientific Python
environment recorded in the manifest. Run each phase in order:

```powershell
.\\target\\measured-oils\\venv\\Scripts\\python.exe experiments/oil_reconstructed/run.py prepare
.\\target\\measured-oils\\venv\\Scripts\\python.exe experiments/oil_reconstructed/run.py fit
.\\target\\measured-oils\\venv\\Scripts\\python.exe experiments/oil_reconstructed/run.py verify
.\\target\\measured-oils\\venv\\Scripts\\python.exe experiments/oil_reconstructed/run.py evaluate
.\\target\\measured-oils\\venv\\Scripts\\python.exe experiments/oil_reconstructed/report.py
```

Preparation and fitting refuse to overwrite existing frozen outputs. For a fresh
rerun pass the same fresh `--out target/measured-oils/<new-study>` to all four
phases. Verification/evaluation check frozen input hashes. Solver witnesses and
elapsed times may differ across versions; evaluate the recorded witnesses to
reproduce this exact label sensitivity set. Outputs from a fresh run replace this
experiment's generated result files, but never alter the original experiments.
The report renderer reads only saved scores; it never fits or changes labels.

Primary source: Grillini, Thomas and George,
[Comparison of Imaging Models for Spectral Unmixing in Oil Painting (2021)](https://doi.org/10.3390/s21072471).
'''
    (HERE/'REPORT.md').write_bytes(report.encode())
    print(json.dumps(diagnostics['base'], indent=2))


if __name__ == '__main__':
    main()
