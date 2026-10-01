"""Read the frozen paired comparison and produce tables and figures."""
import csv
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import run as study

HERE=study.HERE
LABELS={'binary_km':'Binary K-M','binary_empirical':'Binary + correction',
        'expanded_km':'Expanded K-M','expanded_empirical':'Expanded + correction'}


def change(new,old):return 100*(new/old-1)


def table_stats(stats):
    return '\n'.join(f"| {LABELS[name]} | {m['spectral_rmse']['mean']:.6f} | {m['spectral_rmse']['median']:.6f} | {m['spectral_rmse']['p95']:.6f} | {m['spectral_rmse']['max']:.6f} | {m['delta_e_2000']['mean']:.4f} | {m['delta_e_2000']['p95']:.4f} | {m['delta_e_2000']['max']:.4f} |" for name,m in stats.items())


def main():
    s=json.loads((HERE/'summary.json').read_text(encoding='utf-8'))
    v=json.loads((HERE/'verification.json').read_text(encoding='utf-8'))
    manifest=json.loads((HERE/'partition.json').read_text(encoding='utf-8'))
    assert s['manifest_sha256']==v['manifest_sha256']==study.method.old.sha((HERE/'partition.json').read_bytes())
    assert s['bundle_sha256']==v['bundle_sha256']==study.method.old.sha((study.DEFAULT/'frozen-models.json').read_bytes())
    with (HERE/'errors.csv').open(encoding='utf-8',newline='') as f: rows=list(csv.DictReader(f))
    primary=[r for r in rows if int(r['paint_count'])>=3]
    assert len(primary)==183 and len(rows)==233
    a=s['subsets']['multicolor183'];binary=a['binary_empirical'];expanded=a['expanded_empirical']
    comp=s['comparisons']['multicolor183']['expanded_vs_binary']
    color=comp['delta_e_2000']['mean_error_change_percent'];spectral=comp['spectral_rmse']['mean_error_change_percent']
    heading='Multicolor calibration improves the primary result but hurts excluded binaries' if color<0 else 'Adding multicolor calibration does not improve the primary color mean'
    direction=lambda value: 'lower' if value<0 else 'higher'
    comparisons=[]
    for role in s['subsets']:
        m=s['subsets'][role];c=s['comparisons'][role]['expanded_vs_binary']
        comparisons.append(f"| {role.replace('_',' ')} | {m['binary_empirical']['count']} | {m['binary_empirical']['spectral_rmse']['mean']:.6f} | {m['expanded_empirical']['spectral_rmse']['mean']:.6f} | {m['binary_empirical']['delta_e_2000']['mean']:.4f} | {m['expanded_empirical']['delta_e_2000']['mean']:.4f} | {c['delta_e_2000']['mean_error_change_percent']:+.2f}% |")
    group_rows=[]
    for key,g in s['groups'].items():
        group_rows.append({'family':key,'test_rows':','.join(map(str,g['test_rows'])),
            'chromatic_ratio':':'.join(f'{x:.12g}' for x in g['ratio']),
            'primary_count':g['multicolor']['binary_empirical']['count'] if g['multicolor'] else 0,
            **{f'{name}_{metric}':values[metric]['mean'] for name,values in g['all'].items() for metric in ('spectral_rmse','delta_e_2000')}})
    study.method.old_chromatic.write_csv(HERE/'families.csv',group_rows)
    macro=s['equal_family_means']['multicolor']['scores']
    macro_color=change(macro['expanded_empirical']['delta_e_2000'],macro['binary_empirical']['delta_e_2000'])
    macro_spectral=change(macro['expanded_empirical']['spectral_rmse'],macro['binary_empirical']['spectral_rmse'])
    p95_color=change(expanded['delta_e_2000']['p95'],binary['delta_e_2000']['p95'])
    p95_spectral=change(expanded['spectral_rmse']['p95'],binary['spectral_rmse']['p95'])
    binary_changes=s['comparisons']['binary50']['expanded_vs_binary']
    no_white_changes=s['comparisons']['multicolor_no_white']['expanded_vs_binary']
    white_changes=s['comparisons']['multicolor_with_white']['expanded_vs_binary']
    secondary=s['subsets']['binary50']
    worst=sorted(primary,key=lambda r:float(r['expanded_empirical_delta_e_2000'])-float(r['binary_empirical_delta_e_2000']),reverse=True)[:6]
    worst_table='\n'.join(f"| {r['source_row']} | {r['family']} | {r['paint_count']} | {float(r['binary_empirical_delta_e_2000']):.4f} | {float(r['expanded_empirical_delta_e_2000']):.4f} | {float(r['binary_empirical_spectral_rmse']):.6f} | {float(r['expanded_empirical_spectral_rmse']):.6f} |" for r in worst)
    base_runs=[r for m in v['models'].values() for r in m['base_runs']]
    correction=[m['correction'] for m in v['models'].values()]
    all_base_success=sum(r['success'] for r in base_runs)
    base_bounds=[r['bound_variables'] for r in base_runs];pair_bounds=[r['bound_variables'] for r in correction]
    nfev=[r['nfev'] for r in base_runs];pair_nfev=[r['nfev'] for r in correction]
    means=s['subsets']['multicolor183']
    fig,axes=plt.subplots(1,2,figsize=(12,4.5),layout='constrained')
    colors=['#8aa4bd','#365978','#8ccbc0','#177f70']
    for ax,metric,title in zip(axes,['spectral_rmse','delta_e_2000'],['Spectral RMSE','Windowed DE00']):
        x=np.arange(2)
        for i,(name,m) in enumerate(means.items()):
            ax.bar(x+(i-1.5)*.19,[m[metric]['mean'],m[metric]['p95']],.18,color=colors[i],label=LABELS[name])
        ax.set_xticks(x,['Mean','95th percentile']);ax.set_title(title);ax.set_ylim(bottom=0)
    axes[0].legend(fontsize=8)
    fig.suptitle('183 multicolor mixtures; complete chromatic-ratio families excluded\nSame model and settings, different calibration pools')
    fig.savefig(HERE/'comparison.png',dpi=160);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(10.5,5),layout='constrained')
    for ax,metric,title in zip(axes,['spectral_rmse','delta_e_2000'],['Spectral RMSE','Windowed DE00']):
        x=np.array([float(r[f'binary_empirical_{metric}']) for r in primary]);y=np.array([float(r[f'expanded_empirical_{metric}']) for r in primary])
        ax.scatter(x,y,c=np.where(y<x,'#177f70','#c57747'),s=22,alpha=.8)
        end=max(x.max(),y.max())*1.05;ax.plot([0,end],[0,end],'--',color='#777777',linewidth=1)
        ax.set(xlim=(0,end),ylim=(0,end),xlabel='Binary calibration + correction',ylabel='Expanded calibration + correction',title=title)
    fig.suptitle('Every excluded multicolor recipe; below the diagonal favors expanded calibration')
    fig.savefig(HERE/'per-row.png',dpi=160);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(10.5,4.5),layout='constrained')
    for ax,metric,title in zip(axes,['spectral_rmse','delta_e_2000'],['Mean spectral error change (%)','Mean color error change (%)']):
        values=[d[metric]['mean_error_change_percent'] for d in [white_changes,no_white_changes,binary_changes]]
        ax.bar(np.arange(3),values,color=['#177f70' if x<0 else '#c57747' for x in values])
        ax.axhline(0,color='#777777',linewidth=1)
        ax.set_xticks(np.arange(3),['Multicolor + white\n127 samples','Multicolor, no white\n56 samples','Excluded binaries\n50 samples'])
        ax.set_title(title)
        for i,value in enumerate(values):ax.text(i,value+(1 if value>=0 else -1),f'{value:+.2f}%',ha='center',va='bottom' if value>=0 else 'top')
        ax.margins(y=.18)
    fig.suptitle('The calibration tradeoff: negative values mean lower error')
    fig.savefig(HERE/'subgroups.png',dpi=160);plt.close(fig)
    conclusion=("The paired comparison establishes useful headroom from multicolor calibration "
        "within these recipe exclusions. The gains are predictive, rather than scores on the "
        "newly fitted rows. However, the fixed fitting procedure trades away binary accuracy, "
        "and its mean color benefit is concentrated in white-containing mixtures. This supports "
        "further work on the calibration compromise, not automatic replacement of the current package."
        if color<0 and spectral<0 else
        "The paired results show a tradeoff or failure of this calibration change. The full "
        "cohort and tail outcomes should determine its usefulness, rather than training error.")
    text=f'''# {heading}

The same eight-paint model, fitted with additional multicolor measurements,
has **{abs(color):.2f}% {direction(color)} mean windowed color error** and
**{abs(spectral):.2f}% {direction(spectral)} mean spectral RMSE** on the same
**183 multicolor samples**, each predicted with its complete recipe family excluded.
Color improves on {comp['delta_e_2000']['improved']}, worsens on {comp['delta_e_2000']['worsened']}
and ties on {comp['delta_e_2000']['tied']}; spectra improve on {comp['spectral_rmse']['improved']}
and worsen on {comp['spectral_rmse']['worsened']}.

The gains concentrate in white-containing mixtures. On the 50 excluded binary
samples, mean spectral error rises **{binary_changes['spectral_rmse']['mean_error_change_percent']:.2f}%**
and mean color error rises **{binary_changes['delta_e_2000']['mean_error_change_percent']:.2f}%**.
On the 56 multicolor samples without white, mean color error rises
**{no_white_changes['delta_e_2000']['mean_error_change_percent']:.2f}%**. This is a useful
improvement with a material calibration tradeoff, not a universal upgrade.

![Mean and tail comparison](comparison.png)

## What was compared

The [plan](PLAN.md) and [complete partitions](partition.json) were frozen before
fitting. A family has one normalized seven-paint chromatic ratio, regardless of
total amount or white addition. All its recorded members are excluded together,
including its binary parent where present. Other ratios using those pigments
remain available. This is recipe-family exclusion, not unseen-pigment or batch
validation.

The 53 pure/white-tint anchors remain available throughout. The 233 remaining
rows form 107 families; 99 families contain the 183 primary multicolor targets,
and 50 binary parent rows provide a secondary assessment.

- Binary-only fits use 102-103 pure/binary observations after excluding the family.
- Expanded fits use 282-285 observations after excluding the same family, adding
  multicolor measurements to both optical-base and pair-control fitting.

Both reuse the exact unified-eight fitter: 217 log-scattering parameters, measured
pure K/S, white S=1, three starts and the original priors/bounds/stopping rules;
then 112 possible bounded pair controls, with unsupported controls inactive.
No new term, weighting rule, attenuation or tuned setting was introduced.
The mean-error normalization remains fixed, so the expanded data distribution
can change the compromise among recipe types. No sample was excluded based on
its error. All 158 distinct fits (51 binary and 107 expanded) were frozen before
scoring; identical binary training pools are reused without making duplicate fits.

## Primary assessment: the same 183 multicolor samples

| Method | Mean RMSE | Median RMSE | p95 RMSE | Maximum RMSE | Mean DE00 | p95 DE00 | Maximum DE00 |
| --- | --- | --- | --- | --- | --- | --- | --- |
{table_stats(a)}

Lower is better. Spectral RMSE is the mean per-recipe reflectance RMSE over the
31 measured bands. Color error uses the unchanged 400-700 nm D65/2-degree
XYZ/Lab calculation and matching truncated white, without display gamut mapping.

For the corrected model, p95 spectral error changes **{p95_spectral:+.2f}%** and
p95 color error **{p95_color:+.2f}%**. Maximum color error changes from
{binary['delta_e_2000']['max']:.4f} to {expanded['delta_e_2000']['max']:.4f}; maximum
spectral RMSE changes from {binary['spectral_rmse']['max']:.6f} to
{expanded['spectral_rmse']['max']:.6f}. These tails and individual regressions
remain part of the result even when means improve.

Equal weighting over the 99 multicolor families gives binary/expanded mean DE00
{macro['binary_empirical']['delta_e_2000']:.4f}/{macro['expanded_empirical']['delta_e_2000']:.4f}
({macro_color:+.2f}%), and RMSE
{macro['binary_empirical']['spectral_rmse']:.6f}/{macro['expanded_empirical']['spectral_rmse']:.6f}
({macro_spectral:+.2f}%). Fold training sets overlap heavily; these are descriptive
comparisons, not independent replicates or a significance test.

The packaged unified model's earlier mean DE00 of 3.461 came from a less strict
split where relevant binary parents could remain in training. The fair comparator
here is the newly refitted binary-only column above, not that historical number.

## Recipe groups and secondary binary assessment

| Assessment | Rows | Binary corrected RMSE | Expanded corrected RMSE | Binary corrected DE00 | Expanded corrected DE00 | Color error change |
| --- | --- | --- | --- | --- | --- | --- |
{chr(10).join(comparisons)}

The ingredient-count groups refer to total ingredients including white; white
subgroups contain only the primary multicolor rows. [families.csv](families.csv)
lists every ratio family and [errors.csv](errors.csv) retains every assessed row.
Anchor rows are not scored as predictive validation.

![White-mixture gains and binary regressions](subgroups.png)

White-containing multicolor recipes account for 127 of the 183 primary rows:
their mean color error falls {abs(white_changes['delta_e_2000']['mean_error_change_percent']):.2f}%.
The 50 binary parents are a secondary assessment, but their regression matters
for ordinary two-paint mixing: {binary_changes['delta_e_2000']['worsened']} of 50 worsen
in color and {binary_changes['spectral_rmse']['worsened']} worsen spectrally. More
calibration coverage has not removed the model's compromise across recipe types.

The binary tail results are mixed as well: spectral p95 rises from
{secondary['binary_empirical']['spectral_rmse']['p95']:.6f} to
{secondary['expanded_empirical']['spectral_rmse']['p95']:.6f}, while color p95 falls
from {secondary['binary_empirical']['delta_e_2000']['p95']:.4f} to
{secondary['expanded_empirical']['delta_e_2000']['p95']:.4f} and worst color error
falls from {secondary['binary_empirical']['delta_e_2000']['max']:.4f} to
{secondary['expanded_empirical']['delta_e_2000']['max']:.4f}. Thus the binary mean
regression does not imply every binary tail measure worsens.

![Every assessed multicolor recipe](per-row.png)

The six largest increases in multicolor color error are:

| Row | Excluded family | Ingredients | Binary DE00 | Expanded DE00 | Binary RMSE | Expanded RMSE |
| --- | --- | --- | --- | --- | --- | --- |
{worst_table}

## Verification

- Before these fits, the archived unified model's K/S, q, log-scattering and pair
  coefficients were reproduced exactly, along with all 32 archived assessment
  statistics. See [baseline-check.json](baseline-check.json).
- Three protocol tests pass for family invariance, complete coverage/anchor
  retention and ensuring only selected rows reach the fitter.
- All {len(v['models'])} fits succeeded. {all_base_success}/{len(base_runs)} K-M
  starts converged; base evaluations ranged {min(nfev)}-{max(nfev)}, with
  {min(base_bounds)}-{max(base_bounds)} active bounds. Correction fits used
  {min(pair_nfev)}-{max(pair_nfev)} evaluations, with {min(pair_bounds)}-{max(pair_bounds)} active bounds.
- All {v['refitted_models']} distinct pools were refitted after changing excluded
  spectra. Every optical and pair coefficient remained exactly unchanged.
- Independent scalar decoding agrees within {v['checks']['scalar_max_abs']:.3g};
  pure endpoints agree within {v['checks']['pure_max_abs']:.3g}. All recorded and
  257 additional dense recipes per model stay finite and strictly bounded.
- Source, method, protocol, partition and original package hashes remain intact.
  Complete-cohort coverage passed; no failed fit or difficult row was dropped.

See [verification.json](verification.json) for optimizer and numerical records.
The frozen local coefficient bundle is under
`target/measured-oils/multicolor-calibration/frozen-models.json`, SHA-256:

`{s['bundle_sha256']}`

## Interpretation and product boundary

{conclusion}

The source dataset is appropriate evidence for this question. Earlier scores and
method choices make it development evidence rather than a pristine final test;
using one source dataset alone does not invalidate the exclusion experiment.
There are no new physical measurements, independent batches or eight-ingredient
measurements in this study.

These scores pool models fitted with different families excluded. They are not
the scores of a single deployable palette. The existing runtime packages and
defaults are preserved. A final fit using an adopted calibration procedure would
be a separate artifact, and its training error must not be substituted for these
excluded-family results. This turn makes no change to renderer or library code.

## Reproduction

Use a fresh ignored `--out` directory for a repeat. Fit checkpoints allow an
interrupted run to resume; they are tied to the complete partition hash.

```powershell
.\\target\\measured-oils\\venv\\Scripts\\python.exe -m unittest discover -s experiments/oil_multicolor_calibration -p test_protocol.py -v
.\\target\\measured-oils\\venv\\Scripts\\python.exe experiments/oil_multicolor_calibration/run.py prepare
.\\target\\measured-oils\\venv\\Scripts\\python.exe experiments/oil_multicolor_calibration/run.py fit --workers 4
.\\target\\measured-oils\\venv\\Scripts\\python.exe experiments/oil_multicolor_calibration/run.py verify --workers 4
.\\target\\measured-oils\\venv\\Scripts\\python.exe experiments/oil_multicolor_calibration/run.py evaluate
.\\target\\measured-oils\\venv\\Scripts\\python.exe experiments/oil_multicolor_calibration/report.py
```

No settings were changed after assessment. Original measurements and fitted
coefficients remain local under ignored target/; original scripts, hashes and
numerical reports are retained in the repository.
'''
    (HERE/'REPORT.md').write_bytes(text.encode())
    print(json.dumps({'color_change_percent':color,'spectral_change_percent':spectral,
        'p95_color_change_percent':p95_color,'p95_spectral_change_percent':p95_spectral,
        'macro_color_change_percent':macro_color,'macro_spectral_change_percent':macro_spectral},indent=2))


if __name__=='__main__':main()
