"""Render the two distinct frozen failure mechanisms with their limits."""
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+
                     ['| '+' | '.join(map(str,r))+' |' for r in rows])


def main():
    summary=json.loads((HERE/'summary.json').read_text(encoding='utf-8'))
    read=lambda f:list(csv.DictReader((HERE/f).open(newline='')))
    observations=read('observations.csv');parts=read('pair-contributions.csv');coverage=read('coverage.csv')
    envelopes=read('opaque-envelope.csv');regions=read('spectral-regions.csv');shared=read('shared-binary.csv')
    curves=np.load(ROOT/'target/measured-oils/failure-cases/spectra.npz');nm=np.arange(400,701,10)
    obs={int(r['source_row']):r for r in observations}
    headline=table(['Source row','Role','K-M RMSE','Empirical RMSE','Correction RMS'],
        [[row,'Previously scored target' if row in [197,199,205] else '50% white addition; diagnostic']+
         [f"{float(obs[row][key]):.6f}" for key in ['km_spectral_rmse','empirical_spectral_rmse','correction_rms']]
         for row in [205,206,197,198,199,200]])
    part205=[r for r in parts if r['source_row']=='205']
    part_table=table(['Pair','Weight','MSE reduction attributed to pair','RMSE with only this pair','RMSE with this pair removed'],
        [[r['pair'],f"{float(r['weight']):.2f}",f"{float(r['MSE_reduction_shapley']):+.6f}",
          f"{float(r['only_pair_RMSE']):.6f}",f"{float(r['without_pair_RMSE']):.6f}"] for r in part205])
    coverage_table=table(['Target','Pair','Target ratio','Calibration ratios','Inside measured range?'],
        [[r['source_row'],r['pair'],f"{float(r['target_first_over_second']):.4g}:1",r['calibration_ratios'],
          'Yes' if r['inside_calibration_ratio_range']=='True' else 'No']
         for r in coverage if r['source_row'] in ['197','199','205']])
    blend=read('blend-ratios.csv')
    blend_table=table(['Wavelength','Frozen blend/yellow S','Implied by row 197','Implied by row 199'],
        [[n,f"{curves['frozen_blend_over_yellow_S'][(n-400)//10]:.3f}",
          f"{curves['row197_ratio_frozen_row138'][(n-400)//10]:.3f}",
          f"{curves['row199_ratio_frozen_row138'][(n-400)//10]:.3f}"] for n in [600,650,700]])
    a=curves['row197_ratio_frozen_row138'][20:];b=curves['row199_ratio_frozen_row138'][20:]
    agreement=float((abs(a-b)/((a+b)/2)).max())
    shared_table=table(['Frozen palette columns (+ white)','Fitted Viridian/Yellow S at 700 nm','Predicted R: Y/G=1:1','Predicted R: Y/G=16:1','Predicted R: Y/G=76:1'],
        [[key.removeprefix('old-holland-'),f"{float(next(r for r in shared if r['palette']==key)['S_viridian_over_yellow_700']):.3f}"]+
         [f"{float(r['R_700']):.4f}" for r in shared if r['palette']==key] for key in dict.fromkeys(r['palette'] for r in shared)])
    env108=next(r for r in envelopes if r['source_row']=='108')
    floors=table(['Row','Opaque-model RMSE lower bound','Actual frozen K-M RMSE'],
        [[row,f"{float(next(r for r in envelopes if r['source_row']==str(row))['opaque_RMSE_floor']):.6f}",
          f"{float(obs[row]['km_spectral_rmse']):.6f}"] for row in [205,197,199]])
    red205=next(r for r in regions if r['source_row']=='205' and r['lo_nm']=='600')
    redshares={row:float(next(r for r in regions if r['source_row']==str(row) and r['lo_nm']=='600')['km_MSE_contribution'])/float(obs[row]['km_spectral_rmse'])**2 for row in [197,199]}

    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(1,2,figsize=(12.6,4.9),layout='constrained')
    pure1,pure2=curves['row13_measured'],curves['row20_measured']
    axes[0].fill_between(nm,np.minimum(pure1,pure2),np.maximum(pure1,pure2),color='#cbd6e3',alpha=.7,label='Allowed opaque K-M envelope')
    for row,label,color in [(13,'Pure Scarlet','#ad605c'),(20,'Pure Alizarin','#806c9c'),(108,'Measured 1:1 mixture','#222222')]:
        axes[0].plot(nm,curves[f'row{row}_measured'],color=color,label=label,linewidth=2)
    axes[0].set_title('Calibration row 108 falls below both pure paints',fontsize=11,fontweight='bold')
    axes[0].legend(fontsize=8,frameon=False);axes[0].set_xlabel('Wavelength (nm)');axes[0].set_ylabel('Reflectance')
    for key,label,color,style in [('measured','Measured row 205','#222222','-'),('km','K-M','#55718c','--'),
        ('empirical','All pair corrections','#c37b4e','-'),('without_3','Remove Scarlet/Alizarin term','#218878',':')]:
        axes[1].plot(nm,curves['row205_'+key],label=label,color=color,linestyle=style,linewidth=2)
    axes[1].set_title('The learned darkening transfers in the wrong direction',fontsize=11,fontweight='bold')
    axes[1].legend(fontsize=8,frameon=False);axes[1].set_xlabel('Wavelength (nm)');axes[1].set_ylabel('Reflectance')
    fig.suptitle('Row 205: a correction learned from an incompatible opaque-model calibration case\nFrozen coefficients; removal is a diagnostic counterfactual, not a revised model',fontsize=13)
    fig.savefig(HERE/'row205.png',dpi=160);plt.close(fig)

    fig,axes=plt.subplots(2,2,figsize=(12,8),layout='constrained')
    for ax,row in zip(axes[0],[197,199]):
        for key,label,color,style in [('measured','Measured','#222222','-'),('km','K-M','#55718c','--'),('empirical','Empirical','#c37b4e','-')]:
            ax.plot(nm,curves[f'row{row}_'+key],label=label,color=color,linestyle=style,linewidth=2)
        ax.set_title(f'Row {row}: large existing K-M error',fontweight='bold',fontsize=11)
        ax.set_xlabel('Wavelength (nm)');ax.set_ylabel('Reflectance');ax.legend(frameon=False,fontsize=9)
    ax=axes[1,0]
    ax.plot(nm[20:],curves['frozen_blend_over_yellow_S'][20:],color='#55718c',label='Frozen model')
    ax.plot(nm[20:],a,color='#218878',label='Implied by row 197')
    ax.plot(nm[20:],b,color='#c37b4e',linestyle='--',label='Implied by row 199')
    ax.set_title('Effective blend weight is too high for both targets',fontweight='bold',fontsize=11)
    ax.set_xlabel('Wavelength (nm)');ax.set_ylabel('S(blend) / S(yellow)');ax.legend(frameon=False,fontsize=8)
    ax=axes[1,1]
    for key in dict.fromkeys(r['palette'] for r in shared):
        ax.plot(nm,curves[key+'_viridian_over_yellow_S'],label=key.removeprefix('old-holland-')+' + white')
    ax.set_title('Shared paint ratio varies across frozen calibrations',fontweight='bold',fontsize=11)
    ax.set_xlabel('Wavelength (nm)');ax.set_ylabel('Fitted S(viridian) / S(yellow)');ax.legend(frameon=False,fontsize=8)
    fig.suptitle('Rows 197/199: calibration context and unsupported yellow-rich ratios\nBottom-left inversions use the same frozen red/green blend endpoint; no refitting',fontsize=13)
    fig.savefig(HERE/'rows197-199.png',dpi=160);plt.close(fig)

    checks=summary['checks']
    report=f'''# Two different failure mechanisms in the frozen oil models

**Row 205 carries a binary darkening correction into a ternary that needs
brightening. Rows 197/199 already have an overly dark K-M prediction caused by
the fitted optical balance of a red/green blend against yellow.** The evidence
points to calibration/model compatibility and missing ratio coverage, rather
than a common attenuation problem or an optimizer that failed to converge.

These are selected, previously exposed failures. No model was fitted, coefficient
changed, source row relabeled or implementation promoted. The diagnosis uses the
exact frozen bundle from the [35-row study](../oil_ternary_transfer/REPORT.md).
Physical causes such as film thickness or sample preparation remain unresolved.

## The three targets and their white additions

{headline}

Rows 206,198,200 preserve the respective chromatic ratios and add 50% Mixed White.
They were never fitted in these palette models and are shown here only as
neighboring diagnostic observations, not a newly selected validation benchmark.
Whitening reduces the large K-M residuals of 197/199 but does not eliminate them.
It does not prove why their unwhitened counterparts fail.

## Row 205: the strongest pair correction compensates for a model impossibility

Row 205 contains Cadmium Yellow / Scarlet Lake / Alizarine Lake in a 1:2:1 mass
ratio. K-M mean RMSE is 0.036898; the full empirical correction raises it to
0.083059. In 600-700 nm, the target needs a mean reflectance increase of
{float(red205['mean_needed_reflectance_change']):.4f}, but the correction produces
{float(red205['mean_actual_reflectance_change']):.4f}. Its overall reflectance
displacement is misaligned with the residual (projection alpha -0.451).

The dominant harmful term belongs to Scarlet/Alizarin. Its 1:1 calibration sample,
row 108, is **darker than either measured pure paint** at 630-700 nm. At 700 nm:

| Observation | Reflectance |
|---|---:|
| Pure Scarlet Lake | 0.7324 |
| Pure Alizarine Lake | 0.5853 |
| Measured 1:1 mixture, row 108 | **0.4201** |

For the assumed opaque K-M model, `q=(1-R)^2/(2R)` and
`q_mix=sum(c_i*S_i*q_i)/sum(c_i*S_i)`. Positive scattering makes q_mix a weighted
average of constituent q values. Because the reflectance conversion is monotone,
R_mix must lie between the minimum and maximum constituent pure reflectances.
No choice of positive scattering with these fixed pure endpoints can reach 0.4201
when both endpoints are at least 0.5853.

Across the 31 bands, this constraint alone puts a **{float(env108['opaque_RMSE_floor']):.6f} RMSE
lower bound** on fitting row 108 with fixed-pure opaque K-M. Its actual K-M error
is 0.073553. The empirical correction reduces that calibration error to 0.008388
by learning strong darkening. That is useful for this observed binary sample,
but its residual correction is not a physical pair property guaranteed to transfer
when Cadmium Yellow is added.

![Calibration envelope violation and its effect on row 205](row205.png)

Exact Shapley allocations over all active-term subsets account for the nonlinear
reflectance decoder. Negative MSE reduction means harm. These are numerical
attributions inside the frozen model, not percentages of a physical cause.

{part_table}

Removing the Scarlet/Alizarin term reduces row 205's error to 0.046586 but still
does not beat K-M. Cadmium/Scarlet also harms the target; its required 1:2 internal
ratio is outside that pair's calibrated 1:1 and 9:1 ratios. The correction's
spectral curve has no ratio-dependent shape beyond the symmetric `4*c_i*c_j`
amplitude. Thus there is both an opaque-model compatibility problem in calibration
and an uncovered directional ratio. There is no evidence that simply deleting
one pair globally would preserve the improvements elsewhere.

The envelope contradiction does **not** prove incorrect measurement or paint
chemistry. Pure paintouts that are not optically opaque, different film conditions,
measurement effects or an inadequate homogeneous model could break the assumptions.
It establishes that this fixed-pure opaque model cannot exactly fit that calibration
observation. No source correction is inferred from this alone.

## Rows 197/199: the K-M base assigns excessive influence to a dark blend

Both recipes contain Lemon Yellow, Scarlet Lake and Viridian Green. Their raw
recorded proportions are 16:3:1 and 76:3:1. The Scarlet:Viridian ratio is therefore
the same 3:1, while yellow changes from 80% to 95%. The frozen K-M errors are
0.069509 and 0.104356; their corrections have RMS only 0.005637 and 0.002272.
Suppressing those corrections cannot repair the much larger baseline residuals.

The red region (600-700 nm) accounts for {100*redshares[197]:.1f}% and {100*redshares[199]:.1f}%
of the respective K-M squared errors. The measured spectra are substantially
brighter than K-M there. At 700 nm row 199 measures 0.5612, while K-M predicts
0.3188 and the empirical correction changes it only slightly.

### A useful consistency check using the shared 3:1 blend

Calibration row 138 measures the same 3:1 Scarlet/Viridian blend without yellow.
Treating that blend as an effective ingredient gives
`S_D=.75*S_Scarlet+.25*S_Viridian`. For a known yellow fraction y and endpoint
ratios q_Y and q_D, each measured ternary algebraically implies

`S_D/S_Y = y*(q_Y-q_target) / ((1-y)*(q_target-q_D))`.

This is an inversion of an observation, not a refit or replacement coefficient.
Using the **frozen model's** row-138 endpoint keeps its existing q values fixed:

{blend_table}

Across 600-700 nm, the ratios computed separately from the two targets agree within
{100*agreement:.2f}% relative to their mean. The existing model uses approximately
1.5-5.2 times that optical ratio, weighting the dark blend too strongly to reproduce
either target with its frozen endpoints. Using the **measured** row-138 spectrum
instead also produces closely agreeing target-inferred ratios (maximum difference
7.12% over this interval). Both endpoint choices show the same qualitative
discrepancy; it is not confined to using the predicted blend spectrum.

This makes the two target residuals a coherent pattern worth investigating. It
does not prove the inferred ratio is the true material scattering ratio, and no
inferred ratio is inserted into a prediction model in this diagnosis.

![Frozen target predictions, effective blend inversion and shared-pair sensitivity](rows197-199.png)

### Calibration coverage and dependence on other paints

The pair-ratio coverage is:

{coverage_table}

Yellow/Viridian has only a 1:1 binary calibration sample, whereas the two targets
require internal ratios of 16:1 and 76:1. Row 199's Yellow/Scarlet ratio of
25.33:1 also extends beyond its maximum calibrated ratio of 9:1. The red/green
3:1 ratio itself is observed. White-tint data constrain each pigment too, but
they do not directly measure these yellow-rich chromatic interactions.

Four already-frozen palette fits contain Yellow and Viridian with the same pure
and white-tint data and the same Y/G=1:1 observation. Their fitted Y/G optical
ratios nevertheless depend strongly on the other chromatic paint and its binary
calibration data. At 700 nm:

{shared_table}

The last two columns are **unmeasured binary predictions**, not measurements of
rows 197/199 (which also contain Scarlet). The measured 1:1 reflectance is 0.0654,
and the Scarlet-containing fit predicts 0.0390. That moderate calibration residual
coincides with large disagreement in the yellow-rich extrapolation. This quantifies
dependence on calibration context; it is not an uncertainty interval and does
not authorize choosing another palette's coefficients to improve these targets.

The pure-envelope lower bounds for the three targets themselves are small:

{floors}

Their small blue-region envelope violations cannot explain the large red-region
errors in 197/199. The decisive issue there is the fitted relative optical balance
and how it transfers beyond observed chromatic ratios, not an unavoidable red-band
pure-endpoint bound.

## This is not explained by optimizer failure

Both selected palettes have converged three-start K-M runs with objective values
agreeing within 3.3e-15. Their calibration-data Jacobians have full rank
93 and condition numbers 6.71 and 8.73 in the fitted log-scattering coordinates.
Including the priors leaves them similar. There is no evidence here of a numerical
singularity or failed local convergence that a routine optimizer restart would fix.

These are local derivatives with fixed measured pure endpoints and this objective.
They do not quantify physical identifiability, measurement uncertainty, global
uniqueness or model misspecification. A numerically well-determined compromise can
still be wrong for a new composition, especially when observed binaries already
violate the assumed opaque model.

## Source checks and unresolved physical metadata

The original ZIP and member hashes match the earlier study. A second plain-text
reader reproduces the source values and recipe normalization exactly; the selected
row numbers and neighboring white additions are consistent. No parser shift or
local source mutation was found. The recorded integer portions are ratios; do not
assume they are actual grams or derive a weighing error from them.

The [source paper](https://pure.mpg.de/rest/items/item_3285223_1/component/file_3285224/content)
describes weighed tube paints mixed with a knife, applied to Arches oil paper,
dried for several weeks and measured with a specular-excluded X-Rite Color i7.
It does not provide per-swatch optical thickness, a black/white backing pair,
an oil-paper reflectance spectrum, replicate uncertainty or batch IDs sufficient
to resolve these cases. The supplied watercolor substrate spectrum is not an
oil-paper backing measurement and must not be substituted.

Consequently, finite-film effects, different preparation conditions or remaining
source metadata issues are hypotheses, not established explanations. These data
show a contradiction with one optical assumption and a repeatable extrapolation
failure; they do not select a unique replacement physical model.

## Recommended next controlled test

Before adding another correction term, test one calibration ablation: fit the
K-M base from pure/white-tint anchors only, then freeze it and fit the existing
empirical pair controls using the same full binary calibration pool. Keep all
objectives, priors, bounds and assessment rows unchanged. Compare against the
current all-binary K-M calibration on the full 35-row cohort, not only these
three selected failures.

This would test whether forcing an opaque base to compromise across incompatible
chromatic binaries is a major driver of the errors. It is a diagnostic proposal,
not a fix already demonstrated: some white tints also violate the model, and
removing binary constraints may lose useful calibration. The 35 targets are now
exposed, so any resulting improvement must remain explicitly exploratory.
No ablation or model revision was run during this diagnosis.

## Files and reproduction

[observations.csv](observations.csv) distinguishes the three selected targets from
their white-addition diagnostics. [pair-contributions.csv](pair-contributions.csv)
records exact allocations and component removals. Other evidence includes
[coverage.csv](coverage.csv), [binary-consistency.csv](binary-consistency.csv),
[opaque-envelope.csv](opaque-envelope.csv), [blend-ratios.csv](blend-ratios.csv),
[shared-binary.csv](shared-binary.csv), [effective-weights.csv](effective-weights.csv)
and [spectral-regions.csv](spectral-regions.csv).

The [summary](summary.json) retains provenance, raw recipe records and local
Jacobian diagnostics. Source-derived spectral curves remain under ignored
`target/measured-oils/failure-cases/spectra.npz`. Saved target metrics reproduce
within {checks['saved_error_max_abs']:.3g}; independent scalar decoding agrees within
{checks['scalar_max_abs']:.3g}, component recombination within {checks['recombination_max_abs']:.3g},
and MSE allocations within {checks['shapley_sum_max_abs']:.3g}. The positive-scattering
envelope is verified on every available recipe in the two palettes. All source,
method and frozen-model hashes remain unchanged; fitting entry points are disabled.

```powershell
.\\target\\measured-oils\\venv\\Scripts\\python.exe experiments/oil_failure_cases/diagnose.py
.\\target\\measured-oils\\venv\\Scripts\\python.exe experiments/oil_failure_cases/report.py
```

This post-selection diagnosis does not change the broader study's scores or
establish independent accuracy. Runtime, renderer, paper implementation and
defaults are untouched.
'''
    (HERE/'REPORT.md').write_bytes(report.encode('utf-8'))
    print('Saved report and two diagnostic figures')


if __name__=='__main__':main()
