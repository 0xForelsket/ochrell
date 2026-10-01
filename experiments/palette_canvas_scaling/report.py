"""Audit realistic-canvas profiling and exact final-display acceleration."""
import csv
import hashlib
import json
import math
from pathlib import Path
import subprocess
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RENDERER = ROOT.parent/'oilpaint-renderer'
OUT = ROOT/'target/measured-oils/canvas-scaling'
WIDTHS = (512, 1024, 2048)
SCENES = ('fixed-recipes', 'matched-targets', 'renderer-fixture')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows):
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def stats(values):
    return {'count': len(values), 'median': float(np.median(values)),
        'min': float(np.min(values)), 'max': float(np.max(values))}


def blur_budget(width):
    """Conservative live-buffer estimate for this fixture's one sigma=.01 blur."""
    height = width*5//4
    n = width*height
    sigma = width*.01
    if sigma < 8:
        kernel = int(8*sigma+1+.5) | 1
        scratch = 8*n + 4*width + 12*kernel
    else:
        factor = math.ceil(sigma/4)
        sw, sh = max(width//factor, 2), max(height//factor, 2)
        small = sw*sh
        kernel = int(8*sigma/factor+1+.5) | 1
        gaussian = 12*small + 4*sw + 12*kernel
        resize = 8*small + 4*n + 24*width
        scratch = max(gaussian, resize)
    return 56*n + scratch


def main():
    timing, checks, memory = [], [], []
    for phase in ('baseline', 'accelerated'):
        for width in WIDTHS:
            timing.extend({'phase': phase, **r} for r in read_csv(OUT/phase/f'timings-{width}.csv'))
            checks.extend({'phase': phase, **r} for r in read_csv(OUT/phase/f'checks-{width}.csv'))
        memory.extend({'phase': phase, **r} for r in read_csv(OUT/phase/'process-memory.csv'))
    assert len(timing) == 180 and len(checks) == 270 and len(memory) == 6
    assert all(int(r['exit_code']) == 0 and int(r['observed_peak_working_set_bytes']) > 0 for r in memory)
    hashes = {(r['phase'], r['scene'], r['width'], r['mode'], r['plane']): r['sha256'] for r in checks}
    assert len(hashes) == len(checks)
    groups, comparisons = {}, {}
    for width in WIDTHS:
        for scene in SCENES:
            subset = [r for r in timing if int(r['width']) == width and r['scene'] == scene]
            for field in ('height', 'strokes', 'deposits', 'touched_pixels', 'canvas_buffer_bytes', 'alpha_bits'):
                assert len({r[field] for r in subset}) == 1, (width, scene, field)
            example = subset[0]
            expected_buffers = width*(width*5//4)*(60 if scene == 'renderer-fixture' else 56)
            assert int(example['canvas_buffer_bytes']) == expected_buffers
            for phase, modes in [('baseline', ('direct', 'bypass')), ('accelerated', ('direct', 'bypass', 'deferred'))]:
                for mode in modes:
                    selected = [r for r in subset if r['phase'] == phase and r['mode'] == mode]
                    assert {int(r['repetition']) for r in selected} == {0, 1, 2, 3}
                    selected = [r for r in selected if r['repetition'] != '0']
                    key = f'{phase}/{scene}/{width}/{mode}'
                    groups[key] = {'paint_ms': stats([float(r['paint_ms']) for r in selected]),
                        'blur_ms': stats([float(r['blur_ms']) for r in selected]) if selected[0]['blur_ms'] else None,
                        'deposits': int(example['deposits']), 'touched_pixels': int(example['touched_pixels']),
                        'canvas_buffer_bytes': expected_buffers}
                    for plane in ('lat', 'rgb', 'h', 'wet', 'cover', 'hblur'):
                        if mode != 'bypass' or plane != 'rgb':
                            assert hashes[phase, scene, str(width), mode, plane] == hashes['baseline', scene, str(width), 'direct', plane]
            a, b, d = [groups[f'accelerated/{scene}/{width}/{mode}']['paint_ms']['median'] for mode in ('direct', 'bypass', 'deferred')]
            comparisons[f'{scene}/{width}'] = {'speedup': a/d, 'time_reduction_percent': 100*(1-d/a),
                'bypass_removable_fraction_percent': 100*(1-b/a), 'remaining_bypass_ms': b,
                'direct_decode_calls': int(example['deposits'])+1, 'deferred_decode_calls': int(example['touched_pixels'])+1,
                'removed_decode_calls': int(example['deposits'])-int(example['touched_pixels'])}
    native_file = OUT/'native-golden-check.json'
    native = json.loads(native_file.read_text())
    golden_file = RENDERER/'golden/2.0.0-dev.3.json'
    golden = json.loads(golden_file.read_text())
    assert native['engine'] == golden['engine']
    assert all(native['cases'][name]['sha256'] == digest for name, digest in golden['cases'].items())
    source_files = [RENDERER/'crates/oil-kernel/src/brush.rs', RENDERER/'crates/oil-palette/src/lib.rs',
        RENDERER/'crates/oil-palette/examples/canvas_scaling.rs', RENDERER/'crates/oil-palette/tests/many_paints.rs',
        RENDERER/'crates/oil-palette/tests/workflow.rs', RENDERER/'crates/oil-image/src/lib.rs', RENDERER/'Cargo.lock',
        HERE/'PLAN.md', HERE/'run.ps1', Path(__file__)]
    model = ROOT/'target/measured-oils/balanced-eight/old-holland-eight-balanced-empirical.opp'
    assert sha(model) == '643c6960282398b19f5e7eb4b8a788c104164fd1bc0adf83ddc7de8080088db7'
    result = {'groups': groups, 'comparisons': comparisons, 'process_memory': memory,
        'fixture_blur_live_buffer_estimate_bytes': {str(w): blur_budget(w) for w in WIDTHS},
        'verification': {'measured_runs': 135, 'warmup_runs': 45, 'scene_size_pairs': 9,
            'all_valid_output_planes_identical_to_prechange': True, 'all_transport_statistics_identical': True,
            'native_golden_cases_passed': len(golden['cases']), 'native_total_cases': len(native['cases']),
            'engine_version': native['engine'], 'native_report_sha256': sha(native_file), 'golden_sha256': sha(golden_file),
            'tests': '12 unit/integration tests plus 1 doctest in oil-kernel/oil-paint/oil-palette release suites passed',
            'clippy': 'scoped all-target Clippy with warnings denied passed'},
        'model_sha256': sha(model),
        'job_sha256': {name: sha(ROOT/f'target/measured-oils/balanced-eight/comparison/balanced/{name}.opj') for name in SCENES},
        'source_sha256': {p.relative_to(ROOT.parent).as_posix(): sha(p) for p in source_files},
        'before_source_sha256': {name: sha(OUT/'baseline'/name) for name in ('canvas_scaling.rs', 'brush.rs', 'palette-lib.rs')},
        'rustc': subprocess.check_output(['rustc', '--version'], text=True).strip()}
    write_csv(HERE/'timings.csv', timing)
    write_csv(HERE/'checks.csv', checks)
    write_csv(HERE/'process-memory.csv', memory)
    (HERE/'summary.json').write_bytes((json.dumps(result, indent=2)+'\n').encode())
    titles = ['96 fixed-recipe strokes', '96 matched-target strokes', '94-stroke layered fixture']
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.5), layout='constrained')
    for ax, scene, title in zip(axes, SCENES, titles):
        for mode, label, color in [('direct', 'Immediate display', '#b47d42'), ('deferred', 'Exact final display', '#168a78'), ('bypass', 'Diagnostic bypass', '#8a9097')]:
            selected = [groups[f'accelerated/{scene}/{w}/{mode}']['paint_ms'] for w in WIDTHS]
            y = np.array([s['median'] for s in selected])/1000
            low = y-np.array([s['min'] for s in selected])/1000
            high = np.array([s['max'] for s in selected])/1000-y
            ax.errorbar(WIDTHS, y, yerr=[low, high], marker='o', capsize=3, label=label, color=color,
                linestyle='--' if mode == 'bypass' else '-')
        ax.set_xticks(WIDTHS)
        ax.set(xlabel='Canvas width (4:5 aspect)', ylabel='Painting time (seconds)', title=title, ylim=(0, None))
    axes[0].legend(fontsize=8)
    fig.suptitle('Exact final display avoids repeated pixel decoding\nThree rotated observations after warmup; whiskers show min-max')
    fig.savefig(HERE/'timings.png', dpi=160)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 4.5), layout='constrained')
    ax.plot(WIDTHS, [w*(w*5//4)*56/2**20 for w in WIDTHS], 'o-', label='Swatch canvas buffers')
    ax.plot(WIDTHS, [w*(w*5//4)*60/2**20 for w in WIDTHS], 'o-', label='Fixture canvas incl. blurred height')
    observed = [int(next(r for r in memory if r['phase'] == 'accelerated' and int(r['width']) == w)['observed_peak_working_set_bytes'])/2**20 for w in WIDTHS]
    ax.plot(WIDTHS, observed, 'o--', label='Observed benchmark-process peak')
    ax.set_xticks(WIDTHS)
    ax.set(xlabel='Canvas width (4:5 aspect)', ylabel='MiB', ylim=(0, None), title='Eight-paint memory scales with pixel count')
    ax.legend()
    fig.savefig(HERE/'memory.png', dpi=160)
    plt.close(fig)
    rows, mem_rows = [], []
    for width in WIDTHS:
        for scene in SCENES:
            key = f'{scene}/{width}'
            d, f, b = [groups[f'accelerated/{key}/{mode}']['paint_ms'] for mode in ('direct', 'deferred', 'bypass')]
            rows.append(f"| {scene} | {width}x{width*5//4} | {d['median']/1000:.3f} ({d['min']/1000:.3f}-{d['max']/1000:.3f}) | {f['median']/1000:.3f} ({f['min']/1000:.3f}-{f['max']/1000:.3f}) | {comparisons[key]['speedup']:.2f}x | {b['median']/1000:.3f} |")
        peak = next(r for r in memory if r['phase'] == 'accelerated' and int(r['width']) == width)
        mem_rows.append(f"| {width}x{width*5//4} | {width*(width*5//4)*56/2**20:.2f} | {width*(width*5//4)*60/2**20:.2f} | {blur_budget(width)/2**20:.2f} | {int(peak['observed_peak_working_set_bytes'])/2**20:.2f} |")
    largest = comparisons['renderer-fixture/2048']
    largest_direct_s = groups['accelerated/renderer-fixture/2048/direct']['paint_ms']['median']/1000
    largest_final_s = groups['accelerated/renderer-fixture/2048/deferred']['paint_ms']['median']/1000
    fractions = [c['bypass_removable_fraction_percent'] for c in comparisons.values()]
    report = f'''# Realistic canvas profiling and exact final-display acceleration

**Recipe-to-color decoding dominates these eight-paint scenes.** Replacing only
the display evaluation with a diagnostic bypass removes approximately
{min(fractions):.1f}-{max(fractions):.1f}% of wall time. The remaining work includes brush/material
simulation, allocation, RGB writes, blur and drying. This is a controlled timing
subtraction, not an instruction-level profiler or a working display mode.

The resulting optimization is an explicit **paint_final(width)** API. It runs
the unchanged material simulation, then calls the unchanged direct decoder once
per painted pixel. The 2048x2560 layered fixture improves from **{largest_direct_s:.3f} s to
{largest_final_s:.3f} s ({largest['speedup']:.2f}x)**, with all final bits identical. Existing paint(width,
after_layer) retains its per-layer preview behavior. No LUT, optical approximation,
refit, recipe reduction, additional canvas plane or saved-format change is used.

## Same scenes at larger sizes

Load the three existing balanced-package OPJ2 jobs, with identical models,
recipes, geometry and seeds. All matching happened when those jobs were authored.
Widths are 512, 1024 and 2048 with the original 4:5 aspect. One warmup precedes
three measured repetitions; direct/bypass/deferred order rotates each round.
Times below are seconds, median (min-max), from the paired accelerated run.

| Scene | Canvas | Immediate display | Exact final display | Speedup | Diagnostic bypass median |
| --- | --- | --- | --- | --- | --- |
{chr(10).join(rows)}

![Timing by size and scene](timings.png)

The separate pre-change profile is retained in [timings.csv](timings.csv), with
phase=baseline. Speedups above use same-run paired comparisons; historical runs
show host/clock variation and must not be mixed into a claimed improvement.
Initialization is included; loading/matching, hashing and replay validation are
outside the timers. The harness times blur separately in direct/bypass runs;
the public final-only API is measured end-to-end and does not expose blur timing.

## Why the exact optimization works

The brush reads recipe, height, wetness and coverage planes to transport paint.
It does not read RGB. Previously each successful deposit also decoded its new
material state, even if another deposit later replaced that displayed color.
Every such deposit adds positive alpha to coverage, so positive final coverage
identifies every pixel whose display must be refreshed.

For the 2048 fixture, immediate rendering makes
{largest['direct_decode_calls']:,} display calls including the ground; final-only
rendering makes {largest['deferred_decode_calls']:,}. It avoids
{largest['removed_decode_calls']:,} intermediate decodes while retaining the exact
final recipe and spectral evaluation. Counts follow directly from the verified
deposit statistics and positive-coverage pixel counts; no per-pixel timer or
atomic instrumentation is included in performance runs.

Swatches revisit pixels less frequently than the layered fixture, so their gains
are smaller. This strategy does not eliminate decoding cost for the final image.
It is useful exact acceleration, not a claim that large-canvas performance is
solved or that an approximate forward accelerator cannot help further.

## Memory

Buffer capacities are measured from the returned canvas: 56 bytes/pixel for
eight material floats, RGB, height, wetness and coverage, plus 4 bytes/pixel
when blurred height exists. The final-only path uses the same capacities.

| Canvas | Swatch buffers MiB | Fixture buffers MiB | Source-estimated fixture blur peak buffers MiB | Observed process peak MiB |
| --- | --- | --- | --- | --- |
{chr(10).join(mem_rows)}

![Canvas memory and observed process peak](memory.png)

The blur estimate includes temporary Gaussian/resize buffers from oil-image's
source, conservatively retaining the old small image during shadowing. It is
not a whole-process estimate. At small sigma, the Gaussian allocates full-size
temporary planes; at larger sigma the existing implementation downsamples first.
The unchanged bristle buffers, model/matcher, metadata and allocator overhead
are outside canvas accounting.

Observed process peaks come from Windows PeakWorkingSet64 sampled every 100 ms
in a separate native benchmark process per width. They include all three scenes,
verification/hash work and allocator behavior, not an isolated paint allocation.
Both phases and every observation are retained in [process-memory.csv](process-memory.csv).
No inference is made about WASM memory limits, mobile devices or other hosts.

## Correctness and compatibility

- The direct profiling harness matches the public paint API at all nine
  scene/size combinations. Its source mirrors the same public brush/blur calls.
- Bypass preserves every non-RGB plane and all transport statistics. It is only
  diagnostic and cannot be selected as a persisted/display decoder.
- Across 135 measured runs and 45 warmups, every valid final image and all
  material/height/wetness/coverage/blurred-height hashes match the pre-change
  direct baseline. Stroke counts, deposits and alpha bits agree as well.
- Unit/integration checks cover unchanged layer previews, blank/untouched ground,
  saved replay, limits and prepared-four plus direct 8/10/16-paint paths.
  Twelve unit/integration tests and one documentation test pass in the scoped
  oil-kernel/oil-paint/oil-palette release suites. Scoped all-target Clippy passes.
- All {len(golden['cases'])} existing native golden case hashes match engine
  {native['engine']}, including default Ochrell, RGB and Mixbox kernel/lighting
  cases and the existing planning cases. No golden or version was rewritten.
  Other hosts/browsers were not rerun; empirical optical cross-platform bit
  identity remains outside this local result.
- Saved package/job bytes, the frozen balanced model and the 107-family accuracy
  evidence remain unchanged. These are engineering checks, not new paint accuracy
  measurements.

See [checks.csv](checks.csv) and [summary.json](summary.json) for all hashes,
counters, source versions and the native golden comparison record.

## Use and next decision

For code-driven final renders:

```rust
let (canvas, stats) = job.paint_final(2048)?;
```

Keep job.paint(width, callback) when intermediate layer previews are needed.
The final-only method is explicit and requires no model migration or LUT file.
Existing jobs can be loaded and rendered by either API with identical final
output. The low-level material-only stroke function documents that hosts must
refresh RGB before exposing an image.

This is the selected first forward-work optimization because it avoids work
without introducing an approximation error budget. An eight-to-sixteen-paint
LUT still needs a representation that avoids dense simplex growth. If more
painting throughput is required, profile the remaining direct final decode and
compare a bounded-error accelerator against this frozen exact path. No such LUT
is claimed or generated by this step.

## Reproduction

From oilpaint-renderer, build the canvas_scaling example in release mode; then
run this repository's experiments/palette_canvas_scaling/run.ps1 -Phase accelerated.
The runner launches hidden native processes, writes their logs and samples
process memory. Original baseline sources are preserved under ignored target/;
do not overwrite that phase when reproducing a new run.

```powershell
cargo build --release --offline -p oil-palette --example canvas_scaling
cargo test --release --offline -p oil-kernel -p oil-paint -p oil-palette
cargo clippy --offline -p oil-kernel -p oil-paint -p oil-palette --all-targets -- -D warnings
```

The native xhost executable generates the report compared to the existing
golden/2.0.0-dev.3.json; this report script audits all CSVs and hashes. It expects
the local saved jobs from the balanced package study. Raw measured packages and
self-contained OPJ files remain under ignored target/.

Runtime: {result['rustc']}, native Windows release build, one calling thread,
no affinity pinning. Results are for these three fixtures and sizes, not a
general interactive-latency guarantee.
'''
    (HERE/'REPORT.md').write_bytes(report.encode())
    print(json.dumps({'fixture2048': largest, 'golden_cases': len(golden['cases']),
        'valid_output_hashes_match': True, 'observations': len(timing)}, indent=2))


if __name__ == '__main__':
    main()
