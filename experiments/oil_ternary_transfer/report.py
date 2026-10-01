"""Render the complete frozen transfer comparison, including tail regressions."""
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

HERE=Path(__file__).resolve().parent


def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+
                     ['| '+' | '.join(map(str,r))+' |' for r in rows])


def main():
    s=json.loads((HERE/'summary.json').read_text(encoding='utf-8'))
    v=json.loads((HERE/'verification.json').read_text(encoding='utf-8'))
    assert s['complete_primary'] and s['scored_rows']==35 and not s['failed_palettes']
    rows=list(csv.DictReader((HERE/'errors.csv').open(newline='')))
    assert len({r['source_row'] for r in rows})==35
    methods=['km','empirical','attenuated'];labels=['K-M','Original empirical','Fixed attenuation']
    headline=table(['Method','Mean RMSE','Median RMSE','p95 RMSE','Max RMSE','Mean windowed DE00'],
        [[label]+[f"{s['primary35'][method]['spectral_rmse'][stat]:.6f}" for stat in ['mean','median','p95','max']]+
         [f"{s['primary35'][method]['delta_e_2000']['mean']:.4f}"] for method,label in zip(methods,labels)])
    comparisons=table(['Comparison','Mean RMSE reduction','RMSE rows better / worse / tied','Mean DE00 reduction','DE00 rows better / worse / tied'],
        [[label,f"{s['comparisons'][key]['spectral_rmse']['improvement_percent']:+.2f}%",
          ' / '.join(str(s['comparisons'][key]['spectral_rmse'][x]) for x in ['improved','worsened','tied']),
          f"{s['comparisons'][key]['delta_e_2000']['improvement_percent']:+.2f}%",
          ' / '.join(str(s['comparisons'][key]['delta_e_2000'][x]) for x in ['improved','worsened','tied'])]
         for key,label in [('empirical_vs_km','Empirical vs K-M'),('attenuated_vs_km','Attenuation vs K-M'),('attenuated_vs_empirical','Attenuation vs empirical')]])
    macro=table(['Method','Equal-palette mean RMSE','Equal-palette mean DE00'],
        [[label,f"{s['macro_palette_means'][method]['spectral_rmse']:.6f}",f"{s['macro_palette_means'][method]['delta_e_2000']:.4f}"] for method,label in zip(methods,labels)])
    palette_rows=[];palette_csv=[]
    for key,p in s['palettes'].items():
        pair_support=p['palette']['pair_calibration_counts']
        record={'palette':key,'paint_names':'; '.join(p['palette']['paint_names'][:3]),
            'target_rows':','.join(map(str,p['palette']['assessment_rows_one_based'])),
            'calibration_count':len(p['palette']['calibration_rows_one_based']),
            'minimum_binary_pair_count':min(pair_support.values())}
        record.update({m+'_'+metric: p['metrics'][m][metric]['mean'] for m in methods for metric in ['spectral_rmse','delta_e_2000']})
        palette_csv.append(record)
        palette_rows.append([key.removeprefix('old-holland-'),record['target_rows'],record['calibration_count'],record['minimum_binary_pair_count']]+
            [f"{record[m+'_spectral_rmse']:.6f}" for m in methods])
    with (HERE/'palette-results.csv').open('w',encoding='utf-8',newline='') as file:
        writer=csv.DictWriter(file,fieldnames=list(palette_csv[0]),lineterminator='\n');writer.writeheader();writer.writerows(palette_csv)
    worse=sorted(rows,key=lambda r:float(r['empirical_spectral_rmse'])-float(r['km_spectral_rmse']),reverse=True)[:5]
    worse_table=table(['Source row','Three paints','Gate h','K-M RMSE','Empirical RMSE','Attenuated RMSE'],
        [[r['source_row'],r['paints'],f"{float(r['gate']):.4f}"]+[f"{float(r[m+'_spectral_rmse']):.6f}" for m in methods] for r in worse])
    worst=max(rows,key=lambda r:float(r['empirical_spectral_rmse']))
    base_runs=[r for p in s['palettes'].values() for r in p['optimizer']['base']]
    emp_runs=[p['optimizer']['empirical'] for p in s['palettes'].values()]
    assert all(r['success'] for r in base_runs+emp_runs)
    assert all(r['bound_variables']==0 for r in base_runs)
    c=v['checks']

    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(1,2,figsize=(12.5,4.8),layout='constrained')
    colors=['#55718c','#218878','#c37b4e']
    for method,label,color,offset in zip(methods,labels,colors,[-.25,0,.25]):
        axes[0].bar(np.arange(2)+offset,[s['primary35'][method]['spectral_rmse'][k] for k in ['mean','p95']],.24,color=color,label=label)
    axes[0].set_xticks([0,1],['Mean RMSE','95th percentile RMSE']);axes[0].set_ylabel('Spectral reflectance error')
    axes[0].set_title('Modest mean gain; larger errors in the tail',fontweight='bold',fontsize=11)
    axes[0].legend(frameon=False,fontsize=9);axes[0].set_ylim(0,.094)
    for method,label,color,offset in zip(methods,labels,colors,[-.25,0,.25]):
        axes[1].bar(np.arange(2)+offset,[s['primary35'][method]['delta_e_2000']['mean'],s['macro_palette_means'][method]['delta_e_2000']],.24,color=color,label=label)
    axes[1].set_xticks([0,1],['35 samples, equal weight','25 palettes, equal weight']);axes[1].set_ylabel('Mean windowed DE00')
    axes[1].set_title('Original correction retains the color advantage',fontweight='bold',fontsize=11);axes[1].set_ylim(0,5)
    fig.suptitle('Additional Old Holland ternaries: unchanged methods, pure/binary calibration only\n35 assessment rows across 25 paint triples; 400-700 nm',fontsize=13)
    fig.savefig(HERE/'comparison.png',dpi=160);plt.close(fig)

    fig,ax=plt.subplots(figsize=(10,5),layout='constrained')
    gates=np.array([float(r['gate']) for r in rows]);delta=np.array([float(r['empirical_spectral_rmse'])-float(r['km_spectral_rmse']) for r in rows])
    ax.scatter(gates,delta,c=np.where(delta<0,'#218878','#c37b4e'),s=50,alpha=.8,edgecolors='white')
    ax.axhline(0,color='#555555',linewidth=.8)
    for row in ['205','168','207','234','230','199']:
        i=next(i for i,r in enumerate(rows) if r['source_row']==row)
        ax.annotate('row '+row,(gates[i],delta[i]),xytext=(6,6 if row!='168' else 17),textcoords='offset points',fontsize=9)
    ax.set_xlabel('Recipe balance gate h = 27*c1*c2*c3');ax.set_ylabel('Empirical RMSE minus K-M RMSE')
    ax.set_title('Similar recipe balance can help or harm, depending on the paint combination\nDescriptive analysis after scoring; below zero favors empirical',fontsize=12)
    fig.savefig(HERE/'recipe-balance.png',dpi=160);plt.close(fig)

    report=f'''# Broader ternary test: modest empirical gains and substantial tail risk

**The original empirical correction improves mean spectral RMSE by 3.83% and
mean windowed color error by 17.40% over K-M on the 35 additional ternaries.**
It improves spectral RMSE on 23 of 35 samples and color error on 29 of 35.
This broader evidence changes the interpretation of the earlier three Grillini
failures: three-chromatic-pigment mixtures do not generally require suppressing
the empirical correction.

The improvement is uneven. Empirical p95 spectral RMSE is 35.5% worse than K-M,
and the largest spectral regression more than doubles one sample's error.
Fixed attenuation reduces the high-error tail but gives up gains elsewhere:
its mean RMSE is 0.47% worse and mean DE00 10.66% worse than the original correction.
Retain the original correction as a research candidate and investigate specific
failures; this does not justify a universal attenuation default or product release.

![Mean, tail and color comparisons](comparison.png)

## Frozen cohort and fair comparison

The [plan](PLAN.md) executes the [previously prepared cohort](../oil_ternary_sources/next-cohort.json)
from commit `5f86146`. All 35 no-white target rows and 25 palettes were selected
before fitting, by recipe coverage. The known Old Holland targets 172,174,176
are excluded from this score. No rows or difficult palettes were dropped.

For each triple, calibration uses only the prescribed pure and binary samples
from those three paints plus Mixed White, between 25 and 39 rows. Each palette
has four pure endpoints and all six pair types; some binary pairs have only one
recipe. These are tube-paint fractions, not chemically pure pigment or volume
fractions. The first three coordinates are generic paint slots and are not always
yellow/red/blue. Mixed White remains fourth and sets the scattering gauge.

The K-M and bounded empirical fitters, objective, priors, bounds, starts and
stopping settings are unchanged. Each palette gets new coefficients from its own
calibration samples. K-M is the exact base belonging to its empirical model.
All 25 model fits converged and were frozen and verified before assessment.

The secondary comparator imports the exact archived attenuation decoder with
lambda fixed at 1. Its chromatic logit correction is multiplied by
`1 - 27*c1*c2*c3`; white-pair terms are unchanged. No strength or new gate was
learned from these 35 targets. All three methods therefore have the same
calibration-data budget in this comparison.

The data use native 31-band spectra at 400-700 nm. No spectral interpolation,
extrapolation, relabeling or cross-source coefficient transfer was used. DE00
uses the existing D65/2-degree integration over that window and its matching white;
it is not full-visible colorimetry and must not be pooled numerically with the
Grillini 440-740 nm scores.

## Primary 35-sample results

{headline}

{comparisons}

Positive reductions mean improvement; negative reductions mean regression.
The primary average is a mean of per-sample RMSE values, not the square root of
one pooled MSE. The worst absolute spectral error remains about 0.1047 RMSE under
both corrected methods, so a modest average improvement is not evidence of
uniform physical accuracy.

## Equal weighting across paint triples

Palettes have one to three target recipes. Averaging their mean errors equally
checks whether the conclusion depends on the few palettes with more samples.

{macro}

With equal palette weights, the original correction reduces mean spectral RMSE
by 6.21% and mean color error by 19.79% relative to K-M. Sixteen palettes improve
and nine worsen spectrally; 23 improve and two worsen in mean color error. The
fixed attenuation is 1.35% worse in mean spectral RMSE and 13.26% worse in mean
color error than the original correction under this weighting too.

This companion analysis supports the same average ranking. It is not a significance
test: calibration swatches and paint identities are shared among palettes.

## Failures and attenuation tradeoff

The five largest empirical spectral regressions are:

{worse_table}

Row 205, Cadmium Yellow / Scarlet Lake / Alizarine Lake at 1:2:1, is the largest
correction-induced regression: RMSE rises from 0.03690 to 0.08306. Attenuation
reduces it to 0.04287, but does not beat K-M. This palette has at least two samples
for every binary pair, so the failure cannot simply be assigned to the presence
of a one-sample pair without further evidence.

Conversely, row 234 (Scarlet Lake / Alizarine Lake / Viridian Green at 2:2:1)
improves from 0.03426 to 0.01194 with the empirical correction. Attenuation loses
much of that benefit, returning RMSE to 0.03055. The gates are almost the same
for these opposite cases: 0.84375 and 0.864. A rule based only on recipe balance
cannot distinguish their pigment-dependent outcomes.

![Error change versus recipe balance](recipe-balance.png)

This scatter plot and the selected examples are descriptive after scoring;
they were not used to choose a threshold, omit samples or tune the method.

There is also a separate base-model failure. Row {worst['source_row']}, Lemon Yellow /
Scarlet Lake / Viridian Green at 95:3.75:1.25, has RMSE
{float(worst['km_spectral_rmse']):.6f} for K-M,
{float(worst['empirical_spectral_rmse']):.6f} for empirical and
{float(worst['attenuated_spectral_rmse']):.6f} for attenuation. Its small gate means
attenuation barely changes the prediction. A second recipe from that palette,
row 197, is also poor. Suppressing an empirical correction cannot resolve an
error already present in the K-M base. This observation alone does not identify
whether the remaining cause is optical-model inadequacy, calibration conditioning,
sample preparation or source metadata.

## All palette results

Column numbers follow the source archive: 1 Lemon Yellow, 2 Cadmium Yellow,
3 Scarlet Lake, 4 Alizarine Lake, 5 Cobalt Blue, 6 Ultramarine Blue, 7 Viridian
Green. Mixed White (8) is present in every calibration palette. Full names and
exact row partitions are preserved in [palette-results.csv](palette-results.csv)
and the frozen cohort. All values below are mean target spectral RMSE.

{table(['Paint columns','Target rows','Calibration rows','Minimum pair support','K-M','Empirical','Attenuated'],palette_rows)}

[errors.csv](errors.csv) retains every target's recipe, gate and metrics.
[calibration.csv](calibration.csv) contains explicitly separated training errors;
none is included in the 35-row assessment score.

## Verification

- All {len(base_runs)} K-M starts converged in {min(r['nfev'] for r in base_runs)}-{max(r['nfev'] for r in base_runs)} evaluations, with no bound hits.
- All {len(emp_runs)} empirical fits converged in {min(r['nfev'] for r in emp_runs)}-{max(r['nfev'] for r in emp_runs)} evaluations, with zero or one active bound control.
- Each palette was refitted after replacing every excluded target spectrum.
  All K-M and empirical coefficients remained exactly unchanged.
- Independent scalar comparisons agree within {c['scalar_km_max_abs']:.3g} for K-M,
  {c['scalar_empirical_max_abs']:.3g} for empirical, and {c['scalar_attenuated_max_abs']:.3g} for attenuation.
- Pure endpoints agree within {c['pure_max_abs']:.3g}. Attenuation preserves original
  predictions bit-for-bit where any chromatic pigment is absent, including all
  calibration rows; 300 additional face recipes per palette also pass.
- Lambda zero recovers original decoder bits. All methods remain finite and
  strictly within (0,1) on available palette recipes and 517 additional recipes
  per palette. This verifies numerical validity, not physical accuracy there.
- Exact cohort coverage, all calibration supports, train/test disjointness,
  original dependency hashes and frozen-bundle integrity passed.

The frozen model bundle is stored under ignored
`target/measured-oils/ternary-transfer/frozen-models.json`, SHA-256:

`{s['model_bundle_sha256']}`

Detailed provenance and optimizer records are in [summary.json](summary.json),
with checks in [verification.json](verification.json). Runtime, renderer, default
palette and the paper implementation are unchanged.

## What this changes

The earlier conclusion should be narrowed: the binary-to-ternary transfer failed
on the three tested Grillini mixtures, but that failure does not generalize to
all chromatic ternaries. The unchanged correction often helps on this broader
Old Holland selection, especially in the color metric. Universal suppression
throws away useful corrections as well as harmful ones.

The next useful diagnosis is specific: separate row 205's correction-induced
failure from the large K-M errors in rows 197/199. Inspect their calibration
support, spectra and source metadata with frozen predictions before proposing
another change. Do not pick a balance threshold or pigment-specific exception
from this plot and report its performance on these same rows as fresh validation.

This is a broader same-source challenge outside the prior four-paint selection,
not a wholly independent external dataset. The Old Holland source and earlier
targets already informed method selection. Most new paint triples have one
target, physical repeat/batch identity is unavailable here, and concentration
support varies. The average gains and tail regressions are both retained;
neither alone establishes a production-ready measured-paint model.

## Reproduction

Use the checksum-verified original archive and scientific Python environment
recorded in the manifest. Run each phase in order:

```powershell
.\\target\\measured-oils\\venv\\Scripts\\python.exe experiments/oil_ternary_transfer/run.py prepare
.\\target\\measured-oils\\venv\\Scripts\\python.exe experiments/oil_ternary_transfer/run.py fit
.\\target\\measured-oils\\venv\\Scripts\\python.exe experiments/oil_ternary_transfer/run.py verify
.\\target\\measured-oils\\venv\\Scripts\\python.exe experiments/oil_ternary_transfer/run.py evaluate
.\\target\\measured-oils\\venv\\Scripts\\python.exe experiments/oil_ternary_transfer/report.py
```

Prepare and fit refuse to overwrite frozen outputs. For a fresh run use the same
new `--out` path under target/ for every run phase. The report script reads saved
scores only. Fresh optimizer elapsed times may differ; stored coefficients and
scores remain fixed through verification and evaluation. No extra measurements
or coefficient artifacts were bundled into the product.
'''
    (HERE/'REPORT.md').write_bytes(report.encode('utf-8'))
    print('Saved report, per-palette table and two figures')


if __name__=='__main__':main()
