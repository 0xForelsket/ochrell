"""Independently audit exported scores, then render the frozen comparison."""
import csv
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import run as study

HERE = study.HERE
LABELS = {f'{a}_{b}': f'{a.title()} {"K-M" if b == "km" else "+ correction"}'
    for a in ('binary', 'expanded', 'balanced') for b in ('km', 'empirical')}
CORRECTED = ('binary_empirical', 'expanded_empirical', 'balanced_empirical')
COLORS = ('#365978', '#d18c42', '#168a78')
METRICS = ('spectral_rmse', 'spectral_mae', 'spectral_max_abs', 'delta_e_2000')


def change(new, old):
    return 100*(new/old-1)


def audit(s, rows):
    """Check every aggregate against CSV without using the fitter's summarizer."""
    count = np.array([int(row['paint_count']) for row in rows])
    white = np.array([float(row['white_fraction']) for row in rows])
    masks = {'multicolor183': count >= 3, 'binary50': count == 2, 'all233': np.ones(len(rows), dtype=bool),
        'multicolor_no_white': (count >= 3)&(white == 0), 'multicolor_with_white': (count >= 3)&(white > 0)}
    masks.update({f'{n}_paints': count == n for n in range(3, 8)})
    values = {name: {metric: np.array([float(row[f'{name}_{metric}']) for row in rows]) for metric in METRICS} for name in study.MODEL_NAMES}
    checked = 0
    def check(scores, mask):
        nonlocal checked
        for name, scoreset in scores.items():
            assert scoreset['count'] == int(mask.sum())
            for metric in METRICS:
                x = values[name][metric][mask]
                for stat, actual in [('mean', x.mean()), ('median', np.median(x)), ('p95', np.quantile(x, .95)), ('max', x.max())]:
                    np.testing.assert_allclose(actual, scoreset[metric][stat], rtol=0, atol=1e-12)
                    checked += 1
    for role, mask in masks.items():
        check(s['subsets'][role], mask)
    family = np.array([row['family'] for row in rows])
    for name, group in s['groups'].items():
        mask = family == name
        check(group['all'], mask)
        if group['multicolor']:
            check(group['multicolor'], mask & masks['multicolor183'])
    for role in ('all', 'multicolor'):
        selected = [g for g in s['groups'] if role == 'all' or s['groups'][g]['multicolor']]
        assert len(selected) == s['equal_family_means'][role]['families']
        for name in study.MODEL_NAMES:
            for metric in ('spectral_rmse', 'delta_e_2000'):
                means = [values[name][metric][(family == g) & (masks['multicolor183'] if role == 'multicolor' else masks['all233'])].mean() for g in selected]
                np.testing.assert_allclose(np.mean(means), s['equal_family_means'][role]['scores'][name][metric], rtol=0, atol=1e-12)
                checked += 1
    for role, comparisons in s['comparisons'].items():
        for label, scores in comparisons.items():
            if label.startswith('base_vs_'):
                a, b = 'balanced_km', label.removeprefix('base_vs_')+'_km'
            elif label == 'balanced_correction_vs_base':
                a, b = 'balanced_empirical', 'balanced_km'
            else:
                a, b = 'balanced_empirical', label.removeprefix('balanced_vs_')+'_empirical'
            for metric, expected in scores.items():
                x, y = values[a][metric][masks[role]], values[b][metric][masks[role]]
                delta = x-y
                assert int((delta < -1e-12).sum()) == expected['improved']
                assert int((delta > 1e-12).sum()) == expected['worsened']
                assert int((abs(delta) <= 1e-12).sum()) == expected['tied']
                np.testing.assert_allclose(change(x.mean(), y.mean()), expected['mean_error_change_percent'], rtol=0, atol=1e-10)
                checked += 4
    return {'rows': len(rows), 'families': len(s['groups']), 'statistics_checked': checked, 'passed': True}


