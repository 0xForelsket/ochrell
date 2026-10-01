"""Audit the exact authoring cache benchmark and preserve its numerical report."""
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RENDERER = ROOT.parent/'oilpaint-renderer'
OUT = ROOT/'target/measured-oils/authoring-cache'
AFTER, BEFORE = OUT/'after', OUT/'before'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path):
    with path.open(encoding='utf-8', newline='') as stream:
        return list(csv.DictReader(stream))


def summary(values):
    return {'count': len(values), 'median': float(np.median(values)),
        'min': float(np.min(values)), 'max': float(np.max(values))}


def main():
    for name in ('timings.csv', 'checks.csv', 'target-reuse.csv'):
        shutil.copyfile(AFTER/name, HERE/name)
    rows = read_csv(HERE/'timings.csv')
    checks = read_csv(HERE/'checks.csv')
    reuse = read_csv(HERE/'target-reuse.csv')
    assert len(rows) == len(checks) == 63 and len(reuse) == 111
    assert sum(int(row['count']) for row in reuse) == 285
    assert (AFTER/'target-reuse.csv').read_bytes() == (BEFORE/'target-reuse.csv').read_bytes()
    baseline = (BEFORE/'uncached-fixture.opj').read_bytes()
    original = ROOT/'target/measured-oils/balanced-eight/comparison/balanced/renderer-fixture.opj'
    assert baseline == original.read_bytes() == (AFTER/'uncached-fixture.opj').read_bytes()
    for mode in ('disabled', 'cold', 'warm'):
        assert (AFTER/f'{mode}.opj').read_bytes() == baseline
        assert (AFTER/f'{mode}-planes.txt').read_bytes() == (AFTER/'disabled-planes.txt').read_bytes()
    assert len({(row['workload'], row['mode'], row['repetition']) for row in rows}) == 63
    timings, counts, hashes = {}, {}, {}
    for workload, requests, unique in [('fixture', 285, 111), ('repeated64', 64, 8), ('unique64', 64, 64)]:
        outputs = {r['output_sha256'] for r in checks if r['workload'] == workload}
        assert len(outputs) == 1
        hashes[workload] = next(iter(outputs))
        if workload == 'fixture':
            assert hashes[workload] == hashlib.sha256(baseline).hexdigest()
        for mode in ('disabled', 'cold', 'warm'):
            selected = [r for r in rows if r['workload'] == workload and r['mode'] == mode]
            assert {int(r['repetition']) for r in selected} == set(range(1, 8))
            expected = {'disabled': (0, requests, 0), 'cold': (requests-unique, unique, unique), 'warm': (requests, 0, unique)}[mode]
            for row in selected:
                assert int(row['requests']) == requests
                assert (int(row['hits']), int(row['misses']), int(row['entries'])) == expected
                assert int(row['evictions']) == 0
                assert int(row['capacity']) == (0 if mode == 'disabled' else 1024)
            key = f'{workload}/{mode}'
            timings[key] = {'author_ms': summary([float(r['author_ms']) for r in selected]),
                'prime_ms': summary([float(r['prime_ms']) for r in selected]),
                'prime_plus_author_ms': summary([float(r['prime_ms'])+float(r['author_ms']) for r in selected])}
            counts[key] = {'requests': requests, 'hits': expected[0], 'misses': expected[1], 'entries': expected[2]}
    roles = {}
    for row in reuse:
        listed = row['roles'].split(';')
        assert len(listed) == int(row['count'])
        for role in set(listed):
            entry = roles.setdefault(role, {'requests': 0, 'distinct_targets_within_role': 0})
            entry['requests'] += listed.count(role)
            entry['distinct_targets_within_role'] += 1
    sources = [RENDERER/'crates/oil-mix/src/palette.rs', RENDERER/'crates/oil-mix/tests/target_cache.rs',
        RENDERER/'crates/oil-palette/tests/workflow.rs', RENDERER/'crates/oil-palette/examples/authoring_cache.rs',
        RENDERER/'crates/oil-palette/src/lib.rs', RENDERER/'Cargo.lock', HERE/'PLAN.md', Path(__file__)]
    package = ROOT/'target/measured-oils/balanced-eight/old-holland-eight-balanced-empirical.opp'
    assert sha(package) == '643c6960282398b19f5e7eb4b8a788c104164fd1bc0adf83ddc7de8080088db7'
    result = {'timings': timings, 'counts': counts, 'profile_roles': roles,
        'requests': 285, 'distinct_targets': 111, 'repeated_requests': 174,
        'outputs_sha256': hashes, 'package_sha256': sha(package),
        'prechange_source_sha256': {name: sha(BEFORE/name) for name in ('palette.rs', 'authoring_cache.rs', 'profile.txt')},
        'source_sha256': {str(p.relative_to(ROOT.parent)).replace('\\', '/'): sha(p) for p in sources},
        'raw_sha256': {name: sha(HERE/name) for name in ('timings.csv', 'checks.csv', 'target-reuse.csv')},
        'verification': (AFTER/'verification.txt').read_text(),
        'scoped_tests': '17 unit/integration tests plus 1 documentation test passed in oil-mix/oil-palette release suites',
        'clippy': 'cargo clippy --offline -p oil-mix -p oil-palette --all-targets -- -D warnings passed',
        'rustc': subprocess.check_output(['rustc', '--version'], text=True).strip(),
        'cache': {'default_capacity': 1024, 'key': 'validated RGB f32 bits', 'policy': 'FIFO',
            'scope': 'one immutable palette/decoder instance', 'serialized': False,
            'concurrency': 'short synchronized lookup/insert; duplicate concurrent misses may solve independently'}}
    (HERE/'summary.json').write_bytes((json.dumps(result, indent=2)+'\n').encode())
    labels = {'fixture': '94-stroke fixture', 'repeated64': '64 calls / 8 colors', 'unique64': '64 new colors'}
    table, warm = [], []
    speedups = {}
    for workload, label in labels.items():
        a, b = timings[workload+'/disabled']['author_ms'], timings[workload+'/cold']['author_ms']
        speedups[workload] = a['median']/b['median']
        table.append(f"| {label} | {a['median']:.3f} ({a['min']:.3f}-{a['max']:.3f}) | {b['median']:.3f} ({b['min']:.3f}-{b['max']:.3f}) | {speedups[workload]:.2f}x | {counts[workload+'/cold']['hits']}/{counts[workload+'/cold']['requests']} |")
        w = timings[workload+'/warm']
        warm.append(f"| {label} | {w['author_ms']['median']:.4f} | {w['prime_ms']['median']:.3f} | {w['prime_plus_author_ms']['median']:.3f} |")
    fig, axes = plt.subplots(1, 3, figsize=(11, 4.4), layout='constrained')
    for ax, (workload, label) in zip(axes, labels.items()):
        for i, mode in enumerate(('disabled', 'cold')):
            s = timings[workload+'/'+mode]['author_ms']
            ax.bar(i, s['median']/1000, width=.65, color=['#526e89', '#1d8976'][i],
                yerr=[[max(0, s['median']-s['min'])/1000], [max(0, s['max']-s['median'])/1000]], capsize=4)
            ax.text(i, s['median']/1000, f"{s['median']/1000:.2f}s", ha='center', va='bottom', fontsize=9)
        ax.set_xticks([0, 1], ['Disabled', 'Empty cache'])
        ax.set_title(label, fontsize=11)
        ax.set_ylabel('Authoring time (seconds)')
        ax.set_ylim(bottom=0)
        ax.margins(y=.2)
    fig.suptitle('Exact caching accelerates repeated targets\nMedian of seven rotated observations; whiskers show min-max')
    fig.savefig(HERE/'comparison.png', dpi=160)
    plt.close(fig)
    role_table = '\n'.join(f"| {name} | {r['requests']} | {r['distinct_targets_within_role']} |" for name, r in roles.items())
    report = f'''# Exact target caching cuts fixture authoring time by {speedups['fixture']:.2f}x

The existing 94-stroke fixture makes **285 target searches for 111 distinct
exact RGB triples**. The new empty cache reuses 174 results (61.05% of requests),
reducing median authoring time from **{timings['fixture/disabled']['author_ms']['median']/1000:.3f} s to
{timings['fixture/cold']['author_ms']['median']/1000:.3f} s**. The complete authored job
is byte-identical to the pre-change job; cached and uncached paintings agree
exactly in every canvas plane and blurred height. No optical model was changed.

![Cold-cache authoring timings](comparison.png)

## What changed

Each renderer PaletteMixerN owns a bounded FIFO cache, enabled by default with
1024 entries. All three validated RGB f32 bit patterns form the key. Adjacent
colors, signed-zero bit patterns and other distinct inputs are not quantized.
The immutable palette/decoder instance owns the answers, so different optical
coefficients or prepared decoders never share entries implicitly.

The cache stores the entire original TargetMatch, including recipe, achieved
display color, both error values and original solver evaluation count. A hit's
evaluation field describes the search that originally produced that answer;
actual new searches are reported by cache misses. FIFO eviction only causes a
future repeat search; it does not change the resulting recipe.

The existing match_target and encode paths share this cache, including RGB
import's derived streak targets. Painting and direct decoding never touch it.
All 1-16-paint direct mixers and the existing prepared-four mixer use the same
cache implementation. Cache contents/counters are not saved in OPP/OPJ files;
reload starts empty. Existing saved formats and default paint model are unchanged.

## Where repeats occur

Before changing production code, an independent trace reproduced the exact
production OPJ2 bytes. Its target list is unchanged after implementation.

| Role | Requests | Distinct targets within role |
| --- | --- | --- |
{role_table}

Distinct counts within roles are not additive if the same target appears in
multiple roles. [target-reuse.csv](target-reuse.csv) preserves exact keys and all
request roles. No source paint spectra or fitted coefficients are in that file.

## Cold and repeated authoring

Seven observations after a discarded warmup, rotating disabled/cold/warm order
within each workload. Disabled and cold both begin empty; disabled retains
nothing. Units are milliseconds; parentheses show min-max across observations.

| Workload | Disabled | Cold cache | Median speedup | Cold hits / requests |
| --- | --- | --- | --- | --- |
{chr(10).join(table)}

The unique-color workload avoided zero searches. Its small timing difference
is within the broad shared-host variation; this is not evidence of a speedup
for previously unseen colors. The repeated workload visits eight targets eight
times; its gain reflects deliberate reuse, not arbitrary unique RGB input.

## Warm behavior and its cost

Warm mode first matches every requested target, then times the next authoring
pass. Priming is recorded separately and is not included in the warm-pass time.

| Workload | Warm authoring ms | Priming median ms | Median priming + authoring ms |
| --- | --- | --- | --- |
{chr(10).join(warm)}

The fixture's warm pass is {timings['fixture/warm']['author_ms']['median']:.4f} ms,
but priming took {timings['fixture/warm']['prime_ms']['median']/1000:.3f} s. Warm gains
apply when that same palette instance has already matched the exact targets.
They do not remove first-use matching costs or help an indefinitely changing
stream of novel colors. Priming every input beforehand simply relocates work.

The cache is not a disk-persistent warm start. There is no speedup claimed for
painting itself: that path consumes already-authored material recipes.

## Exactness and verification

- Four new focused tests cover full report bits, adjacent targets, invalid
  inputs, palette/model/decoder/load isolation, eviction/clear/disable behavior
  and shared concurrent callers.
- A new end-to-end test compares cached and disabled RGB import: report bits,
  complete saved job bytes, five canvas planes and blurred height all agree;
  painting does not change cache counters and saved reload starts empty.
- The oil-mix/oil-palette release suites pass **17 unit/integration tests and
  one documentation test**, including existing 8/10/16-material cases.
- Scoped all-target Clippy passes with warnings denied.
- All **63 measured benchmark runs** produce the identical expected output
  bytes within each workload. The fixed fixture also matches both the saved
  pre-change job and the prior balanced-package workflow's job.
- All three cache modes paint/reload at 384x480 with identical five-plane hashes
  and blurred heights. All measured hit/miss counts match the traced requests.
- The measured package SHA remains unchanged. The 107-family accuracy evidence
  and balanced coefficients were not modified or refitted.

Pre-change/current fixture OPJ2 SHA-256:
`{hashes['fixture']}`.

See [checks.csv](checks.csv), [timings.csv](timings.csv), and
[summary.json](summary.json) for every timing, result hash, counter and source hash.

## API and limits

The cache is already enabled for new renderer palette mixers. Use
`mixer.target_cache_stats()` to inspect it;
`mixer.with_target_cache_capacity(n)` to configure/reset it (zero disables);
and `mixer.clear_target_cache()` with exclusive mutable access to clear it.

Send + Sync is preserved. Lookup and insertion take short mutex locks; expensive
solving occurs outside them. Concurrent misses for the same key may both solve.
The benchmark uses one caller and does not measure contended throughput. Cache
capacity bounds retained entries; different identical-palette instances keep
separate caches and may repeat work independently.

This is an exact memoization optimization, not a forward LUT or a new inverse
approximation. It removes repeated work without changing the palette's color
range, physical accuracy, matching solver or persistent material state.

## Reproduction

From the sibling renderer checkout:

```powershell
cargo test --release --offline -p oil-mix -p oil-palette
cargo clippy --offline -p oil-mix -p oil-palette --all-targets -- -D warnings
cargo run --release --offline -p oil-palette --example authoring_cache -- ../ochrell/target/measured-oils/balanced-eight/old-holland-eight-balanced-empirical.opp ../ochrell/target/measured-oils/authoring-cache/after ../ochrell/target/measured-oils/authoring-cache/before/uncached-fixture.opj
```

The pre-change OPJ2 argument is optional for a fresh checkout. It is required
for reproducing this archived before/after check. Run this report script from
Ochrell after the benchmark. The [plan](PLAN.md) states the workloads and checks.
Use a fresh output directory to preserve existing timing runs when repeating.

Runtime: {result['rustc']}; native Windows release build, single caller,
no affinity pinning. Scheduling/clock variation is visible in the retained
observations. The cache-disabled comparator uses the same unchanged solver and
includes inexpensive counter/lock bookkeeping; the saved pre-change job confirms
output equivalence, not a stable timing comparison across separate sessions.
'''
    (HERE/'REPORT.md').write_bytes(report.encode())
    print(json.dumps({'speedups': speedups, 'fixture_cold': timings['fixture/cold'], 'verification': result['verification']}, indent=2))


if __name__ == '__main__':
    main()
