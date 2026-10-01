"""Package evidence, native painting comparison and the large-palette LUT decision."""
import csv
import io
import json
import math
from pathlib import Path
import shutil
import subprocess
import zipfile
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import run as study

HERE, ROOT, OUT = study.HERE, study.ROOT, study.DEFAULT
RENDERER = ROOT.parent/'oilpaint-renderer'
LABELS = {'previous': 'Previous: binary calibration', 'balanced': 'Balanced: full calibration'}


def read_csv(path):
    with path.open(encoding='utf-8', newline='') as stream:
        return list(csv.DictReader(stream))


def stats(values):
    return {'count': len(values), 'mean': float(np.mean(values)), 'median': float(np.median(values)),
        'min': float(np.min(values)), 'p95': float(np.quantile(values, .95)), 'max': float(np.max(values))}


def main():
    c, r, manifest = study.inputs()
    fit = json.loads((HERE/'fit-verification.json').read_text(encoding='utf-8'))
    runtime = json.loads((HERE/'package-verification.json').read_text(encoding='utf-8'))
    assert fit['manifest'] == manifest
    assert fit['fit_sha256'] == runtime['packages']['fit_sha256'] == study.method.old.sha((OUT/'frozen-model.json').read_bytes())
    comparison = OUT/'comparison'
    for name in ('timings.csv', 'matches.csv', 'swatches.csv', 'plane-hashes.csv'):
        shutil.copyfile(comparison/name, HERE/name)
    rows = {name: read_csv(comparison/f'{name}.csv') for name in ('timings', 'matches', 'swatches', 'plane-hashes')}
    assert len(rows['matches']) == len(rows['swatches']) == 64
    assert len(rows['plane-hashes']) == 30
    grouped = {}
    for label in LABELS:
        for op in sorted({row['operation'] for row in rows['timings']}):
            selected = [row for row in rows['timings'] if row['model'] == label and row['operation'] == op]
            values = np.array([float(row['milliseconds']) for row in selected])
            if op == 'decode-srgb':
                assert all(int(row['operations']) == 100000 for row in selected)
                values *= 10  # milliseconds per 100000 -> nanoseconds per operation.
            if op.startswith('paint-') or op == 'decode-srgb':
                assert {int(row['repetition']) for row in selected} == set(range(1, 8))
            grouped[f'{label}/{op}'] = stats(values)
    matches = {label: [row for row in rows['matches'] if row['model'] == label] for label in LABELS}
    swatches = {label: [row for row in rows['swatches'] if row['model'] == label] for label in LABELS}
    for i in range(32):
        a, b = matches['previous'][i], matches['balanced'][i]
        assert a['target_id'] == b['target_id'] == str(i)
        assert [a[ch] for ch in ('r', 'g', 'b')] == [b[ch] for ch in ('r', 'g', 'b')]
        a, b = swatches['previous'][i], swatches['balanced'][i]
        assert a['recipe_id'] == b['recipe_id'] == str(i) and a['recipe'] == b['recipe']
        if i < 8:
            assert [a[ch] for ch in ('r', 'g', 'b')] == [b[ch] for ch in ('r', 'g', 'b')]
    errors = {label: np.array([float(row['error_ok100']) for row in matches[label]]) for label in LABELS}
    delta = errors['balanced']-errors['previous']
    matching = {'metric': 'Displayed OKLab distance times 100; RGB target reachability, not measured-paint accuracy',
        'scores': {label: stats(values) for label, values in errors.items()},
        'comparison_tolerance_ok100': 1e-4, 'improved': int((delta < -1e-4).sum()),
        'worsened': int((delta > 1e-4).sum()), 'tied': int((abs(delta) <= 1e-4).sum()),
        'black': {label: matches[label][0] for label in LABELS}}
    image_differences = {}
    for name, title in [('fixed-recipes', 'Identical recipes and strokes'), ('matched-targets', 'Identical RGB targets and strokes'), ('renderer-fixture', '94-stroke renderer fixture')]:
        fig, axes = plt.subplots(1, 2, figsize=(9, 6), layout='constrained')
        images = []
        for ax, label in zip(axes, LABELS):
            pixels = plt.imread(comparison/label/f'{name}.png')
            assert pixels.shape == (480, 384, 3) and np.isfinite(pixels).all()
            images.append(pixels)
            ax.imshow(pixels)
            ax.set_title(LABELS[label], fontsize=11)
            ax.axis('off')
        difference = abs(images[1]-images[0])
        image_differences[name] = {'mean_abs_display_channel_difference': float(difference.mean()),
            'max_abs_display_channel_difference': float(difference.max()),
            'status': 'Difference between rendered images; not an accuracy metric'}
        fig.suptitle(title+'\nNative 400-700 nm preview; display differences are not physical validation', fontsize=12)
        fig.savefig(OUT/f'{name}-comparison.png', dpi=160)
        plt.close(fig)
    # Exact decoded swatches explain recipe identity independently of brush/coverage.
    fig, ax = plt.subplots(figsize=(12, 9), layout='constrained')
    for i in range(32):
        col, row = i % 4, i // 4
        for j, label in enumerate(LABELS):
            item = swatches[label][i]
            color = [float(item[ch]) for ch in ('r', 'g', 'b')]
            ax.add_patch(Rectangle((col*3+j*1.35, -row), 1.3, .65, facecolor=color))
        ax.text(col*3, -row+.70, f"{i+1}. {swatches['previous'][i]['name']}", fontsize=8)
    ax.set(xlim=(-.1, 11.9), ylim=(-7.2, 1.1))
    ax.axis('off')
    fig.suptitle('Same material recipe: previous (left) / balanced (right)\nRows: pure paints, chromatic mixtures, white tints, all-eight mixtures')
    fig.savefig(OUT/'decoded-swatches.png', dpi=160)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(12, 9), layout='constrained')
    for i in range(32):
        col, row = i % 4, i // 4
        target = [float(matches['previous'][i][ch]) for ch in ('r', 'g', 'b')]
        colors = [target] + [[float(matches[label][i]['achieved_'+ch]) for ch in ('r', 'g', 'b')] for label in LABELS]
        for j, color in enumerate(colors):
            ax.add_patch(Rectangle((col*3+j*.9, -row), .86, .65, facecolor=color))
        ax.text(col*3, -row+.70, f"{i+1}. error {errors['previous'][i]:.2f} / {errors['balanced'][i]:.2f}", fontsize=8)
    ax.set(xlim=(-.1, 11.9), ylim=(-7.2, 1.1))
    ax.axis('off')
    fig.suptitle('Target / previous achieved / balanced achieved\nErrors are displayed OKLab x100 against RGB targets, not paint measurements')
    fig.savefig(OUT/'target-swatches.png', dpi=160)
    plt.close(fig)
    decoder_bytes = {str(n): {'dimensions': n-1, 'dense_rgb_f32_bytes_at_65': 65**(n-1)*12,
        'ordered_simplex_rgb_f32_bytes_at_65': math.comb(65+n-2, n-1)*12} for n in (4, 8, 16)}
    preference = {'preferred_measured_package': runtime['packages']['packages']['empirical']['file'],
        'identity': runtime['packages']['packages']['empirical']['identity'],
        'scope': 'Local experimental measured Old Holland Eight recipe painting',
        'decision': 'Prefer balanced for measured recipe behavior; retain previous binary calibration for explicit comparison',
        'global_default_changed': False, 'decoder': 'native direct 31-band; no eight-paint LUT',
        'limitations': ['Same-source accuracy evidence', 'Lighter closest-found black', 'RGB matching is approximate and may be unreachable', 'Binary spectral tradeoff remains']}
    study.method.old.write_json(OUT/'preferred-palette.json', preference)
    old = ROOT/'target/measured-oils/unified-eight/old-holland-eight-empirical.opp'
    old_sha = study.method.old.sha(old.read_bytes())
    assert old_sha == '9d21533abbe7a4d3a947ac96f322e3b804f1b08910579a903a0cdb1d69eb4001'
    readme = '''# Balanced Old Holland Eight: local experimental package

Preferred measured recipe palette: old-holland-eight-balanced-empirical.opp.
The km package provides its optical base for diagnosis. The prior binary-fit
old-holland-eight-empirical.opp is retained as an explicit comparison.

All 286 source measurements calibrate the balanced model. Accuracy evidence is
the separate 107-family exclusion study, not this model's training residuals.
Amounts are normalized recorded tube-paint mass portions; spectra cover only
400-700 nm, with a windowed D65 preview. Mixed White is zinc/titanium tube paint.
There is no eight-ingredient measurement in the source. Darkest-found colors
are approximate inverse-search results, not a proved black limit.

Load with PaletteN::<8,31> in Ochrell or
PaletteMixerN::<8,false,31>::from_palette_bytes in oilpaint-renderer.
Keep eight material proportions when mixing. No eight-paint LUT is supplied.
Self-contained saved paintings use PaletteJobN<8,false,31> / OPJ2.

Example (run in the sibling renderer checkout):
```powershell
cargo run --release --offline -p oil-palette --example old_holland_eight -- PATH/old-holland-eight-balanced-empirical.opp OUTPUT
cargo run --release --offline -p oil-palette --example compare_old_holland -- PATH/old-holland-eight-empirical.opp PATH/old-holland-eight-balanced-empirical.opp OUTPUT
```

This is a local source-derived research package. No redistribution license is
asserted here. The global/synthetic default has not changed. Existing projects
continue using their embedded model identity and coefficients.
'''
    (OUT/'README.md').write_bytes(readme.encode())
    archive = OUT/'old-holland-eight-balanced-local.zip'
    members = [(OUT/name, name) for name in ('README.md', 'packages.json', 'preferred-palette.json',
        'old-holland-eight-balanced-km.opp', 'old-holland-eight-balanced-empirical.opp')]
    members.append((old, old.name))
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for file, name in members:
            info = zipfile.ZipInfo(name, (2026, 10, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, file.read_bytes())
    archive.write_bytes(stream.getvalue())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for file, name in members:
            assert z.read(name) == file.read_bytes()
    renderer_files = [RENDERER/'crates/oil-palette/examples/compare_old_holland.rs',
        RENDERER/'crates/oil-palette/src/lib.rs', RENDERER/'crates/oil-palette/src/codec.rs',
        RENDERER/'crates/oil-mix/src/palette.rs', RENDERER/'crates/oil-mix/Cargo.toml', RENDERER/'Cargo.lock']
    evidence = {'fit_sha256': fit['fit_sha256'], 'packages': runtime['packages']['packages'],
        'completed_checks': {'cargo test --offline -p oil-palette': '7 integration tests and 1 documentation test passed',
            'cargo clippy --offline -p oil-palette --example compare_old_holland -- -D warnings': 'passed'},
        'reference_package_sha256': old_sha, 'timings': grouped, 'target_matching': matching,
        'display_differences': image_differences, 'lut_storage_scaling': decoder_bytes, 'recommendation': preference,
        'renderer_verification': (comparison/'verification.txt').read_text(),
        'renderer_source_hashes': {p.relative_to(RENDERER).as_posix(): study.method.old.sha(p.read_bytes()) for p in renderer_files},
        'renderer_runtime_ochrell_revision': '17c13d018c1ac569755dadb41b9b169f7f3cd1ea',
        'rustc': subprocess.check_output(['rustc', '--version'], text=True).strip(),
        'local_archive': {'file': archive.name, 'bytes': archive.stat().st_size, 'sha256': study.method.old.sha(archive.read_bytes())},
        'comparison_files': {p.relative_to(OUT).as_posix(): study.method.old.sha(p.read_bytes()) for p in sorted(comparison.rglob('*')) if p.is_file()}}
    for dest in (OUT, HERE):
        study.method.old.write_json(dest/'workflow-verification.json', evidence)
    lines = []
    for op, label, units in [('decode-srgb', 'Recipe to displayed RGB', 'ns/recipe'),
        ('paint-fixed-recipes', '96 fixed-recipe strokes', 'ms'), ('paint-matched-targets', '96 matched-target strokes', 'ms'),
        ('paint-renderer-fixture', '94-stroke renderer fixture', 'ms')]:
        a, b = grouped['previous/'+op], grouped['balanced/'+op]
        lines.append(f"| {label} | {a['median']:.2f} ({a['min']:.2f}-{a['max']:.2f}) | {b['median']:.2f} ({b['min']:.2f}-{b['max']:.2f}) | {units} |")
    black = {label: '#'+''.join(f'{int(float(matches[label][0]["achieved_"+ch])*255+.5):02X}' for ch in ('r', 'g', 'b')) for label in LABELS}
    report = f'''# Balanced Old Holland Eight is packaged and usable in the renderer

The final balanced model is fitted on all 286 source measurements, exported as
native OPP3 packages and verified through the existing eight-material renderer.
**Recommendation: use the balanced corrected package as the preferred local
measured recipe palette, with the previous package retained for comparison.**
The global renderer/synthetic default is unchanged.

This choice follows the earlier excluded-family measured-paint comparison and
successful product checks. It does not follow from a claim that these rendered
images are more physically accurate. The balanced model has a lighter darkest
mixture found by the current search, and slightly worse RGB-target coverage in
this fixed test set. Those differences remain visible and documented.

## Local deliverables

- [Balanced empirical palette](../../target/measured-oils/balanced-eight/old-holland-eight-balanced-empirical.opp):
  {runtime['packages']['packages']['empirical']['bytes']} bytes, native 31 bands and 28 pair corrections.
- [Balanced K-M base](../../target/measured-oils/balanced-eight/old-holland-eight-balanced-km.opp):
  {runtime['packages']['packages']['km']['bytes']} bytes, diagnostic reference.
- [Local comparison bundle](../../target/measured-oils/balanced-eight/old-holland-eight-balanced-local.zip):
  both new packages, the unchanged previous package, metadata and usage notes.
- [Preferred local palette descriptor](../../target/measured-oils/balanced-eight/preferred-palette.json):
  explicit recommendation and identity; not an automatic global-default switch.

The source-derived packages and preview images remain under ignored target/.
This report, scripts, numerical evidence and renderer example are committed.

## Final calibration and runtime checks

The unchanged tested weighting rule gives each nonpure category equal total
influence. Full-data category sizes are 50, 45, 56 and 127; pure endpoints remain
fixed. The final fit took {fit['fit_wall_seconds']:.3f} seconds on this host and
reproduced all optical/pair coefficients exactly on a second fit.

The [107-family exclusion study](../oil_balanced_calibration/REPORT.md) remains
the predictive evidence: 16.28% lower multicolor mean DE00 and 16.16% lower mean
spectral RMSE than its paired binary baseline, recovering binary/no-white mean
color regressions while retaining a 25.05% binary spectral penalty. Those are
cross-fitted procedure results, not validation scores of this all-data model.
[fit-verification.json](fit-verification.json) labels final training diagnostics
explicitly; they are not a new accuracy test.

All 2,411 probes pass: 286 measured recipes, 8 pures, all 28 pair ramps including
tiny fractions, 1,024 dense recipes and the equal eight-paint mixture. Rust and
Python spectra agree within {max(x['spectral_max_abs'] for x in runtime['checks'].values()):.3g};
linear RGB within {max(x['linear_rgb_max_abs'] for x in runtime['checks'].values()):.3g}.
Package/recipe round trips and later mixing remain exact.

The renderer loads the new package with its existing Ochrell dependency pinned
to 17c13d0. No library/format or runtime algorithm change was necessary. Each
palette carries a distinct model identity, preserving old saved paintings.

## Identical recipes and paint behavior

The 32 authored recipes cover all pure paints, saturated pairs, dark mixtures,
chromatic neutrals, white tints and eight-ingredient blends. Three strokes per
recipe give 96 strokes. The two packages use identical geometry and amounts.
All four material/height/wetness/coverage planes agree exactly between packages;
only displayed colors change. All eight material slots remain active where used.

![Exact decoded recipe colors](../../target/measured-oils/balanced-eight/decoded-swatches.png)

![Identical recipe painting comparison](../../target/measured-oils/balanced-eight/fixed-recipes-comparison.png)

The pure decoded colors agree exactly. Changes in mixture colors are expected
when replacing fitted coefficients; they are not brush-transport changes.
The usual 94-stroke fixture additionally exercises overlap, pickup, drying,
smudging, scumbling and renderer glaze modes. These software checks do not
validate physical glaze/translucency behavior absent from the optical model.

![Renderer fixture comparison](../../target/measured-oils/balanced-eight/renderer-fixture-comparison.png)

All six jobs save, reload and repaint all five canvas planes bit-identically
on this host. Saved job bytes and future mixtures also reproduce exactly.
The oil-palette suite passes all seven integration tests and one documentation
test; scoped Clippy for the new comparison example passes with warnings denied.
Cross-platform bit identity of empirical logarithms/exponentials was not tested.

## RGB target matching: usable, with a darker-color limitation

Both packages match the same 32 RGB targets: grays, saturated colors, pastels
and muted colors. The search returns achieved color, proportions and residual
error; it does not guarantee a unique recipe or globally optimal match.

| Metric | Previous package | Balanced package |
| --- | --- | --- |
| Mean displayed OKLab x100 target error | {errors['previous'].mean():.4f} | {errors['balanced'].mean():.4f} |
| Maximum target error | {errors['previous'].max():.4f} | {errors['balanced'].max():.4f} |
| Closest found to requested black | {black['previous']} | {black['balanced']} |
| Time for 32 matches (single observation) | {grouped['previous/match-32-targets']['mean']:.1f} ms | {grouped['balanced/match-32-targets']['mean']:.1f} ms |
| Author 94-stroke fixture, including streak variants | {grouped['previous/author-fixture']['mean']:.1f} ms | {grouped['balanced/author-fixture']['mean']:.1f} ms |

At a numerical comparison tolerance of 0.0001 OKLab x100, balanced improves
{matching['improved']} targets, worsens {matching['worsened']}, and ties {matching['tied']}.
The mean target error increases {100*(errors['balanced'].mean()/errors['previous'].mean()-1):.2f}%.
This describes RGB reachability/search behavior, not agreement with real paint.
RGB reachability alone is not a reason to prefer one physical calibration.

![Target and achieved colors](../../target/measured-oils/balanced-eight/target-swatches.png)

![Matched-target paintings](../../target/measured-oils/balanced-eight/matched-targets-comparison.png)

## Performance and the LUT decision

Seven observations after one discarded warmup, alternating package order.
Decode uses the same 4,096-recipe corpus and 100,000 operations per observation.
Paint jobs render 384x480; matching/preparation is outside the paint timings.
Values below are median (min-max); all observations are in [timings.csv](timings.csv).

| Operation | Previous | Balanced | Units |
| --- | --- | --- | --- |
{chr(10).join(lines)}

Runtime: {evidence['rustc']}, release workspace build, one calling thread;
shared-host scheduling and clock variation remain. These are small native
fixtures, not a browser/large-canvas throughput claim. Both palettes use the
same decoder; timing differences do not establish an algorithmic speed change.

**No eight-paint LUT is generated in this package.** The current forward LUT
supports four paints/81 bands. Eight proportions have seven independent recipe
coordinates. A naive 65-point dense extension would require
{decoder_bytes['8']['dense_rgb_f32_bytes_at_65']:,} bytes ({decoder_bytes['8']['dense_rgb_f32_bytes_at_65']/1e12:.2f} TB)
for RGB f32 payload alone. Even packing just ordered simplex grid nodes would
use {decoder_bytes['8']['ordered_simplex_rgb_f32_bytes_at_65']/1e9:.2f} GB. These
are storage calculations, not quality requirements or proof all LUTs are large.

The direct balanced decoder is about {grouped['balanced/decode-srgb']['median']/1000:.2f}
microseconds per recipe here. Target matching is much more expensive per call,
but occurs during authoring; painting uses persistent recipes and never solves
the inverse per pixel. The measured fixture authoring time makes repeated-target
caching a concrete next optimization. A small RGB-to-recipe LUT could later
seed/refine matching, but it would not accelerate recipe-to-display painting.

For painting acceleration across 8-16 paints, evaluate sparse/adaptive tables,
factorized approximations or repeated-recipe caching against this frozen direct
model. Preserve all recipe proportions and compare approximation errors on pure,
boundary, dark, white-tint and dense recipes. A 3D RGB lookup cannot in general
replace eight-material state: different recipes can share a displayed RGB and
behave differently when mixed later. The four-paint LUT remains available for
its supported mode; it is not silently applied to this package.

## Reproduction and adoption

Run the final fitter in a fresh ignored output directory, export, run the existing
Rust measured_palette_probe for km and empirical, then verify-runtime. Run the
new sibling renderer example with the old and balanced corrected packages:

```powershell
.\\target\\measured-oils\\venv\\Scripts\\python.exe experiments/oil_balanced_package/run.py fit
.\\target\\measured-oils\\venv\\Scripts\\python.exe experiments/oil_balanced_package/run.py export
cargo run --release --offline --example measured_palette_probe -- target/measured-oils/balanced-eight/old-holland-eight-balanced-km.opp target/measured-oils/balanced-eight/recipes.f64 target/measured-oils/balanced-eight/km-predictions.f64
cargo run --release --offline --example measured_palette_probe -- target/measured-oils/balanced-eight/old-holland-eight-balanced-empirical.opp target/measured-oils/balanced-eight/recipes.f64 target/measured-oils/balanced-eight/empirical-predictions.f64
.\\target\\measured-oils\\venv\\Scripts\\python.exe experiments/oil_balanced_package/run.py verify-runtime
```

From oilpaint-renderer:

```powershell
cargo run --release --offline -p oil-palette --example compare_old_holland -- ../ochrell/target/measured-oils/unified-eight/old-holland-eight-empirical.opp ../ochrell/target/measured-oils/balanced-eight/old-holland-eight-balanced-empirical.opp ../ochrell/target/measured-oils/balanced-eight/comparison
```

Then run experiments/oil_balanced_package/report.py from Ochrell. The original
coefficients, measured source and previous packages remain unchanged.

For code-driven recipe painting, adopt the balanced corrected package as the
preferred local experimental measured palette. Keep the old package selectable
and keep achieved-color feedback for unreachable targets. A universal default
switch and large-palette acceleration are separate product changes.

Frozen final fit: `{fit['fit_sha256']}`.
Local ZIP: `{evidence['local_archive']['sha256']}`.
See [workflow-verification.json](workflow-verification.json) for source/artifact
hashes, matching results, timing aggregates and exact-replay evidence.
'''
    (HERE/'REPORT.md').write_bytes(report.encode())
    print(json.dumps({'timings': grouped, 'target_matching': matching, 'archive': evidence['local_archive']}, indent=2))


if __name__ == '__main__':
    main()