def stats_table(scores, names):
    header = '| Method | Mean RMSE | Median RMSE | p95 RMSE | Max RMSE | Mean DE00 | Median DE00 | p95 DE00 | Max DE00 |\n| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n'
    return header + '\n'.join('| '+LABELS[name]+' | '+' | '.join(
        f'{scores[name][metric][stat]:.6f}' if metric == 'spectral_rmse' else f'{scores[name][metric][stat]:.4f}'
        for metric in ('spectral_rmse', 'delta_e_2000') for stat in ('mean', 'median', 'p95', 'max'))+' |' for name in names)


def main():
    s = json.loads((HERE/'summary.json').read_text(encoding='utf-8'))
    v = json.loads((HERE/'verification.json').read_text(encoding='utf-8'))
    manifest = json.loads((HERE/'partition.json').read_text(encoding='utf-8'))
    assert s['manifest_sha256'] == v['manifest_sha256'] == study.method.old.sha((HERE/'partition.json').read_bytes())
    assert s['bundle_sha256'] == v['bundle_sha256'] == study.method.old.sha((study.DEFAULT/'frozen-models.json').read_bytes())
    with (HERE/'errors.csv').open(encoding='utf-8', newline='') as stream:
        rows = list(csv.DictReader(stream))
    checked = audit(s, rows)
    checked.update({'errors_sha256': study.method.old.sha((HERE/'errors.csv').read_bytes()),
        'summary_sha256': study.method.old.sha((HERE/'summary.json').read_bytes()),
        'report_code_sha256': study.method.old.sha(HERE.joinpath('report.py').read_bytes())})
    study.method.old.write_json(HERE/'score-audit.json', checked)
    primary = [row for row in rows if int(row['paint_count']) >= 3]
    assert len(primary) == 183 and len(rows) == 233
    a = s['subsets']['multicolor183']
    means = {name: a[name]['delta_e_2000']['mean'] for name in CORRECTED}
    main_color = change(means['balanced_empirical'], means['binary_empirical'])
    expanded_color = change(means['balanced_empirical'], means['expanded_empirical'])
    retained_color = 100*(means['binary_empirical']-means['balanced_empirical'])/(means['binary_empirical']-means['expanded_empirical'])
    retained_spectral = 100*(a['binary_empirical']['spectral_rmse']['mean']-a['balanced_empirical']['spectral_rmse']['mean'])/(a['binary_empirical']['spectral_rmse']['mean']-a['expanded_empirical']['spectral_rmse']['mean'])
    subgroup_rows = []
    for role, scores in s['subsets'].items():
        subgroup_rows.append('| '+role.replace('_', ' ')+f" | {scores['balanced_empirical']['count']} | "+' | '.join(
            f"{scores[name][metric]['mean']:.6f}" if metric == 'spectral_rmse' else f"{scores[name][metric]['mean']:.4f}"
            for metric in ('spectral_rmse', 'delta_e_2000') for name in CORRECTED)+' |')
    comparison_rows = []
    for role in ('multicolor183', 'binary50', 'multicolor_no_white', 'multicolor_with_white', 'all233'):
        for reference in ('binary', 'expanded'):
            c = s['comparisons'][role]['balanced_vs_'+reference]
            comparison_rows.append(f"| {role.replace('_', ' ')} | {reference} | {c['spectral_rmse']['mean_error_change_percent']:+.2f}% | {c['spectral_rmse']['improved']}/{c['spectral_rmse']['worsened']} | {c['delta_e_2000']['mean_error_change_percent']:+.2f}% | {c['delta_e_2000']['improved']}/{c['delta_e_2000']['worsened']} |")
    families = [{'family': name, 'test_rows': ','.join(map(str, group['test_rows'])),
        'primary_count': group['multicolor']['balanced_empirical']['count'] if group['multicolor'] else 0,
        **{f'{model}_{metric}': values[metric]['mean'] for model, values in group['all'].items() for metric in ('spectral_rmse', 'delta_e_2000')}} for name, group in s['groups'].items()]
    study.method.old_chromatic.write_csv(HERE/'families.csv', families)
    macro = s['equal_family_means']['multicolor']['scores']
    macro_table = '\n'.join(f"| {LABELS[name]} | {macro[name]['spectral_rmse']:.6f} | {macro[name]['delta_e_2000']:.4f} |" for name in study.MODEL_NAMES)
    regressions = []
    for reference in ('binary', 'expanded'):
        worst = sorted(primary, key=lambda row: float(row['balanced_empirical_delta_e_2000'])-float(row[reference+'_empirical_delta_e_2000']), reverse=True)[:6]
        for row in worst:
            regressions.append(f"| {reference} | {row['source_row']} | {row['family']} | {float(row['white_fraction']):.3f} | {float(row[reference+'_empirical_delta_e_2000']):.4f} | {float(row['balanced_empirical_delta_e_2000']):.4f} | {float(row[reference+'_empirical_spectral_rmse']):.6f} | {float(row['balanced_empirical_spectral_rmse']):.6f} |")
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.7), layout='constrained')
    roles = ('multicolor_with_white', 'multicolor_no_white', 'binary50')
    for ax, metric, title in zip(axes, ('spectral_rmse', 'delta_e_2000'), ('Mean spectral RMSE', 'Mean windowed DE00')):
        for i, name in enumerate(CORRECTED):
            ax.bar(np.arange(3)+(i-1)*.24, [s['subsets'][role][name][metric]['mean'] for role in roles], .23, label=LABELS[name], color=COLORS[i])
        ax.set_xticks(np.arange(3), ['Multicolor + white\n127 samples', 'Multicolor, no white\n56 samples', 'Excluded binaries\n50 samples'])
        ax.set_title(title)
        ax.set_ylim(bottom=0)
    axes[0].legend(fontsize=8)
    fig.suptitle('Equal category weighting: the same excluded recipe families\nLower errors are better; corrected models')
    fig.savefig(HERE/'subgroups.png', dpi=160)
    plt.close(fig)
    fig, axes = plt.subplots(2, 2, figsize=(11.5, 8), layout='constrained')
    for axisrow, role, label in zip(axes, ('multicolor183', 'binary50'), ('183 multicolors', '50 excluded binaries')):
        for ax, metric, title in zip(axisrow, ('spectral_rmse', 'delta_e_2000'), ('Spectral RMSE', 'Windowed DE00')):
            for i, name in enumerate(CORRECTED):
                ax.bar(np.arange(3)+(i-1)*.24, [s['subsets'][role][name][metric][stat] for stat in ('mean', 'p95', 'max')], .23, label=LABELS[name], color=COLORS[i])
            ax.set_xticks(np.arange(3), ['Mean', '95th percentile', 'Maximum'])
            ax.set_title(label+' / '+title)
            ax.set_ylim(bottom=0)
    axes[0, 0].legend(fontsize=8)
    fig.suptitle('Mean and tail errors under identical exclusions')
    fig.savefig(HERE/'comparison.png', dpi=160)
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 5), layout='constrained')
    for ax, reference in zip(axes, ('binary', 'expanded')):
        for white, color, label in [(True, '#168a78', 'Contains white'), (False, '#365978', 'No white')]:
            selected = [row for row in primary if (float(row['white_fraction']) > 0) == white]
            x = [float(row[reference+'_empirical_delta_e_2000']) for row in selected]
            y = [float(row['balanced_empirical_delta_e_2000']) for row in selected]
            ax.scatter(x, y, color=color, s=23, alpha=.8, label=label)
        end = max(a[reference+'_empirical']['delta_e_2000']['max'], a['balanced_empirical']['delta_e_2000']['max'])*1.05
        ax.plot([0, end], [0, end], '--', color='#888888', linewidth=1)
        ax.set(xlim=(0, end), ylim=(0, end), xlabel=reference.title()+' corrected DE00', ylabel='Balanced corrected DE00')
    axes[0].legend(fontsize=8)
    fig.suptitle('183 excluded multicolors: below the diagonal favors balancing')
    fig.savefig(HERE/'per-row.png', dpi=160)
    plt.close(fig)
    binary = s['comparisons']['binary50']
    no_white = s['comparisons']['multicolor_no_white']
    base_runs = [r for m in v['models'].values() for r in m['base_runs']]
    corrections = [m['correction'] for m in v['models'].values()]
    counts = {name: [job['category_counts'][name] for job in manifest['jobs'].values()] for name in study.CATEGORIES}
    weights = {name: [(len(job['train_rows'])-8)/(4*job['category_counts'][name]) for job in manifest['jobs'].values()] for name in study.CATEGORIES}
    weight_table = '\n'.join(f'| {name.replace("_", " ")} | {min(counts[name])}-{max(counts[name])} | {min(weights[name]):.6f}-{max(weights[name]):.6f} |' for name in study.CATEGORIES)
    text = f'''# Balanced calibration recovers color means, with a remaining binary spectral cost

**The predefined rule succeeds as a color-error compromise.** It recovers the
binary and no-white multicolor mean-color regressions while retaining most of
the multicolor gains. Binary spectral accuracy remains worse than the original
binary-calibrated baseline, and the unweighted expanded fit still has the best
primary mean color score. This supports a candidate for painting trials, rather
than a claim that one calibration is best on every criterion.

The balanced model changes mean multicolor color error by **{main_color:+.2f}%**
against binary calibration and **{expanded_color:+.2f}%** against unweighted
expanded calibration. It retains **{retained_color:.2f}% of the expanded model's
mean color improvement** over the binary baseline, and **{retained_spectral:.2f}%
of its mean spectral improvement**. Negative changes mean lower error.

For excluded binaries, mean spectral error changes
{binary['balanced_vs_expanded']['spectral_rmse']['mean_error_change_percent']:+.2f}%
against expanded calibration and
{binary['balanced_vs_binary']['spectral_rmse']['mean_error_change_percent']:+.2f}%
against the binary baseline. Mean color changes are respectively
{binary['balanced_vs_expanded']['delta_e_2000']['mean_error_change_percent']:+.2f}% and
{binary['balanced_vs_binary']['delta_e_2000']['mean_error_change_percent']:+.2f}%.
For no-white multicolors, the corresponding mean color changes are
{no_white['balanced_vs_expanded']['delta_e_2000']['mean_error_change_percent']:+.2f}% and
{no_white['balanced_vs_binary']['delta_e_2000']['mean_error_change_percent']:+.2f}%.
The full means, tails and regressions below determine the tradeoff.

![Calibration compromise across recipe types](subgroups.png)

## Exact experiment

The [plan](PLAN.md), fitter and tests were frozen before 107 candidate fits.
The [partition](partition.json) records every permitted row and weight. Reuse
the earlier 51 binary and 107 expanded fits, verified by their frozen hashes,
with identical 107 complete chromatic-ratio exclusions. All members of a family,
including its binary parent and white additions, are excluded together.
The 8 pure and 45 white-tint anchors remain available. Other ratios using the
same paints remain in training. Assessment is on 183 multicolors and 50 binaries;
the anchors are not scored as predictive validation.

The candidate uses each expanded training pool (282-285 rows) with equal total
weight for four nonpure categories. For n training rows, m nonpure rows and n_g
training rows in category g, each nonpure row receives m/(4 n_g); pures retain 1.
The original data residual denominator sqrt(n * 31) and all priors are unchanged.
Thus total row weight stays n, preserving data weight relative to regularization.
Weights are computed independently within each training pool from recipes alone.

| Category | Training rows across folds | Per-row weight across folds |
| --- | --- | --- |
{weight_table}

Both fitting stages use these weights. The model remains the same measured-pure
K-M base (217 parameters, white S=1, three original starts) followed by 112
possible bounded pair controls. Prediction equations, pure endpoints, bounds,
priors and stopping rules are unchanged. No sweep or new term was introduced.

## Primary: 183 excluded multicolors

{stats_table(a, study.MODEL_NAMES)}

Spectral RMSE is the mean per-recipe reflectance RMSE over the 31 measured bands.
Color is the unchanged D65/2-degree, 400-700 nm windowed DE00, with a matching
truncated white and no display gamut mapping. These are not full-visible-spectrum
color errors. All six methods use the same excluded rows.

![Primary and binary means and tails](comparison.png)

Equal weight over the 99 families containing multicolor assessments gives:

| Method | Family-mean RMSE | Family-mean DE00 |
| --- | --- | --- |
{macro_table}

Fold training sets overlap. Family means are descriptive checks on sample-count
imbalance, not independent experimental replicates or significance tests.

## Recipe subgroups and secondary binaries

| Assessment | Rows | Binary RMSE | Expanded RMSE | Balanced RMSE | Binary DE00 | Expanded DE00 | Balanced DE00 |
| --- | --- | --- | --- | --- | --- | --- | --- |
{chr(10).join(subgroup_rows)}

All columns above include pair correction. Ingredient counts include white.
The 50-binary tail comparison is:

{stats_table(s['subsets']['binary50'], CORRECTED)}

The no-white multicolor tail comparison is:

{stats_table(s['subsets']['multicolor_no_white'], CORRECTED)}

Balanced corrected model versus each comparator (negative is better):

| Assessment | Reference | Mean RMSE change | RMSE better/worse | Mean DE00 change | DE00 better/worse |
| --- | --- | --- | --- | --- | --- |
{chr(10).join(comparison_rows)}

[errors.csv](errors.csv) contains all 233 assessed rows; [families.csv](families.csv)
contains all 107 families. [summary.json](summary.json) retains all six methods,
all metrics and subgroups, including the base-only comparisons and corrections.

![Individual multicolor color errors](per-row.png)

The six largest multicolor color-error increases against each comparator are:

| Reference | Source row | Family | White fraction | Reference DE00 | Balanced DE00 | Reference RMSE | Balanced RMSE |
| --- | --- | --- | --- | --- | --- | --- | --- |
{chr(10).join(regressions)}

## Verification

- Three protocol tests check identical exclusions, per-fold category weights,
  total objective scale, unchanged prior rows, both analytic Jacobians against
  finite differences, and selected-data fitting interfaces.
- With uniform weights, the new fitter reproduces a frozen expanded model's
  q, K, S, log-scattering and pair controls exactly. All archived comparator
  aggregates and per-row scores are reproduced exactly. See [preflight.json](preflight.json).
- All {len(v['models'])} candidates succeeded. {sum(r['success'] for r in base_runs)}/{len(base_runs)}
  base starts converged, using {min(r['nfev'] for r in base_runs)}-{max(r['nfev'] for r in base_runs)}
  evaluations with {min(r['bound_variables'] for r in base_runs)}-{max(r['bound_variables'] for r in base_runs)}
  active bounds. Corrections used {min(r['nfev'] for r in corrections)}-{max(r['nfev'] for r in corrections)}
  evaluations and {min(r['bound_variables'] for r in corrections)}-{max(r['bound_variables'] for r in corrections)} active bounds.
- Every candidate was refitted after replacing excluded spectra. All fitted
  optical and pair coefficients were exactly unchanged.
- Scalar decoding agrees within {v['checks']['scalar_max_abs']:.3g}; pure endpoints
  within {v['checks']['pure_max_abs']:.3g}. All recorded and 257 extra dense recipes
  per model produce finite reflectance strictly in (0,1).
- An independent CSV audit checks {checked['statistics_checked']} statistics,
  including every subgroup and family aggregate, macro mean and comparison count.
  See [score-audit.json](score-audit.json) and [verification.json](verification.json).
- All source, previous fitter, comparator and existing local runtime package
  hashes remain unchanged. No failed family or difficult row was dropped.

Frozen candidate bundle under ignored
`target/measured-oils/balanced-calibration/frozen-models.json`, SHA-256:

`{s['bundle_sha256']}`

## Evidence and product boundary

Relative to binary-only calibration, the corrected balanced model has lower mean
color error in each of the three assessed recipe categories: excluded binaries,
multicolors without white, and multicolors with white. It also improves no-white
multicolor mean spectral error. Relative to unweighted expanded calibration,
it improves binary and no-white means at the cost of white-containing mixtures.
Across all 233 assessed rows, its mean color score is nearly unchanged (+0.16%)
and mean spectral RMSE is slightly lower (-0.62%) than expanded calibration.

Recovery of a mean is not recovery of every sample: 29/50 binary color errors
and 31/50 binary spectral errors remain worse than the original binary baseline.
Binary p95/max color errors improve over both comparators, but binary spectral
p95 still exceeds the original baseline. Primary multicolor p95 color improves
slightly over expanded calibration (5.8897 to 5.8445), while its worst color error
rises (8.7423 to 9.2652), as do its spectral p95 and maximum. No-white worst color
and spectral errors also rise relative to expanded calibration, despite better
means. These are material residual tradeoffs, not a universal accuracy gain.

For the next product comparison, the balanced procedure is a reasonable
candidate: it preserves most multicolor gains, recovers mean color on the
previously harmed categories and improves binary color tails without adding
runtime work. Keep the unweighted expanded result as the reference for the
lowest multicolor mean. This study does not identify optimal weights or justify
choosing different procedures after inspecting individual target errors.

This is one predeclared candidate motivated by previous results on the same
source. It assesses transfer to excluded recipe ratios; it is development
evidence, not a pristine final test or independent-batch validation. No new
physical measurements or measured eight-ingredient recipe were added.

Balancing changes the compromise the model is asked to make. A change in excluded
errors supports a calibration choice within this experiment; it does not prove
that sample imbalance alone caused the previous errors or remove structural
limits of the optical model. Error-dependent tuning was not performed here.

These results pool 107 fitted candidates. They do not describe one deployable
palette; a final all-data fit would be a separate artifact. Existing packages,
library code, renderer and defaults remain unchanged.

## Reproduction

Use a fresh ignored --out directory for a repeat. Checkpoints carry the full
partition hash. The report reads the tracked numerical outputs after evaluation.

```powershell
.\\target\\measured-oils\\venv\\Scripts\\python.exe -m unittest discover -s experiments/oil_balanced_calibration -p test_protocol.py -v
.\\target\\measured-oils\\venv\\Scripts\\python.exe experiments/oil_balanced_calibration/run.py prepare
.\\target\\measured-oils\\venv\\Scripts\\python.exe experiments/oil_balanced_calibration/run.py fit --workers 4
.\\target\\measured-oils\\venv\\Scripts\\python.exe experiments/oil_balanced_calibration/run.py verify --workers 4
.\\target\\measured-oils\\venv\\Scripts\\python.exe experiments/oil_balanced_calibration/run.py evaluate
.\\target\\measured-oils\\venv\\Scripts\\python.exe experiments/oil_balanced_calibration/report.py
```

Original measurements and fitted coefficients stay local under ignored target/.
Original scripts, hashes and numerical reports are retained in the repository.
'''
    (HERE/'REPORT.md').write_bytes(text.encode())
    print(json.dumps({'audit': checked, 'primary_color_change_vs_binary': main_color,
        'primary_color_change_vs_expanded': expanded_color, 'retained_color_gain_percent': retained_color,
        'retained_spectral_gain_percent': retained_spectral}, indent=2))


if __name__ == '__main__':
    main()
