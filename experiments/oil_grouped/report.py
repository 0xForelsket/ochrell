"""Render the frozen grouped-validation scores; never fit or select a model."""
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
s = json.loads((HERE / 'summary.json').read_text())
check = json.loads((HERE / 'verification.json').read_text())
baseline = json.loads((HERE / 'baseline-check.json').read_text())
with (HERE / 'errors.csv').open(newline='') as f:
    rows = list(csv.DictReader(f))


def table(headers, body):
    return '\n'.join(['| ' + ' | '.join(headers) + ' |',
                      '| ' + ' | '.join(['---'] * len(headers)) + ' |'] +
                     ['| ' + ' | '.join(map(str, row)) + ' |' for row in body])


score_rows = []
for role, label in [('multicolor16', '16 multicolor'), ('parent_pairs8', '8 chromatic pairs'), ('pooled24', 'All 24')]:
    for model, name in [('km', 'Fold K-M'), ('interaction', 'Empirical'), ('v1_reference', 'V1 (21-row reference)')]:
        a = s['subsets'][role][model]
        de, rmse = a['delta_e_2000'], a['spectral_rmse']
        score_rows.append([label, name, f"{de['mean']:.3f}", f"{de['p95']:.3f}", f"{de['max']:.3f}",
                           f"{rmse['mean']:.5f}", f"{rmse['p95']:.5f}"])
scores = table(['Set', 'Model', 'Mean DE00', 'P95 DE00', 'Max DE00', 'Mean RMSE', 'P95 RMSE'], score_rows)
group_rows = []
for g in s['groups'].values():
    a, b = [g['metrics'][name]['delta_e_2000']['mean'] for name in ('km', 'interaction')]
    group_rows.append([g['ratio'], ', '.join(map(str, g['test_rows'])), g['train_count'],
                       f'{a:.3f}', f'{b:.3f}', 'improves' if b < a else 'worsens'])
groups = table(['Y:R:B ratio', 'Withheld source rows', 'Fit rows', 'K-M mean DE00', 'Empirical mean DE00', 'Change'], group_rows)
regressions = []
for r in rows:
    a, b = [float(r[name + '_delta_e_2000']) for name in ('km', 'interaction')]
    if b > a + 1e-12:
        regressions.append([r['source_row'], r['paint_family'], f'{a:.3f}', f'{b:.3f}', f'+{b-a:.3f}'])
regression_table = table(['Source row', 'Mixture', 'K-M DE00', 'Empirical DE00', 'Increase'], regressions)
primary = s['subsets']['multicolor16']
gain = 100 * (1 - primary['interaction']['delta_e_2000']['mean'] / primary['km']['delta_e_2000']['mean'])
old = s['previous_parent_available16']
runs = [r for model in s['optimizer'].values() for r in model['base']]
corrections = [model['correction'] for model in s['optimizer'].values()]
timing = sum(r['elapsed_seconds'] for r in runs + corrections)

