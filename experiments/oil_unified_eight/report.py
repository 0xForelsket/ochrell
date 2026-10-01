"""Report frozen scores and local package previews; never fit or tune."""
import csv
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import run as study
from generate_window_projection import projection

HERE=study.HERE; OUT=study.DEFAULT


def display(linear):
    rgb=np.asarray(linear,dtype=float).copy()
    for i,row in enumerate(rgb):
        if not ((row>=0)&(row<=1)).all():
            y=float(np.clip(row@np.array([.2126,.7152,.0722]),0,1)); a=1.
            for v in row:
                d=v-y
                if d>0:a=min(a,(1-y)/d)
                elif d<0:a=min(a,-y/d)
            rgb[i]=np.clip(y+a*(row-y),0,1)
    return np.where(rgb<=.0031308,12.92*rgb,1.055*rgb**(1/2.4)-.055)


def main():
    s=json.loads((HERE/'summary.json').read_text(encoding='utf-8'))
    v=json.loads((HERE/'verification.json').read_text(encoding='utf-8'))
    p=json.loads((HERE/'package-verification.json').read_text(encoding='utf-8'))
    c,r,train,manifest=study.inputs()
    frozen=(OUT/'frozen-model.json').read_bytes(); artifact=json.loads(frozen)
    assert artifact['manifest']==manifest==s['manifest']==v['manifest']
    assert study.old.sha(frozen)==s['bundle_sha256']==v['bundle_sha256']==p['packages']['frozen_fit_sha256']
    model=artifact['model']; a=s['scores']['assessment183']; shared=s['shared35']; original=s['original35']
    gain={key:100*(1-a['empirical'][key]['mean']/a['km'][key]['mean']) for key in ['spectral_rmse','delta_e_2000']}
    shared_gain={key:100*(1-shared['empirical'][key]['mean']/original['empirical'][key]) for key in gain}
    with (HERE/'errors.csv').open(encoding='utf-8',newline='') as f: rows=list(csv.DictReader(f))
    worst=sorted([x for x in rows if x['role']=='assessment'],key=lambda x:float(x['empirical_delta_e_2000']),reverse=True)[:5]
    group_table='\n'.join(f"| {role.replace('_',' ')} | {m['km']['count']} | {m['km']['spectral_rmse']['mean']:.6f} | {m['empirical']['spectral_rmse']['mean']:.6f} | {m['km']['delta_e_2000']['mean']:.3f} | {m['empirical']['delta_e_2000']['mean']:.3f} |" for role,m in s['scores'].items() if role not in ['assessment183','calibration103'])
    worst_table='\n'.join(f"| {x['source_row']} | {x['paint_count']} | {float(x['empirical_spectral_rmse']):.6f} | {float(x['empirical_delta_e_2000']):.3f} |" for x in worst)
    packages=p['packages']['packages']
    package_table='\n'.join(f"| {name} | `{x['file']}` | {x['bytes']:,} | `{x['sha256']}` |" for name,x in packages.items())
    renderer=OUT/'renderer'; evidence=renderer/'verification.txt'
    renderer_text=evidence.read_text(encoding='utf-8') if evidence.exists() else 'Renderer final evidence is pending.'
    renderer_hashes={f.name:study.old.sha(f.read_bytes()) for f in renderer.iterdir() if f.is_file()} if renderer.exists() else {}
    study.old.write_json(OUT/'renderer-files.json',renderer_hashes)
    assert renderer_text.count('all canvas planes replay bit-identical')==2
    renderer_sources=[study.ROOT.parent/'oilpaint-renderer'/name for name in [
        'crates/oil-mix/src/palette.rs','crates/oil-palette/src/lib.rs',
        'crates/oil-palette/src/codec.rs','crates/oil-palette/examples/old_holland_eight.rs']]
    study.old.write_json(HERE/'renderer-verification.json',{'fit_sha256':study.old.sha(frozen),
        'empirical_package_sha256':p['packages']['packages']['empirical']['sha256'],
        'evidence':renderer_text,'files':renderer_hashes,
        'renderer_source_hashes':{str(x.relative_to(study.ROOT.parent)):study.old.sha(x.read_bytes()) for x in renderer_sources}})
    (HERE/'preflight.json').write_bytes((OUT/'preflight.json').read_bytes())
    fig,axes=plt.subplots(1,2,figsize=(10.5,4),layout='constrained')
    for ax,key,title in zip(axes,['spectral_rmse','delta_e_2000'],['Spectral RMSE','Windowed DE00']):
        x=np.arange(2)
        for offset,name,color in [(-.18,'km','#536f89'),(.18,'empirical','#16877c')]:
            ax.bar(x+offset,[a[name][key]['mean'],a[name][key]['p95']],.36,label=name,color=color)
        ax.set_xticks(x,['Mean','95th percentile']);ax.set_title(title);ax.legend();ax.set_ylim(bottom=0)
    fig.suptitle('Unified Old Holland Eight: 183 mixtures excluded from fitting')
    fig.savefig(HERE/'comparison.png',dpi=160);plt.close(fig)

    # Source-derived swatches stay local under ignored target/.
    weights=np.array(projection())
    fig,axes=plt.subplots(2,8,figsize=(15,4.2),layout='constrained')
    for i in range(8):
        for row in range(2):
            recipe=np.eye(8)[i].copy()
            if row:recipe[7]+=1.;recipe/=recipe.sum()
            rgb=display(study.predict(recipe[None,:],model)@weights)[0]
            axes[row,i].add_patch(Rectangle((0,0),1,1,color=rgb));axes[row,i].set_axis_off()
            axes[row,i].set_title(study.NAMES[i].replace(' ','\n') if row==0 else '1:1 with white',fontsize=9)
    fig.suptitle('Old Holland Eight — fitted empirical palette\n400–700 nm preview; lower row shows equal-mass white tints')
    fig.savefig(OUT/'palette-swatches.png',dpi=150);plt.close(fig)
    order=sorted(np.flatnonzero(~train),key=lambda i:float(rows[i]['empirical_delta_e_2000']))
    selected=order[:5]+order[-5:]
    pred={name:display(study.predict(c,model,corrected)@weights) for name,corrected in [('K-M',False),('Empirical',True)]}
    measured=display(r@weights)
    fig,axes=plt.subplots(10,3,figsize=(8,9),layout='constrained')
    for row,i in enumerate(selected):
        for col,(name,rgb) in enumerate([('Measured',measured[i]),('K-M',pred['K-M'][i]),('Empirical',pred['Empirical'][i])]):
            axes[row,col].add_patch(Rectangle((0,0),1,1,color=rgb));axes[row,col].set_axis_off()
            if row==0:axes[row,col].set_title(name)
        axes[row,0].text(-.03,.5,f"Row {i+1}\nDE00 {float(rows[i]['empirical_delta_e_2000']):.2f}",transform=axes[row,0].transAxes,ha='right',va='center',fontsize=8)
    fig.suptitle('Five smallest and five largest empirical color errors\nWindowed screen previews; numeric DE00 uses unclipped XYZ/Lab')
    fig.savefig(OUT/'measured-comparison.png',dpi=140);plt.close(fig)

    text=f'''# Unified Old Holland Eight: fitted and packaged

One consistent eight-paint model is now fitted, assessed and available as local
runtime packages. The empirical candidate reduces mean spectral RMSE by
**{gain['spectral_rmse']:.2f}%** and mean windowed color error by **{gain['delta_e_2000']:.2f}%**
against its own shared K-M base on all **183 mixtures excluded from fitting**.
It improves color on {s['improved_counts183']['delta_e_2000']} of 183 rows and spectra
on {s['improved_counts183']['spectral_rmse']} of 183. Spectral p95 and maximum still worsen.
This is a usable experimental painting model, not a physically certified preset.

![Assessment means and tails](comparison.png)

## Fit and assessment

The [plan](PLAN.md) was saved before fitting. The unchanged source supplies
eight pures, 95 binaries and 183 mixtures of three to seven paints. All 28 pair
types are present in calibration, with 1-9 observations per pair. Only the 103
pure/binary rows calibrate either stage. There are no measured eight-ingredient
recipes; their runtime evaluation remains an unvalidated extension of the model.

The base fits 217 log-relative scattering parameters (7 paints x 31 bands),
with measured pure K/S and Mixed White S=1. All three starts converge, with no
active bounds. The frozen base then supports 112 bounded empirical controls
(28 pairs x 4 wavelength controls); that stage converges in ten evaluations,
with one bound control. Optimizer records are retained in [summary.json](summary.json).

No four-paint optical fits were combined. Every paint now has one set of K/S
coefficients used for every recipe. The old objectives, starting points, bounds
and stopping criteria were generalized by dimension only; regularizers retain
their mean-square normalization at the new parameter counts. No attenuation,
target tuning or failed-row exclusion was introduced.

| Model | Mean RMSE | Median RMSE | p95 RMSE | Maximum RMSE | Mean windowed DE00 | p95 DE00 | Max DE00 |
| --- | --- | --- | --- | --- | --- | --- | --- |
'''
    for name,m in a.items():
        text+=f"| {name} | {m['spectral_rmse']['mean']:.6f} | {m['spectral_rmse']['median']:.6f} | {m['spectral_rmse']['p95']:.6f} | {m['spectral_rmse']['max']:.6f} | {m['delta_e_2000']['mean']:.3f} | {m['delta_e_2000']['p95']:.3f} | {m['delta_e_2000']['max']:.3f} |\n"
    text+=f'''
Native spectra cover 400-700 nm at 10 nm. DE00 uses the same truncated D65/2-degree
XYZ/Lab calculation and matching white as previous Old Holland studies, without
RGB clipping. Source conditions and earlier assessments informed method selection,
so these scores are exploratory same-source evidence, not independent validation.

| Assessment group | Count | K-M RMSE | Empirical RMSE | K-M DE00 | Empirical DE00 |
| --- | --- | --- | --- | --- | --- |
{group_table}

All row-level metrics, including calibration rows clearly labeled separately,
are in [errors.csv](errors.csv). The five largest remaining color errors are:

| Source row | Paint count | Empirical RMSE | Empirical DE00 |
| --- | --- | --- | --- |
{worst_table}

## Comparison on the established 35-target cohort

| Method | Mean spectral RMSE | Mean windowed DE00 |
| --- | --- | --- |
| Previous palette-specific K-M | {original['km']['spectral_rmse']:.6f} | {original['km']['delta_e_2000']:.4f} |
| Previous palette-specific correction | {original['empirical']['spectral_rmse']:.6f} | {original['empirical']['delta_e_2000']:.4f} |
| Unified eight-paint K-M | {shared['km']['spectral_rmse']['mean']:.6f} | {shared['km']['delta_e_2000']['mean']:.4f} |
| Unified eight-paint correction | {shared['empirical']['spectral_rmse']['mean']:.6f} | {shared['empirical']['delta_e_2000']['mean']:.4f} |

The unified corrected model improves these two means by {shared_gain['spectral_rmse']:.2f}%
and {shared_gain['delta_e_2000']:.2f}% relative to the archived correction. However,
its base now sees the complete 103-row binary calibration graph rather than one
four-paint subset. This is not an equal-data-budget algorithm comparison. The
unified plain K-M base has lower mean spectral error than its correction on these
35 rows, while the correction has lower color error. Both packages are retained.

## Usable local packages

Files are under `target/measured-oils/unified-eight/`:

| Model | Filename | Bytes | File SHA-256 |
| --- | --- | --- | --- |
{package_table}

OPP3 preserves the native 31-band optical curves, eight paint identities, mass
convention, explicit model kind, pair controls and windowed display projection.
The display projection follows the existing neutral-normalized RGB convention
over the measured window, then the existing gamut map. It is a limited-window
preview, not a full-visible measurement. No missing spectral tails are invented.

Load either package with `PaletteN::<8,31>::from_bytes` in Ochrell or
`PaletteMixerN::<8,false,31>::from_palette_bytes` in the native renderer. Recipes
retain all eight components. The empirical model travels inside its package;
loading it does not silently fall back to plain K-M. Existing package identities
and four-paint acceleration remain compatible. No default is changed.

The source-derived packages and previews remain local ignored research artifacts.
The repository contains original implementation, provenance and error reports.
No author was contacted and no redistribution decision was changed.

## Verification and actual painting

Before fitting, the generalized code reproduced the old four-paint K/S and pair
coefficients exactly; its directional Jacobian check agreed within 1.1e-12.
Replacing all 183 excluded spectra and refitting changed no coefficient.
Independent scalar decoding agrees within 3.4e-16 reflectance; pure endpoints
remain exact to 1.2e-16. Dense all-eight recipes are finite and bounded.

Both exported packages were independently loaded and evaluated by Rust on 1,318
recorded/dense/pure recipes. Spectra agree with Python within 3.4e-16 and linear
RGB within 2.3e-16. Package and recipe serialization preserve exact bytes and
future mixtures. See [preflight.json](preflight.json), [verification.json](verification.json),
[package-verification.json](package-verification.json) and
[renderer-verification.json](renderer-verification.json).

The native `old_holland_eight` example loads the actual empirical OPP3, paints
94 strokes using matched targets and explicit recipes (including an all-eight
load), and checks all canvas planes after saving/reopening each job. Its final run records:

```text
{renderer_text.strip()}
```

Timings are local smoke observations, not comparative benchmarks. The black
match is only the best recipe found, not a certified gamut boundary. Native
paintings, replay bundles, plane hashes and swatch sheets are retained under
the local output directory. Screen appearance also depends on the display.

## Reproduction

Use the existing source archive and scientific environment. For a new fit,
choose a fresh `--out` for every phase; frozen files are never overwritten.

```powershell
.\\target\\measured-oils\\venv\\Scripts\\python.exe experiments/oil_unified_eight/run.py prepare
.\\target\\measured-oils\\venv\\Scripts\\python.exe experiments/oil_unified_eight/run.py fit
.\\target\\measured-oils\\venv\\Scripts\\python.exe experiments/oil_unified_eight/run.py verify
.\\target\\measured-oils\\venv\\Scripts\\python.exe experiments/oil_unified_eight/run.py evaluate
.\\target\\measured-oils\\venv\\Scripts\\python.exe experiments/oil_unified_eight/package.py export
```

Run `measured_palette_probe` for both packages using `recipes.f64` and write
`km-predictions.f64` / `empirical-predictions.f64`, then run `package.py verify`.
In the sibling renderer, run `cargo run --release --offline -p oil-palette
--example old_holland_eight -- <empirical.opp> <output-directory>`. The final
report script reads scores, checks and previews without fitting.

Frozen fit SHA-256: `{s['bundle_sha256']}`.
Source: Asadi Shahmirzadi, Babaei and Seidel, *A Multispectral Dataset of Oil and
Watercolor Paints* (2020); [dataset page](https://www.azadehasadi.net/paintdatasets.html).
This is a modern Old Holland selection, not a reconstruction of a specific
historical Monet painting or paint batch.
'''
    (HERE/'REPORT.md').write_bytes(text.encode())
    usage='''# Old Holland Eight experimental runtime packages

These packages contain one unified eight-paint fit from the Asadi Shahmirzadi,
Babaei and Seidel (2020) Old Holland dataset. They are local research artifacts.

- old-holland-eight-empirical.opp: K-M plus 28 bounded empirical pair corrections.
- old-holland-eight-km.opp: the identical frozen optical base without corrections.
- packages.json: source fit and package hashes.

All curves are native 31-band 400-700 nm measurements/fits. Display is a windowed
D65 preview, not a full-visible color measurement. Recipes use normalized tube-
paint mass portions. This is a modern selection, not Monet's historical tubes.

Load with Ochrell PaletteN::<8,31>::from_bytes. For native painting, use
oil_palette::PaletteMixerN::<8,false,31>::from_palette_bytes and
PaletteJobN<8,false,31>. The old_holland_eight example in the sibling renderer
accepts the package path and an output directory, producing PNGs and exact-replay
OPJ2 jobs. Both packages retain the same eight paint names/order, but have distinct
model identities; recipes cannot be silently moved between them.

Eight pures and 95 binaries fitted the model; 183 higher-order mixtures were
excluded from fitting. The empirical model's mean windowed DE00 is 3.461 and
mean spectral RMSE 0.029703. This is exploratory same-source assessment, not
independent validation. Some visible errors remain; no eight-ingredient mixture
was measured. The original source and fitted model hashes are embedded in each
package. Source: https://www.azadehasadi.net/paintdatasets.html

The CIE-derived projection data retain their CC BY-SA 4.0 attribution described
in the Ochrell repository's data/README.md. No broader distribution or default
promotion is implied by this local package. Full methods, results and limitations
are in experiments/oil_unified_eight/REPORT.md in the Ochrell repository.
'''
    (OUT/'README.md').write_bytes(usage.encode())
    print('Saved report, comparison chart and local swatch previews')


if __name__=='__main__':main()
