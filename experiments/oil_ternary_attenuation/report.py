"""Report the single frozen revision, including its failure to beat K-M."""
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def table(headers, records):
    return '\n'.join(['| '+' | '.join(headers)+' |', '| '+' | '.join(['---']*len(headers))+' |']+
                     ['| '+' | '.join(map(str, row))+' |' for row in records])


def main():
    summary = json.loads((HERE/'summary.json').read_text(encoding='utf-8'))
    verification = json.loads((HERE/'verification.json').read_text(encoding='utf-8'))
    rows = list(csv.DictReader((HERE/'errors.csv').open(newline='')))
    primary = [r for r in rows if r['variant'] == 'base' and r['role'] == 'chromatic3']
    labels = ['Bcy', 'bCy', 'bcY']
    primary.sort(key=lambda r: labels.index(r['sample']))
    assert all(f['lambda'] == 1 and f['at_upper_bound'] for f in summary['fits'])
    assert all(f['profile_nondecreasing_steps'] == 0 for f in summary['fits'])
    assert all(float(r['attenuated_spectral_rmse']) < float(r['original_spectral_rmse'])
               for r in rows if r['role'] == 'chromatic3')
    base = summary['variants']['base']['assessments']
    a = base['chromatic3_primary']
    primary_table = table(['Frozen model', 'Mean RMSE', 'p95 RMSE', 'Maximum RMSE', 'Mean windowed DE00'],
        [[label]+[f"{a[key]['spectral_rmse'][metric]:.6f}" for metric in ['mean','p95','max']]+
         [f"{a[key]['delta_e_2000']['mean']:.4f}"] for key, label in
         [('km','K-M'),('original','Original empirical correction'),('attenuated','Attenuated correction')]])
    per_row = table(['Excluded recipe', 'Ternaries used for lambda', 'K-M RMSE', 'Original RMSE', 'Attenuated RMSE'],
        [[r['sample'], ', '.join(x for x in labels if x != r['sample'])]+
         [f"{float(r[k+'_spectral_rmse']):.6f}" for k in ['km','original','attenuated']] for r in primary])
    range_rows = []
    for tolerance, result in summary['sensitivity'].items():
        original = result['primary_comparison']['original_spectral_rmse']['improvement_percent_range']
        km = result['primary_comparison']['km_spectral_rmse']['improvement_percent_range']
        range_rows.append([tolerance, result['mappings'], f'{original[0]:.2f}-{original[1]:.2f}%', f'{-km[1]:.2f}-{-km[0]:.2f}%'])
    variant_rows = []
    for key, result in summary['variants'].items():
        d = result['assessments']['chromatic3_primary']
        assert d['attenuated']['spectral_rmse']['mean'] > d['km']['spectral_rmse']['mean']
        assert d['attenuated']['delta_e_2000']['mean'] > d['km']['delta_e_2000']['mean']
        rr = [r for r in rows if r['variant'] == key and r['role'] == 'chromatic3']
        variant_rows.append([key, ', '.join(result['changed_subset_labels']) or '(base)']+
            [f"{d[k]['spectral_rmse']['mean']:.6f}" for k in ['km','original','attenuated']]+
            [sum(float(r['attenuated_spectral_rmse']) < float(r['km_spectral_rmse']) for r in rr)])
    contextual = []
    for role, label in [('white9_unchanged','9 white ternaries (unchanged)'), ('pairs9_unchanged','9 pairs (unchanged)'),
                        ('ternary12_composite','12 ternaries (composite)'), ('all21_composite','21 rows (composite)')]:
        contextual.append([label]+[f"{base[role][k]['spectral_rmse']['mean']:.6f}" for k in ['km','original','attenuated']])
    fits = [f for f in summary['fits'] if f['variant'] == 'base']
    fit_table = table(['Excluded recipe', 'Lambda', 'Original calibration MSE', 'Attenuated calibration MSE'],
        [[f['excluded'], f"{f['lambda']:.1f}", f"{f['original_calibration_mse']:.8f}", f"{f['calibration_mse']:.8f}"] for f in fits])

    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.9), layout='constrained')
    x = np.arange(3)
    for offset, key, label, color in [(-.25,'km','K-M','#55718c'),(0,'original','Original correction','#c37951'),(.25,'attenuated','Attenuated correction','#238678')]:
        axes[0].bar(x+offset, [float(r[key+'_spectral_rmse']) for r in primary], .24, label=label, color=color)
    axes[0].set_xticks(x, ['Blue-heavy\nBcy','Carmine-heavy\nbCy','Yellow-heavy\nbcY'])
    axes[0].set_ylabel('Excluded-target spectral RMSE'); axes[0].legend(frameon=False, fontsize=9)
    axes[0].set_title('Attenuation limits harm; mean K-M error is still lower', fontsize=11, fontweight='bold', pad=12)
    axes[0].set_ylim(0,.038)
    profiles = np.load(ROOT/'target/measured-oils/ternary-attenuation/calibration-profiles.npz')
    for label, color in zip(labels, ['#55718c','#c37951','#238678']):
        values = profiles['base/'+label]
        axes[1].plot(np.linspace(0,1,1001), values/values[0], color=color, label='Exclude '+label)
    axes[1].set_xlabel('Attenuation strength lambda'); axes[1].set_ylabel('Calibration MSE / original calibration MSE')
    axes[1].set_xlim(0,1); axes[1].set_ylim(0,1.05); axes[1].legend(frameon=False, fontsize=9)
    axes[1].set_title('All calibration profiles prefer the upper bound', fontsize=11, fontweight='bold', pad=12)
    fig.suptitle('One constrained revision: three exposed recipes, inferred identities\nLeft: excluded target. Right: the other two recipes used for calibration.', fontsize=13)
    fig.savefig(HERE/'comparison.png', dpi=160); plt.close(fig)

    checks = verification['checks']
    report = f'''# Ternary attenuation: less harm, but no advantage over K-M

**The single revision improves on the original empirical correction but fails to
beat the frozen K-M baseline on the primary mean error.** For the three excluded
chromatic ternaries, mean spectral RMSE is 0.017338 with attenuation, 0.024189 with
the original correction, and 0.016568 with K-M. Attenuation reduces the original
correction's error by 28.3%, but remains 4.65% worse than K-M.

This conclusion holds across all seven tested inferred mappings: the revision
improves on the original correction by 28.1-30.8%, but remains 4.4-5.4% worse than
K-M. Every fit chooses the maximum allowed attenuation.
The evidence supports limiting a harmful residual correction, not learning more
accurate three-pigment paint behavior. **Do not promote this revision to the
runtime or treat the result as independent validation.**

![Excluded-target errors and calibration-only strength profiles](comparison.png)

## Fixed rule and sequence

The [plan](PLAN.md) and implementation were frozen before any revision fit or
assessment. The earlier [diagnosis](../oil_white_split/REPORT.md) motivated this
one candidate. All K-M coefficients and empirical pair curves stayed frozen in
the original bundle:

`8090dd57ce49b584fcae15cdb85eafbe942a4181c97f53b27a95d22265bc1ced`

For normalized total paint fractions, the rule is:

```
h = 27 * cY * cC * cB
0 <= lambda <= 1
new_shift = (1 - lambda*h)*chromatic_pair_shift + white_pair_shift
prediction = sigmoid(logit(KM_prediction) + new_shift)
```

The factor 27 normalizes the gate at equal thirds; it was not normalized to the
three observed recipes. The gate is smooth and bounded. It vanishes whenever a
chromatic pigment is absent, preserving every binary mixture and the current
white-containing ternaries. In mixtures containing all four paints it attenuates
only the chromatic terms; there are no such measured assessment samples here.
Numerical boundedness on those recipes does not establish their accuracy.

The three observed chromatic ternaries are all 2:1:1, giving h=27/32. At the fitted
lambda=1, they retain **15.625%** of the original chromatic logit correction.
This is not a 15.625% linear interpolation of reflectance. The fixed bound was
not widened after observing results, and no alternative gate was tested.

For each mapping, the three ternaries share the original 22-row binary/pure
calibration model. Each new scalar fit sees only two ternary targets and is scored
on the excluded third. This rotates through three exclusions across seven
mappings: 21 fits, but only three physical recipe labels. Identical primary
models across some mappings also share identical fit outcomes.

The scalar objective is mean squared spectral error on the two calibration
samples over the existing 31 bands at 440-740 nm. Bounded scalar minimization and
both endpoints are compared. A 1001-point calibration-only profile checks the
chosen objective. All scalar coefficients were frozen, verified, then evaluated.
No K-M or pair-curve fitting entry point is enabled in this experiment.

## Primary excluded-target results

{primary_table}

{per_row}

All three excluded samples improve over the original correction under every
mapping. In the base map only the yellow-heavy sample improves slightly over
K-M in spectral RMSE; blue-heavy and carmine-heavy remain worse. All three base-map
windowed color errors remain worse than K-M. The mean color advantage over K-M
is absent under every mapping too.

Windowed DE00 uses the existing D65/2-degree 440-740 nm convention with a matching
truncated white. It is not full-visible color error. Percentile statistics over
three samples are descriptive, not population estimates.

## The parameter hits its limit in every fit

All 21 optimizations succeeded and selected lambda=1. Each bounded optimizer used
37 objective evaluations, plus the explicitly checked endpoints and diagnostic
profile. All 1000 successive steps in every sampled calibration profile reduce
the objective as attenuation increases. No intermediate optimum was selected.

{fit_table}

These are losses on the **two calibration ternaries**, separate from the excluded
errors above. The consistent boundary solution says the calibration prefers to
suppress more of the learned correction within the allowed rule. It does not
identify a subtle strength or prove that the chosen gate captures paint physics.

All observed ternaries have the same gate value, so this dataset cannot establish
the gate's composition dependence. It primarily tests a shared shrinkage of the
correction at one composition pattern. K-M remains the stronger primary reference
after that shrinkage; adjusting the gate again to eliminate the remaining gap
would be another exposed-data revision, not fresh evidence.

## Mapping sensitivity

The seven projections are the same frozen feasible alternatives used previously.
No label was selected or changed to favor this revision.

{table(['Diagnostic mean-MSE tolerance', 'Mappings', 'RMSE reduction vs original', 'RMSE increase vs K-M'], range_rows)}

{table(['Mapping', 'Changed selected recipes', 'K-M mean RMSE', 'Original mean RMSE', 'Attenuated mean RMSE', 'Rows beating K-M / 3'], variant_rows)}

The uncertainty range is conditional on the paired-scan hypothesis and fixed
pure identities. These are not probability bounds over unrestricted labelings.

## The previously successful mixtures are preserved

All nine white ternaries and nine pair assessments remain **bit-identical** to
the original empirical decoder under every fitted strength and mapping: 126
unchanged model/observation assessments. Their own previous grouped K-M and
empirical models are retained. Only the three chromatic ternaries receive the
new excluded-target scalar predictions.

{table(['Assessment', 'K-M mean RMSE', 'Original mean RMSE', 'Attenuated mean RMSE'], contextual)}

The twelve- and twenty-one-row totals combine the old grouped assessment with
the new scalar exclusion protocol. They improve as expected when the three bad
predictions improve, but the new model has additional ternary calibration data.
These composite totals must not be presented as an unchanged-budget rerun of the
original benchmark or used to conceal the primary failure to beat K-M.

## Verification

- All 21 fits were repeated after perturbing the excluded target. Lambda and
  calibration objective remained exactly unchanged.
- All 147 original assessment records reproduced exactly (maximum difference {summary['original_assessment_replay_max_abs']:.3g}).
- Independent scalar decoding agrees within {checks['scalar_max_abs']:.3g}; pure endpoints within {checks['pure_max_abs']:.3g}.
- Lambda zero preserves original decoder bits. Each unique primary model was
  checked on 906 unaffected face/edge recipes, also with bit-identical predictions.
- Each unique primary model was checked on 1029 recipes for finite bounded
  spectra at lambda 0, .5 and 1. Representative tiny third-pigment fractions
  down to 1e-12 satisfy the declared continuous-change bound.
- At equal thirds and lambda=1, the decoder reproduces K-M. This is a mathematical
  check on an unmeasured recipe, not a claim of real-paint accuracy there.
- Source, mapping, original coefficients, implementation and protocol hashes
  remain unchanged. Both frozen bundles stayed byte-identical through scoring.

The new scalar bundle SHA-256 is:

`{summary['frozen_sha256']}`

It and the calibration profiles are kept under ignored
`target/measured-oils/ternary-attenuation/`. Detailed derived outputs are in
[summary.json](summary.json), [errors.csv](errors.csv) and
[verification.json](verification.json).

## Decision and limits

Retain the diagnosis and this negative comparison with K-M as research evidence.
The experiment supports the concern that additive binary residual corrections
should not be trusted automatically in three-chromatic-pigment interiors. It
does not justify this particular gate as a better optical model or a new default.

Before another correction is proposed, seek evidence from additional three-pigment
compositions in existing public measurements. Broader ratios and pigment sets
would test whether the failure pattern generalizes and provide information that
these three identically shaped recipes cannot supply. Keep any new study separate
from this completed experiment and from the paper-faithful implementation.

All three targets already influenced the research direction through diagnosis.
The exclusion protocol prevents direct fitting to each reported target, but does
not undo that exposure. The underlying source map also used aggregate published
scores. This remains exploratory under inferred labels, with no independent
physical validation, significance claim, product promotion or renderer change.

## Reproduction

Use the existing checksum-verified source cache and scientific environment from
the [source reconstruction](../oil_source_recovery/REPRODUCE.md). Run in order:

```powershell
.\\target\\measured-oils\\venv\\Scripts\\python.exe experiments/oil_ternary_attenuation/run.py prepare
.\\target\\measured-oils\\venv\\Scripts\\python.exe experiments/oil_ternary_attenuation/run.py fit
.\\target\\measured-oils\\venv\\Scripts\\python.exe experiments/oil_ternary_attenuation/run.py verify
.\\target\\measured-oils\\venv\\Scripts\\python.exe experiments/oil_ternary_attenuation/run.py evaluate
.\\target\\measured-oils\\venv\\Scripts\\python.exe experiments/oil_ternary_attenuation/report.py
```

Prepare and fit refuse to overwrite frozen output. Use one fresh `--out` path
under target/ for all four run phases to repeat the experiment. The report script
uses the saved versioned scores and the original default calibration profile
cache. Original experiments and coefficients are never overwritten.
'''
    (HERE/'REPORT.md').write_bytes(report.encode('utf-8'))
    print('Saved report and comparison figure')


if __name__ == '__main__': main()