text = f"""# Chromatic-ratio families held out together

**The empirical improvement mostly survives the stricter split, with a persistent
red/blue weakness.** Mean multicolor color error is
{primary['interaction']['delta_e_2000']['mean']:.3f} DE00 versus
{primary['km']['delta_e_2000']['mean']:.3f} for K-M fitted on the same rows, a
{gain:.1f}% reduction. Eighteen of 24 assessed colors improve, five worsen and
one ties. Ten of 11 group means improve; the red/blue 1:1 group gets worse.
This is exploratory evidence from previously exposed data, not fresh validation.
No runtime, renderer, paper model or default was changed.

## What was held out

The [plan](PLAN.md) and all fitting code/settings were frozen before fitting.
The four pure samples and 17 single-paint white tints remain calibration anchors.
The other 24 recipes form 11 groups according to their Y:R:B ratio after removing
white. Each group includes the chromatic parent, where present, and all its
recorded white additions. No member of a scored group enters that fold's fit.
These are recipe groups, not a claim about shared physical preparation batches.

To isolate the effect of excluding related recipes, the training pool remains
the previous 29 rows. Each fold removes its group from that pool. Eight folds
therefore fit 28 rows. The three Y:R:B groups already had no training member and
share the same 29-row fit, giving nine unique fits for eleven folds. Other
multicolor assessment samples are never added to training. This is not generic
leave-one-group-out training on all remaining 45 samples; nor is it exclusion of
an entire paint pair such as every yellow/red ratio.

Both methods share the same fitted K-M base in each fold. The empirical model's
24 possible correction controls, objective, bounds and priors are unchanged.
When withholding the only yellow/blue parent, those four interaction controls
remain zero; the other paint-pair controls still operate in its white additions.
Pure and single-chromatic tint generalization is outside this test's scope.

## Results on identical samples

DE00 uses the existing truncated D65 / CIE 1931 2-degree pipeline without RGB
clipping. Spectral RMSE is measured on reflectance 0-1 over 31 bands. P95 is a
sample quantile, not a confidence bound. V1 is the unchanged 21-row reference;
the fold-specific K-M model is the direct matched-training comparator.

{scores}

For the same 16 multicolor samples, the earlier parent-available empirical score
was {old['interaction']['delta_e_2000']['mean']:.3f}; excluding each related parent
raises it to {primary['interaction']['delta_e_2000']['mean']:.3f}. K-M changes from
{old['v3']['delta_e_2000']['mean']:.3f} to {primary['km']['delta_e_2000']['mean']:.3f}.
The empirical model improves 13/16 multicolor colors and 12/16 spectral RMSEs.
The six recipes in the three Y:R:B groups are unchanged controls because their
training set was already unrelated to their own ratio group. The ten white-added
chromatic-pair recipes are the multicolor cases whose training actually changes.

Across all 24 recipes, empirical mean DE00 is 3.091 versus K-M's 3.917, and mean
spectral RMSE is 0.02462 versus 0.02772. Giving every ratio group equal weight
instead of every sample produces mean DE00 3.005 versus 3.910. Thus the benefit
does not depend only on larger groups receiving more weight.

## Group results and regressions

{groups}

![Mean color error by withheld chromatic-ratio group](groups.png)

Every color regression against the fold's K-M base is retained:

{regression_table}

The red/blue 1:1 group is the weakest result: its parent reaches DE00 9.561 and
both white additions also worsen. That fold has only the 9:1 red/blue parent
available for learning that pair's correction. This is a plausible sparse-ratio
limitation, not proof of its cause. The model also worsens the yellow/red 3:1
parent despite improving that group's average.

The 16-row empirical color scores pass the original mean/p95/max color screens,
but both spectral screens still fail. Spectral p95 is 0.06223 versus K-M's
0.06064, so mean improvement hides worse spectral tails. Across all 24 rows, the
empirical mean DE00 3.091 and p95 6.497 also exceed the original color limits
of 3 and 6; only the maximum-color limit of 10 passes among the five screens.
No threshold was changed or interpreted as measurement uncertainty.

## Verification and provenance

- Four new protocol tests pass: group membership/coverage, white and amount
  invariance, training-only arrays, and zero activation for an absent pair.
- Before fitting, {baseline['aggregate_statistics_checked']} archived baseline
  statistics were reproduced within {baseline['max_abs_difference']:.2g}.
- All 27 K-M starts and nine empirical fits converge without active bounds.
  K-M takes {min(r['nfev'] for r in runs)}-{max(r['nfev'] for r in runs)} evaluations
  per start; every correction takes eight. Total recorded optimizer time is
  {timing:.3f} seconds, excluding startup/checks and unrelated to renderer speed.
- Independent scalar decoding agrees within
  {check['independent_scalar_max_abs']:.2g} reflectance; pure endpoints drift by at
  most {check['pure_max_abs']:.2g}. Every fitted model predicts finite bounded
  reflectance on all 45 recorded recipes.
- Actual refits after perturbing every non-training spectrum leave all fitted
  K-M and empirical coefficients exactly unchanged for all nine unique splits.
- The prepared manifest hashes source data, settings, implementation, plan,
  colorimetry and previous artifacts. All fits were saved before scoring, and
  evaluation/verification leave the coefficient bundle unchanged.

Frozen local coefficient bundle SHA-256:
`{s['model_bundle_sha256']}`.

The full [summary](summary.json), [per-row errors](errors.csv),
[baseline check](baseline-check.json) and [verification](verification.json) are
retained. Coefficients remain under ignored `target/measured-oils/grouped-ratios`.
Pooled scores combine fold-specific models and are not one deployable palette.
Overlapping folds and the small, reused dataset do not justify an independent
confidence claim. No model parameters were changed after assessment.

## Decision

Continue treating the empirical correction as a promising experimental appearance
predictor. The benefit persists when chromatic parents and their white additions
are withheld together, but broad accuracy and generalization across preparation
conditions remain unestablished. Red/blue ratio coverage is the clearest next
measurement priority. Before another model change, inspect that trajectory and
obtain additional ratios or independent data rather than tuning to the same
red/blue failures. Keep the current runtime/default and paper implementation.

## Reproduction

From the repository root, using the existing scientific Python environment:

```powershell
& target/measured-oils/venv/Scripts/python.exe -m unittest discover -s experiments/oil_grouped -p test_protocol.py -v
& target/measured-oils/venv/Scripts/python.exe experiments/oil_grouped/run.py prepare --out target/measured-oils/grouped-ratios-repeat
& target/measured-oils/venv/Scripts/python.exe experiments/oil_grouped/run.py fit --out target/measured-oils/grouped-ratios-repeat
& target/measured-oils/venv/Scripts/python.exe experiments/oil_grouped/run.py verify --out target/measured-oils/grouped-ratios-repeat
& target/measured-oils/venv/Scripts/python.exe experiments/oil_grouped/run.py evaluate --out target/measured-oils/grouped-ratios-repeat
& target/measured-oils/venv/Scripts/python.exe experiments/oil_grouped/report.py
```

Use a fresh output directory; frozen coefficients are never overwritten. Evaluate
and verify also refresh this directory's derived reports, while retaining the
original fitted bundle in its separate output directory. Recipe grouping depends
on the documented source; see the plan for the complete fixed protocol.
"""
(HERE / 'REPORT.md').write_bytes(text.encode('utf-8'))

