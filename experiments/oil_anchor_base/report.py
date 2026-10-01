"""Present the single calibration ablation and retain its cohort-wide regressions."""
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

HERE=Path(__file__).resolve().parent
METHODS=['original_km','original_empirical','anchor_km','anchor_empirical']
LABELS=['Current K-M','Current K-M + correction','Pure/white K-M','Pure/white K-M + correction']


def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+
                     ['| '+' | '.join(map(str,r))+' |' for r in rows])


def main():
    s=json.loads((HERE/'summary.json').read_text(encoding='utf-8'))
    v=json.loads((HERE/'verification.json').read_text(encoding='utf-8'))
    assert s['complete_primary'] and s['scored_rows']==35 and not s['failed_palettes']
    rows=list(csv.DictReader((HERE/'errors.csv').open(newline='')))
    primary=s['comparisons']['anchor_empirical_vs_original_empirical']
    macro=s['macro_comparisons']['anchor_empirical_vs_original_empirical']
    headline=table(['Method','Mean RMSE','Median RMSE','p95 RMSE','Max RMSE','Mean windowed DE00'],
        [[label]+[f"{s['primary35'][m]['spectral_rmse'][k]:.6f}" for k in ['mean','median','p95','max']]+
         [f"{s['primary35'][m]['delta_e_2000']['mean']:.4f}"] for m,label in zip(METHODS,LABELS)])
    comparisons=table(['Comparison','Mean RMSE change','Spectral better / worse','Mean DE00 change','Color better / worse'],
        [[label,f"{-s['comparisons'][key]['spectral_rmse']['improvement_percent']:+.2f}%",
          f"{s['comparisons'][key]['spectral_rmse']['improved']} / {s['comparisons'][key]['spectral_rmse']['worsened']}",
          f"{-s['comparisons'][key]['delta_e_2000']['improvement_percent']:+.2f}%",
          f"{s['comparisons'][key]['delta_e_2000']['improved']} / {s['comparisons'][key]['delta_e_2000']['worsened']}"]
         for key,label in [('anchor_empirical_vs_original_empirical','New corrected vs current corrected'),
                           ('anchor_km_vs_original_km','New base vs current base'),
                           ('anchor_empirical_vs_anchor_km','New corrected vs its own base'),
                           ('anchor_empirical_vs_original_km','New corrected vs current plain K-M')]])
    macro_table=table(['Method','Equal-palette mean RMSE','Equal-palette mean DE00'],
        [[label,f"{s['macro_palette_means'][m]['spectral_rmse']:.6f}",f"{s['macro_palette_means'][m]['delta_e_2000']:.4f}"] for m,label in zip(METHODS,LABELS)])
    case_rows=[next(r for r in rows if int(r['source_row'])==i) for i in [197,199,205]]
    cases=table(['Row','Current base RMSE','New base RMSE','Current corrected RMSE','New corrected RMSE','Current / new corrected DE00'],
        [[r['source_row']]+[f"{float(r[m+'_spectral_rmse']):.6f}" for m in METHODS[::2]+METHODS[1::2]]+
         [f"{float(r['original_empirical_delta_e_2000']):.3f} / {float(r['anchor_empirical_delta_e_2000']):.3f}"] for r in case_rows])
    worse=sorted(rows,key=lambda r:float(r['anchor_empirical_spectral_rmse'])-float(r['original_empirical_spectral_rmse']),reverse=True)[:5]
    worse_table=table(['Row','Paints','Current corrected RMSE','New corrected RMSE','Current / new DE00'],
        [[r['source_row'],r['paints'],f"{float(r['original_empirical_spectral_rmse']):.6f}",f"{float(r['anchor_empirical_spectral_rmse']):.6f}",
          f"{float(r['original_empirical_delta_e_2000']):.3f} / {float(r['anchor_empirical_delta_e_2000']):.3f}"] for r in worse])
    palettes=[]
    for key,p in s['palettes'].items():
        record={'palette':key,'paints':'; '.join(p['palette']['paint_names'][:3]),
            'assessment_rows':','.join(map(str,p['palette']['assessment_rows_one_based'])),'new_base_rows':len(p['base_rows']),
            'full_pair_stage_rows':len(p['palette']['calibration_rows_one_based'])}
        record.update({m+'_'+metric:p['metrics'][m][metric]['mean'] for m in METHODS for metric in ['spectral_rmse','delta_e_2000']});palettes.append(record)
    with (HERE/'palette-results.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(palettes[0]),lineterminator='\n');writer.writeheader();writer.writerows(palettes)
    palette_table=table(['Paint columns','Targets','Base / pair fit rows','Current corrected RMSE','New corrected RMSE'],
        [[r['palette'].removeprefix('old-holland-'),r['assessment_rows'],f"{r['new_base_rows']} / {r['full_pair_stage_rows']}",
          f"{r['original_empirical_spectral_rmse']:.6f}",f"{r['anchor_empirical_spectral_rmse']:.6f}"] for r in palettes])
    base_runs=[r for p in s['palettes'].values() for r in p['optimizer']['base']]
    correction_runs=[p['optimizer']['empirical'] for p in s['palettes'].values()]
    assert all(r['success'] for r in base_runs+correction_runs)
    checks=v['checks']
    p95_gain=100*(1-s['primary35']['anchor_empirical']['spectral_rmse']['p95']/s['primary35']['original_empirical']['spectral_rmse']['p95'])

    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    colors=['#55718c','#218878','#9290b8','#c37b4e']
    fig,axes=plt.subplots(1,2,figsize=(13,4.9),layout='constrained')
    for i,(method,label,color) in enumerate(zip(METHODS,LABELS,colors)):
        offset=(i-1.5)*.2
        for ax,metric in zip(axes,['spectral_rmse','delta_e_2000']):
            ax.bar(np.arange(2)+offset,[s['primary35'][method][metric][stat] for stat in ['mean','p95']],.19,color=color,label=label)
    axes[0].set_ylabel('Spectral reflectance error');axes[1].set_ylabel('Windowed DE00')
    axes[0].set_title('Lower spectral tail, worse mean error',fontweight='bold',fontsize=11)
    axes[1].set_title('Color error worsens in both mean and tail',fontweight='bold',fontsize=11)
    for ax in axes:ax.set_xticks([0,1],['Mean','95th percentile'])
    axes[0].legend(frameon=False,fontsize=8);axes[0].set_ylim(0,.105);axes[1].set_ylim(0,10.5)
    fig.suptitle('Pure/white-only K-M calibration: a single ablation on all 35 exposed targets\nPair-correction objective and calibration pool unchanged; 25 palettes',fontsize=13)
    fig.savefig(HERE/'comparison.png',dpi=160);plt.close(fig)
    fig,ax=plt.subplots(figsize=(7.4,5.5),layout='constrained')
    x=np.array([float(r['original_empirical_spectral_rmse']) for r in rows]);y=np.array([float(r['anchor_empirical_spectral_rmse']) for r in rows])
    ax.scatter(x,y,c=np.where(y<x,'#218878','#c37b4e'),s=45,edgecolors='white')
    limit=.115;ax.plot([0,limit],[0,limit],color='#666666',linestyle='--',linewidth=1)
    for row in [197,199,205,226,209,224]:
        i=next(i for i,r in enumerate(rows) if int(r['source_row'])==row)
        ax.annotate('row '+str(row),(x[i],y[i]),xytext=(5,5),textcoords='offset points',fontsize=9)
    ax.set_xlim(0,limit);ax.set_ylim(0,limit);ax.set_aspect('equal')
    ax.set_xlabel('Current corrected spectral RMSE');ax.set_ylabel('New corrected spectral RMSE')
    ax.set_title('Selected failures improve spectrally; other recipes regress\nBelow the diagonal favors the ablation',fontsize=12)
    fig.savefig(HERE/'per-row.png',dpi=160);plt.close(fig)

    report=f'''# Pure/white base calibration fails the overall comparison

**Reject this ablation as a replacement for the current method.** Across the
same 35 targets, the new corrected model has **9.17% higher mean spectral RMSE**
and **29.31% higher mean windowed DE00** than the current corrected model.
Spectral error improves on 13 rows but worsens on 22; color improves on 10 and
worsens on 25. Equal weighting across palettes gives the same conclusion.

The three selected failures do improve spectrally, and p95/max spectral errors
fall. However, all three selected cases worsen in color error, and useful
predictions elsewhere are lost. This experiment does not support removing all
chromatic binaries from K-M calibration as a general fix.

![Primary mean and tail comparison](comparison.png)

## The single change

The [plan](PLAN.md) was saved before fitting/scoring. This follows the user's
approved calibration ablation from the [failure diagnosis](../oil_failure_cases/REPORT.md).
The original 25-palette / 35-target cohort, source rows, white gauge, native
400-700 nm spectra, objectives, priors, parameter bounds, initializations and
stopping rules are unchanged.

K-M now sees only pure paints and white tints: 20-27 samples per palette.
After its coefficients are frozen, the empirical controls still see the same
full 25-39-row pure/binary calibration pool as before. All pair controls, including
white pairs, are refitted on that pool. No new basis, attenuation, extra parameter,
recipe exception or target-informed sample deletion is introduced. Neither stage
sees any ternary target.

The second stage reuses the original features, residual and Jacobian with the
exact original optimizer settings. Given each of the 25 archived K-M bases, the
extracted stage reproduces its original pair coefficients **exactly**. Thus the
comparison does not confound the new calibration split with a changed correction
optimizer. Stage two leaves its new base coefficients byte-identical.

The mean-error normalization also remains unchanged. Reducing the first-stage
sample count changes its weighting relative to the fixed priors; this is part of
the declared intervention. The experiment is not an isolation of individual bad
binary observations while holding every statistical weight constant.

## Full-cohort results

{headline}

{comparisons}

Positive percentage change means higher error. The original all-binary-base
empirical model remains best in mean spectral and color error among these four
models. The new base alone is 29.88% worse spectrally than the original K-M base.
The existing pair correction repairs part of that loss (19.17% improvement over
its new base), but does not recover the original performance.

For the new corrected model, spectral p95 improves by {p95_gain:.2f}% relative to
the original correction, and maximum RMSE falls from 0.104666 to 0.076848. Those
tail improvements are retained as a tradeoff, not used to override the prespecified
mean-error result. Mean and p95 color errors both worsen.

DE00 uses the established D65/2-degree 400-700 nm window and matching white.
It is not full-visible colorimetry and is not numerically pooled with Grillini's
different spectral window. These are descriptive scores on exposed observations,
not an independent quality certification.

## Equal weighting across 25 palettes

{macro_table}

With equal palette weights, the corrected ablation is **13.87% worse in spectral
RMSE** and **33.63% worse in DE00** than the current correction. Ten palettes improve
and fifteen worsen spectrally; seven improve and eighteen worsen in color.
The failure therefore does not depend on giving extra weight to palettes with
more target recipes. Shared calibration swatches still prevent interpreting
these palettes as independent statistical replicates.

## The selected failures are not enough to choose the method

{cases}

For rows 197/199, removing chromatic binaries from base calibration substantially
reduces spectral error, consistent with the previous diagnosis that calibration
context affected the optical balance. But their color errors rise, and the
remaining spectral errors are still material. Row 205's new K-M base worsens;
its refitted correction makes the final spectral error somewhat less bad than
before, while color also worsens.

This supports a limited conclusion: the calibration split affects these cases.
It does not establish that pure/white calibration produces more faithful optical
parameters, fixes the incompatible binary observations, or improves paint mixtures
generally.

![Every target before and after the ablation](per-row.png)

The five largest new spectral regressions are:

{worse_table}

Rows 226 and 209 were reasonably predicted by the current correction and become
much worse. Their loss outweighs benefits elsewhere in the prespecified mean.
No failing row or palette was dropped, and no settings were revised after seeing
these outcomes. Detailed per-row values remain in [errors.csv](errors.csv).

## All palette results

Columns refer to the original paints: 1 Lemon Yellow, 2 Cadmium Yellow,
3 Scarlet Lake, 4 Alizarine Lake, 5 Cobalt Blue, 6 Ultramarine Blue, 7 Viridian
Green; Mixed White is always coordinate four. Every target row remains outside
both calibration stages.

{palette_table}

[palette-results.csv](palette-results.csv) includes both base models, corrected
models, native-window color errors and full paint names. [calibration.csv](calibration.csv)
separates pure, white-tint and chromatic-binary training records and marks which
rows enter the new base fit; none is counted as an assessment observation.

## Verification

- All 25 new fits succeeded. All {len(base_runs)} K-M starts converged in
  {min(r['nfev'] for r in base_runs)}-{max(r['nfev'] for r in base_runs)} evaluations with no active bounds.
- All {len(correction_runs)} correction fits converged in
  {min(r['nfev'] for r in correction_runs)}-{max(r['nfev'] for r in correction_runs)} evaluations, with 0-4 active bound controls.
- Repeating all 25 complete fits after perturbing excluded targets changed no
  base or pair coefficient.
- Perturbing chromatic binary calibration targets and repeating only stage one
  also changed no base coefficient. The new base genuinely uses the anchors only.
- Reusing each archived base reproduces its original pair controls with maximum
  difference {checks['original_pair_stage_theta_max_abs']:.3g}; original target scores replay within
  {s['original_score_replay_max_abs']:.3g}.
- Independent scalar decoding agrees within {checks['scalar_km_max_abs']:.3g} for K-M
  and {checks['scalar_empirical_max_abs']:.3g} for the correction. Pure endpoints agree
  within {checks['pure_max_abs']:.3g}. Available and 517 additional recipes per palette
  have finite predictions strictly within (0,1).
- Exact partitions, complete target coverage, unchanged upstream hashes and both
  frozen-bundle identities passed. These checks establish execution correctness,
  not physical accuracy.

New frozen bundle SHA-256:

`{s['new_bundle_sha256']}`

It is retained under ignored `target/measured-oils/anchor-base/frozen-models.json`.
The original bundle remains unchanged at
`{s['old_bundle_sha256']}`.
Provenance, coefficients' optimizer records and all comparisons are recorded in
[summary.json](summary.json), with verification evidence in
[verification.json](verification.json).

## Decision

Keep the original all-binary-base calibration as the research baseline. The data
do not support the broad claim that chromatic binaries should be withheld from
the optical fit: even where some observations violate the ideal opaque model,
they also provide information that pure/white tints alone do not replace.
The empirical stage helps the weaker new base, but its fixed capacity does not
fully compensate for the lost calibration information.

The original model's tail failures and physical-model contradictions remain.
This negative result does not validate the old model as physically correct; it
rejects this one proposed global remedy. Any future change should retain useful
chromatic evidence and explicitly account for uncertain model compatibility,
rather than selecting exceptions or another global split from these same errors.
No further revision is selected or fitted in this experiment.

The study is exploratory because all 35 targets were previously scored and three
failures motivated the hypothesis. No new physical measurements or independent
dataset were added. Production code, renderer, paper implementation and defaults
are unchanged.

## Reproduction

Use the existing checksum-verified Old Holland source and scientific Python
environment. Run phases in order:

```powershell
.\\target\\measured-oils\\venv\\Scripts\\python.exe experiments/oil_anchor_base/run.py prepare
.\\target\\measured-oils\\venv\\Scripts\\python.exe experiments/oil_anchor_base/run.py fit
.\\target\\measured-oils\\venv\\Scripts\\python.exe experiments/oil_anchor_base/run.py verify
.\\target\\measured-oils\\venv\\Scripts\\python.exe experiments/oil_anchor_base/run.py evaluate
.\\target\\measured-oils\\venv\\Scripts\\python.exe experiments/oil_anchor_base/report.py
```

Preparation and fitting refuse frozen-output overwrite. For a fresh run, supply
one new `--out` directory under target/ consistently to every run phase. The
report script reads saved results only. Original experiment files and coefficients
are never overwritten.
'''
    (HERE/'REPORT.md').write_bytes(report.encode('utf-8'))
    print('Saved report, per-palette table and two figures')


if __name__=='__main__':main()
