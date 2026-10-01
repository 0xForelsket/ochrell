"""Present frozen component attributions and clearly separate hypotheses."""
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
    read = lambda file: list(csv.DictReader((HERE/file).open(newline='')))
    rows = read('observations.csv'); components = read('components.csv'); calibration = read('calibration.csv')
    coverage = read('coverage.csv'); regions = read('spectral-regions.csv')
    base = [r for r in rows if r['variant'] == 'base']
    chromatic = [r for r in base if r['kind'] == 'chromatic_ternary']
    assert all(r['same_nominal_ratio_in_calibration'] == 'True' for r in coverage if r['sample'] in ['Bcy', 'bCy', 'bcY'])
    for variant in summary['groups'].values():
        assert variant['chromatic_ternary']['diagnoses'] == {'opposite_direction': 2, 'overshoot': 1, 'improves': 0}
    primary_model = chromatic[0]['model']
    assert len({r['model'] for r in chromatic}) == 1
    data = np.load(ROOT/'target/measured-oils/white-split-diagnosis/spectra.npz')
    nm = np.arange(440, 741, 10)
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                         'axes.spines.top': False, 'axes.spines.right': False})
    fig, axes = plt.subplots(2, 3, figsize=(13, 7), layout='constrained')
    titles = ['Blue-heavy (Bcy)', 'Carmine-heavy (bCy)', 'Yellow-heavy (bcY)']
    for column, r in enumerate(chromatic):
        name = r['sample']; ax = axes[0, column]
        for key, label, color, style in [('measured', 'Measured (inferred identity)', '#222222', '-'),
             ('km', 'K-M baseline', '#56728f', '--'), ('full', 'Empirical correction', '#c26b3d', '-')]:
            ax.plot(nm, data[name+'_'+key], color=color, linestyle=style, label=label, linewidth=2)
        ax.set_title(titles[column], fontweight='bold'); ax.set_ylabel('Reflectance'); ax.set_xlabel('Wavelength (nm)')
        ax = axes[1, column]
        ax.axhline(0, color='#aaaaaa', linewidth=.7)
        ax.plot(nm, data[name+'_measured']-data[name+'_km'], color='#222222', label='Needed: measured minus K-M', linewidth=2)
        ax.plot(nm, data[name+'_full']-data[name+'_km'], color='#c26b3d', label='Actual: corrected minus K-M', linewidth=2)
        ax.set_ylabel('Reflectance displacement'); ax.set_xlabel('Wavelength (nm)')
        ax.set_title('Opposite direction overall' if r['diagnosis'] == 'opposite_direction' else 'Weak alignment; full step overshoots', fontsize=10)
    axes[0, 0].legend(fontsize=8); axes[1, 0].legend(fontsize=8)
    fig.suptitle('Three chromatic pigments: the learned binary corrections do not transfer reliably\nFrozen base mapping and coefficients; no fitting in this diagnosis', fontsize=13)
    fig.savefig(HERE/'chromatic-spectra.png', dpi=160); plt.close(fig)

    names = ['YC', 'YB', 'YW', 'CB', 'CW', 'BW']
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), layout='constrained')
    for ax, kind, title in zip(axes, ['white_ternary', 'chromatic_ternary'], ['9 ternaries with white', '3 ternaries without white']):
        group = summary['groups']['base'][kind]
        values = [group['shapley_MSE_reduction_sum'][p]/group['count']*1e4 for p in names]
        ax.bar(names, values, color=['#208878' if x >= 0 else '#c26b3d' for x in values])
        ax.axhline(0, color='#555555', linewidth=.7); ax.set_title(title, fontweight='bold')
        ax.set_ylabel('Attributed mean MSE reduction (x 10^-4)')
    fig.suptitle('Pair contributions: positive helps, negative harms\nExact Shapley allocation of frozen spectral MSE changes; panels use different scales', fontsize=12)
    fig.savefig(HERE/'pair-attribution.png', dpi=160); plt.close(fig)

    failure_rows = []
    for r, label in zip(chromatic, titles):
        rr = [v for v in rows if v['sample'] == r['sample']]
        failure_rows.append([label, f"{float(r['km_spectral_rmse']):.6f}", f"{float(r['full_spectral_rmse']):.6f}",
            f"{float(r['correction_projection_alpha']):+.3f}",
            f"{min(float(v['correction_projection_alpha']) for v in rr):+.3f} to {max(float(v['correction_projection_alpha']) for v in rr):+.3f}",
            'Wrong direction' if r['diagnosis'] == 'opposite_direction' else 'Overshoot'])
    counterfactuals = []
    for r in chromatic:
        counterfactuals.append([r['sample']]+[f"{float(r[k+'_spectral_rmse']):.6f}" for k in ['km', 'full', 'without_YC', 'without_YB', 'without_CB']])
    white = summary['groups']['base']['white_ternary']
    white_table = table(['Frozen components included', 'Mean RMSE on 9 white ternaries'],
        [[label, f"{white['means'][key]['spectral_rmse']:.6f}"] for key, label in
         [('km', 'None (K-M)'), ('chromatic_only', 'Chromatic-pair terms only'), ('white_only', 'White-pair terms only'), ('full', 'All terms')]])
    cal_rows = []
    for pair in ['YC', 'YB', 'CB', 'YW', 'CW', 'BW']:
        selected = [r for r in calibration if r['model'] == primary_model and r['pair'] == pair]
        cal_rows.append([pair, ', '.join(r['sample'] for r in selected),
            f"{np.mean([float(r['km_spectral_rmse']) for r in selected]):.6f}",
            f"{np.mean([float(r['full_spectral_rmse']) for r in selected]):.6f}",
            sum(float(r['full_spectral_rmse']) < float(r['km_spectral_rmse']) for r in selected)])
    white_contrib = sum(white['shapley_MSE_reduction_sum'][p] for p in ['YW', 'CW', 'BW'])
    all_contrib = sum(white['shapley_MSE_reduction_sum'].values())
    region_rows = []
    for r in chromatic:
        reg = next(v for v in regions if v['variant'] == 'base' and v['sample'] == r['sample'] and v['lo_nm'] == '600')
        region_rows.append([r['sample'], f"{float(r['mse_change']):.8f}",
            f"{float(reg['contribution_to_total_MSE_change']):.8f}",
            f"{100*float(reg['contribution_to_total_MSE_change'])/float(r['mse_change']):.1f}%"])
    checks = summary['checks']
    report = f'''# Why the frozen correction helps white mixtures and harms chromatic ternaries

**The failure is the transfer of separately learned pair corrections into a
three-chromatic-pigment mixture.** All calibration mixtures contain at most two
materials. Their correction terms are learned in isolation; a ternary prediction
then adds three such terms. That extra assumption is not tested by calibration.
The physical K-M base already performs relatively well on the three no-white
ternaries, and the added residual corrections move two in the wrong overall
spectral direction and overshoot the third.

This is a diagnosis of model behavior, not proof of a particular physical paint
mechanism. All seven feasible selected-palette mappings support the same
direction/overshoot classification. Source identities remain inferred, and these
are previously exposed observations. No model was fitted or changed.

## 1. It is not a general inability to mix without white

The prior grouped assessment improved eight of nine held-out two-chromatic-pigment
mixtures. In the full 22-row calibration fit used for the three Y/C/B ternaries,
all nine chromatic binary calibration mixtures also improve. The breakdown
appears when **three chromatic pigments act together**, not whenever white is
absent.

The calibration pool has four pure samples and eighteen binary mixtures: three
ratios for each of six pigment pairs. Each binary observation activates one pair
correction; pures activate none. There is no ternary calibration observation.
After the K-M base is frozen, the empirical data loss and separable regularizer
contain no cross-pair terms. The off-block feature Gram entries are exactly zero.
Thus each empirical pair curve learns how to repair its own binary residuals,
with no observation showing how those repairs interact with another pigment.

The held-out Y/C/B samples use 2:1:1 recipes. Every internal pair ratio (1:1,
2:1 or 1:2) is represented in that full calibration fit. This is not a missing
binary ratio. It is missing **third-pigment context**. Stored binary concentrations
are rounded .33/.67, while ternary proportions give exact nominal ratios; the
unchanged fitter retains those released fractions.

For pigment fractions `c`, a pair contributes
`4*c_i*c_j * h_ij(wavelength)` to the logit of the K-M reflectance. The fitted
spectral curve `h_ij` has no dependence on the identity of a third pigment.
Every measured ternary activates three pairs with weights .5, .5 and .25, whose
sum is 1.25. Binary calibration activates one pair with weight at most 1.
This is outside the calibration feature combinations even though the recipes
are ordinary mixtures. However, white-containing ternaries have the same total
weight 1.25, so that scalar total alone does not explain which mixtures fail.

## 2. Wrong direction in two mixtures, overshoot in one

Let `d = corrected - K-M` and `needed = measured - K-M`. The exact spectral-MSE
change is `mean(d*d) - 2*mean(d*needed)`. The diagnostic projection
`alpha = dot(d,needed)/dot(d,d)` separates the two contributions:

- Negative alpha: the frozen reflectance displacement points away from the
  measured residual overall. Any positive step along that displacement increases
  squared error.
- Alpha between 0 and .5: some alignment exists, but the full displacement is
  large enough to increase squared error.
- Alpha above .5: the full displacement reduces squared error.

This is an explanatory calculation in reflectance space using exposed measured
targets. It is not a fitted parameter, logit-scaling prescription or proposed
production decoder.

{table(['Mixture', 'K-M RMSE', 'Full RMSE', 'Base alpha', 'Alpha across 7 maps', 'Diagnosis'], failure_rows)}

The carmine-heavy mixture is the clearest failure: K-M RMSE is about 0.00851,
while the correction displacement itself has RMS 0.01945 and points away from
the required change overall. The final RMSE becomes 0.02544. There is substantial
spectral-shape mismatch, not merely a uniformly excessive correction amplitude.

![Measured spectra, frozen predictions and displacement directions](chromatic-spectra.png)

The 600-740 nm interval accounts for most of the net MSE increase in all three
base-map failures. Contributions are summed squared-error changes divided by
all 31 bands, so they add exactly to each sample's total MSE change.

{table(['Mixture', 'Total MSE increase', '600-740 nm contribution', 'Share of net increase'], region_rows)}

## 3. There is no single pair that can simply be deleted

Pair terms add in logit space; reflectance, RMSE and color errors are nonlinear.
We therefore enumerated all subsets of active terms and calculated exact Shapley
allocations of the **MSE reduction**. They sum to the measured change and include
interactions caused by the nonlinear decoder. They are model attributions, not
fractions of a physical cause.

![Pair attributions in white and chromatic ternaries](pair-attribution.png)

For the three no-white ternaries taken together, Y/B is the largest harmful
attribution under every mapping. But its role reverses by sample: it harms the
blue-heavy and yellow-heavy mixtures while helping the carmine-heavy mixture in
combination with other terms. In that carmine-heavy mixture the Y/C and C/B terms
cause the larger harm. Removing Y/B globally would therefore not fix the pattern.

These base-map removals show the distinction directly. Lower RMSE is better;
none of these counterfactuals is fitted or selected as a replacement.

{table(['Mixture', 'K-M', 'All pairs', 'Without YC', 'Without YB', 'Without CB'], counterfactuals)}

## 4. Why the white-containing mixtures benefit

White-containing ternaries activate one chromatic pair and two white pairs.
The chromatic-pair weight is only .25 or .5, versus a combined 1.25 across
chromatic pairs in a Y/C/B ternary. The white-pair curves supply additional,
separately calibrated corrections. Their K-M baseline also has substantially
more error to correct: mean RMSE 0.04088 versus 0.01657 for the no-white ternaries.

{white_table}

Both groups of terms help on average, and their combination helps more. On the
base mapping, white-pair terms account for {100*white_contrib/all_contrib:.1f}% of
the summed MSE reduction under the exact allocation; chromatic-pair terms account
for the rest. This is not simply a successful white term masking uniformly bad
chromatic terms. The chromatic correction itself behaves better in those
white-containing contexts. The aggregate benefit of both groups persists across
all seven mappings. Individual mixtures can still regress.

## 5. The binary fits support a correction, not its unrestricted transfer

The following are **training errors**, shown only to diagnose coverage and fit.
They use the full calibration model shared by the three chromatic ternaries;
they are not the grouped holdout scores from the previous report.

{table(['Pair', 'Calibration recipes', 'Mean K-M RMSE', 'Mean corrected RMSE', 'Improved / 3'], cal_rows)}

All nine chromatic binary calibration rows improve, so the ternary failure is
not explained by the correction simply failing its observed chromatic pairs.
Binary calibration is still imperfect. In particular, the Y/W curve trades a
large improvement on `Wy` against regressions on `WY` and `wY`. The earlier
optimizer audit found no K-M bound hits and only zero or one bounded empirical
control per fit; optimizer nonconvergence is not the observed explanation.

The supported conclusion is narrower than "real paint has a three-way chemical
interaction." A residual learned from one optical-model error need not transfer
as an additive physical property. Other explanations, including remaining source
alignment uncertainty, film/binder differences or limitations of the K-M base,
are not identified by these calculations. We have isolated the unsupported model
assumption and its numerical failure, not the physical root cause.

## Proposed next experiment, not performed

Test one bounded, shared attenuation of the empirical correction when all three
chromatic pigments are present, keeping the K-M base and learned pair curves
frozen. It should preserve binary mixtures and the current white-containing
ternaries exactly. Its parameter is **unidentifiable from the present binary-only
calibration**: such a term has no effect on any calibration sample. It therefore
requires explicitly adding ternary calibration information, not another optimizer
run over the same 22 rows.

With the existing public subset, a small exploratory test could fit that single
parameter on two Y/C/B ternaries and assess the excluded third, rotating through
all three exclusions. Freeze the attenuation function, bound, objective and splits
before scores; retain the original K-M and unmodified correction as comparisons.
Do not silently count fitted ternaries as held-out observations. This would be
an exposed-data, three-fold diagnostic, not new independent validation, and
attenuation can only limit harm rather than learn the correct missing spectral
shape. Keep it separate from the paper-faithful implementation.

## Reproducibility and limits

The [plan](PLAN.md) specifies these analyses. [observations.csv](observations.csv)
contains all 147 grouped observations and the component counterfactuals;
[components.csv](components.csv) contains pair weights and exact allocations;
[coverage.csv](coverage.csv) records ratio support;
[calibration.csv](calibration.csv) keeps training errors explicitly separate;
[spectral-regions.csv](spectral-regions.csv) records wavelength contributions.
Source-derived spectra remain under ignored
`target/measured-oils/white-split-diagnosis/spectra.npz`.

All 147 prior assessment records reproduce within {checks['saved_error_max_abs']:.3g}.
Independent scalar predictions agree within {checks['scalar_max_abs']:.3g}, pair
recombination within {checks['recombination_max_abs']:.3g}, and exact MSE allocation
within {checks['shapley_sum_max_abs']:.3g}. Pure endpoints are preserved, absent-pair
removals do nothing, and component predictions are finite and bounded. Fitting
entry points are disabled in the diagnostic process. The coefficient bundle,
original dependencies, inputs and mapping hashes remain unchanged.

```powershell
.\\target\\measured-oils\\venv\\Scripts\\python.exe experiments/oil_white_split/diagnose.py
.\\target\\measured-oils\\venv\\Scripts\\python.exe experiments/oil_white_split/report.py
```

The source ordering was reconstructed using aggregate published scores, so optical
holdout alone does not remove reconstruction bias. Seven alternative projections
cover the previously declared paired-scan family, not all possible identities.
There are only three no-white ternaries. Color metrics use the prior 440-740 nm
window and matching D65 white, not full-visible colorimetry. No additional real
measurements, new validation dataset, runtime changes or model revision were made.
'''
    (HERE/'REPORT.md').write_bytes(report.encode('utf-8'))
    print('Saved report and two figures')


if __name__ == '__main__': main()