fig, ax = plt.subplots(figsize=(10, 7.5), layout='constrained')
group_values = list(s['groups'].values())
y = np.arange(len(group_values))
for shift, key, label, color in [(-.18, 'km', 'K-M fitted on the same rows', '#8d9ba5'),
                                (.18, 'interaction', 'Empirical pair correction', '#217b7e')]:
    values = [g['metrics'][key]['delta_e_2000']['mean'] for g in group_values]
    bars = ax.barh(y + shift, values, .33, label=label, color=color)
    ax.bar_label(bars, fmt='%.2f', padding=4, fontsize=9)
ax.set_yticks(y, [f"{g['ratio']}  (n={len(g['test_rows'])})" for g in group_values])
ax.invert_yaxis()
ax.set_ylabel('Withheld Y:R:B ratio, including all recorded white additions')
ax.set_xlabel('Mean CIEDE2000 per group (lower is better)')
ax.set_xlim(0, 8.6)
ax.grid(axis='x', alpha=.2)
ax.set_axisbelow(True)
ax.legend(loc='lower right', fontsize=9)
ax.set_title('Grouped recipe assessment: 24 samples in 11 groups\nExploratory; original calibration anchors retained', pad=15)
for tick, group in zip(ax.get_yticklabels(), group_values):
    if group['ratio'] == '0:1:1':
        tick.set_color('#a23f3f')
        tick.set_fontweight('bold')
fig.savefig(HERE / 'groups.png', dpi=170)
plt.close(fig)
print('Wrote REPORT.md and groups.png')
