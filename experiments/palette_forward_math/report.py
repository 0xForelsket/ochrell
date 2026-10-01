"""Audit local forward-decoder evidence and generate the numerical report."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import platform
import statistics
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RENDERER = ROOT.parent / "oilpaint-renderer"
RAW = ROOT / "target/measured-oils/forward-math"
PACKAGE = ROOT / "target/measured-oils/balanced-eight/old-holland-eight-balanced-empirical.opp"
SCENES = ("fixed-recipes", "matched-targets", "renderer-fixture")
WIDTHS = (512, 1024, 2048)
MODES = ("reference", "algebraic", "exp-lut")
METRICS = ("reflectance", "raw_linear", "display_channel", "oklab100")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def write_csv(name, rows):
    with (HERE / name).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def stats(values):
    return {"median": statistics.median(values), "min": min(values), "max": max(values)}


def main():
    micro_errors, micro_timings, metadata = [], [], {}
    package_sha = sha(PACKAGE)
    assert package_sha == "643c6960282398b19f5e7eb4b8a788c104164fd1bc0adf83ddc7de8080088db7"
    frozen_sha = sha(ROOT / "target/measured-oils/balanced-eight/frozen-model.json")
    assert frozen_sha == "99cc38cb2751d8a09895e3a78375aabd003c6933c068145334bf604a71d70afc"
    for phase, n_modes in (("algebraic", 2), ("lookup", 3)):
        meta = dict(line.split("=", 1) for line in (RAW / phase / "verification.txt").read_text().splitlines())
        metadata[phase] = meta
        assert int(meta["recipes"]) == 62608
        assert meta["package_sha256"] == package_sha
        assert sha(RAW / phase / "recipes.f64") == meta["recipe_sha256"]
        errors = read_csv(RAW / phase / "errors.csv")
        times = read_csv(RAW / phase / "timings.csv")
        assert len(times) == n_modes * 5
        assert len(errors) == (n_modes - 1) * 7 * 4
        for mode in MODES[1:n_modes]:
            selected = [r for r in errors if r["decoder"] == mode]
            for metric in METRICS:
                assert sum(int(r["count"]) for r in selected if r["metric"] == metric) == 62608
            limits = {"reflectance": 2e-12, "raw_linear": 2e-12, "oklab100": .001} if mode == "algebraic" else dict(zip(METRICS, (1e-5, 2e-5, 1e-4, .01)))
            for row in selected:
                assert all(math.isfinite(float(row[k])) for k in ("mean", "p95", "max"))
                if row["metric"] in limits:
                    assert float(row["max"]) <= limits[row["metric"]]
                if row["family"] == "pure":
                    assert float(row["max"]) == 0
        micro_errors.extend({"phase": phase, **r} for r in errors)
        micro_timings.extend({"phase": phase, **r} for r in times)
    assert metadata["lookup"]["recipe_sha256"] == metadata["algebraic"]["recipe_sha256"]
    lookup_times = {
        mode: stats([float(r["ns_per_decode"]) for r in micro_timings if r["phase"] == "lookup" and r["decoder"] == mode])
        for mode in MODES
    }
    assert lookup_times["exp-lut"]["median"] <= .9 * lookup_times["algebraic"]["median"]

    paint_times, paint_errors, checks = [], [], []
    for width in WIDTHS:
        paint_times.extend(read_csv(RAW / "painting" / f"timings-{width}.csv"))
        paint_errors.extend(read_csv(RAW / "painting" / f"errors-{width}.csv"))
        checks.extend(read_csv(RAW / "painting" / f"checks-{width}.csv"))
        assert not (RAW / "painting" / f"process-{width}.err").read_text().strip()
        assert "renderer-fixture" in (RAW / "painting" / f"process-{width}.txt").read_text()
    assert len(paint_times) == 81 and len(paint_errors) == 27 and len(checks) == 162
    prior = {
        (r["scene"], r["width"], r["plane"]): r["sha256"]
        for r in read_csv(ROOT / "experiments/palette_canvas_scaling/checks.csv")
        if r["phase"] == "baseline" and r["mode"] == "direct"
    }
    assert len(prior) == 54
    checked = {(r["scene"], r["width"], r["decoder"], r["plane"]): r["sha256"] for r in checks}
    assert len(checked) == 162
    for row in checks:
        key = (row["scene"], row["width"], row["plane"])
        if row["decoder"] == "reference" or row["plane"] != "rgb":
            assert row["sha256"] == prior[key], row
    for row in paint_errors:
        width = int(row["width"])
        assert int(row["pixels"]) == width * (width * 5 // 4)
        metrics = ("channel_max", "oklab100_mean", "oklab100_max", "sampled_spectral_max", "sampled_linear_max")
        assert all(math.isfinite(float(row[k])) for k in metrics)
        if row["decoder"] == "reference":
            assert int(row["changed_float_pixels"]) == 0
        elif row["decoder"] == "algebraic":
            assert float(row["sampled_spectral_max"]) <= 2e-12
            assert float(row["sampled_linear_max"]) <= 2e-12
            assert float(row["oklab100_max"]) <= .001
        else:
            assert float(row["sampled_spectral_max"]) <= 1e-5
            assert float(row["sampled_linear_max"]) <= 2e-5
            assert float(row["channel_max"]) <= 1e-4
            assert float(row["oklab100_max"]) <= .01
    grouped = defaultdict(list)
    for row in paint_times:
        grouped[(row["scene"], int(row["width"]), row["decoder"])].append(float(row["paint_ms"]) / 1000)
    assert len(grouped) == 27 and all(len(v) == 3 for v in grouped.values())
    painting = [dict(scene=s, width=w, decoder=m, **stats(grouped[s, w, m])) for w in WIDTHS for s in SCENES for m in MODES]

    jobs = []
    for scene in SCENES:
        original_path = ROOT / f"target/measured-oils/balanced-eight/comparison/balanced/{scene}.opj"
        original = original_path.read_bytes()
        for tag, name in enumerate(("Reference", "AlgebraicV1", "ExpLutV1")):
            path = RAW / "painting" / f"{scene}-{name}.opj"
            data = path.read_bytes()
            assert data[:8] == original[:8] and data[12:-32] == original[12:-32]
            assert int.from_bytes(data[8:12], "little") == tag
            assert hashlib.sha256(data[:-32]).digest() == data[-32:]
            if tag == 0:
                assert data == original
            jobs.append(dict(scene=scene, decoder=MODES[tag], sha256=sha(path), bytes=len(data), original_sha256=sha(original_path)))

    golden = json.loads((RENDERER / "golden/2.0.0-dev.3.json").read_text())
    native = json.loads((RAW / "native-golden-check.json").read_text())
    assert native["engine"] == golden["engine"] == "2.0.0-dev.3"
    golden_cases = golden["cases"]
    assert len(golden_cases) == 31
    for name, digest in golden_cases.items():
        assert native["cases"][name]["sha256"] == digest, name

    for name, rows in (("decode-errors.csv", micro_errors), ("decode-timings.csv", micro_timings), ("paint-timings.csv", paint_times), ("paint-errors.csv", paint_errors), ("plane-checks.csv", checks)):
        write_csv(name, rows)
    max_errors = {mode: {metric: max(float(r["max"]) for r in micro_errors if r["phase"] == "lookup" and r["decoder"] == mode and r["metric"] == metric) for metric in METRICS} for mode in MODES[1:]}
    source_paths = [
        "crates/oil-mix/src/palette_forward.rs", "crates/oil-mix/src/palette.rs",
        "crates/oil-mix/src/lib.rs", "crates/oil-paint/src/lib.rs",
        "crates/oil-palette/src/lib.rs", "crates/oil-palette/src/codec.rs",
        "crates/oil-mix/examples/forward_math.rs", "crates/oil-palette/examples/forward_paint.rs",
        "crates/oil-mix/tests/forward_decoder.rs", "crates/oil-palette/tests/forward_jobs.rs",
    ]
    summary = dict(
        date="2026-10-01", host=platform.platform(),
        package_sha256=package_sha,
        frozen_model_sha256=frozen_sha,
        preparation_and_screen=metadata, decode_ns=lookup_times, max_recipe_errors=max_errors,
        paint_seconds=painting, saved_jobs=jobs, native_golden_cases=31,
        source_sha256={p: sha(RENDERER / p) for p in source_paths},
        report_source_sha256=sha(Path(__file__)),
        table_bytes=513 * 8, basis31_bytes=31 * 32,
        real_arithmetic_reflectance_error_bound=math.exp(3.2 / 512) * (3.2 / 512) ** 2 / 32,
        test_note="26 unit/integration tests plus 1 doctest passed; scoped all-target Clippy passed. See commands in REPORT.md.",
    )
    (HERE / "summary.json").write_bytes((json.dumps(summary, indent=2) + "\n").encode("utf-8"))

    colors = ("#607d8b", "#d28f36", "#278d83")
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.4), sharey=True)
    for ax, scene in zip(axes, SCENES):
        for i, (mode, color) in enumerate(zip(MODES, colors)):
            selected = [stats(grouped[scene, w, mode]) for w in WIDTHS]
            y = [r["median"] for r in selected]
            x = [n + (i - 1) * .25 for n in range(3)]
            ax.bar(x, y, .23, color=color, label=mode)
            ax.errorbar(x, y, yerr=[[r["median"] - r["min"] for r in selected], [r["max"] - r["median"] for r in selected]], fmt="none", ecolor="#333333", capsize=2)
        ax.set_title(scene)
        ax.set_xticks(range(3), [str(w) for w in WIDTHS])
        ax.set_xlabel("Canvas width (4:5 aspect)")
        ax.grid(axis="y", alpha=.2)
    axes[0].set_ylabel("Final-image render, seconds")
    axes[0].legend(frameon=False)
    fig.suptitle("Same saved recipes: median and min-max of three rotated rounds")
    fig.tight_layout()
    fig.savefig(HERE / "timings.png", dpi=160)
    plt.close(fig)

    def table_time(scene, width, mode):
        s = stats(grouped[scene, width, mode])
        return f'{s["median"]:.3f} ({s["min"]:.3f}-{s["max"]:.3f})'

    rows = []
    for w in WIDTHS:
        for s in SCENES:
            ref, alg, lut = (stats(grouped[s, w, m])["median"] for m in MODES)
            rows.append(f"| {s} | {w}x{w*5//4} | {table_time(s,w,'reference')} | {table_time(s,w,'algebraic')} | {table_time(s,w,'exp-lut')} | {ref/lut:.2f}x | {alg/lut:.2f}x |")
    numeric = [f'| {metric} | {max_errors["algebraic"][metric]:.9g} | {max_errors["exp-lut"][metric]:.9g} |' for metric in METRICS]
    lookup_paint = [r for r in paint_errors if r["decoder"] == "exp-lut"]
    lookup_paint_max = max(float(r["oklab100_max"]) for r in lookup_paint)
    lookup_channel = max(float(r["channel_max"]) for r in lookup_paint)
    fixture_row = next(r for r in lookup_paint if r["scene"] == "renderer-fixture" and r["width"] == "2048")
    text = f"""# Optional faster forward evaluation

**Keep both tested accelerators as explicit choices.** The algebraic version
removes redundant logarithms; the compact lookup then trades a small bounded
interpolation error for additional speed. The balanced Old Holland Eight model,
every material amount and the reference default remain unchanged.

On the 2048x2560, 94-stroke fixture, median final-image rendering is **4.901 s
reference, 3.050 s algebraic and 2.857 s lookup**: 1.72x reference-to-lookup.
The added lookup gain over algebraic is only 1.07x for this large fixture,
and 1.12-1.81x for the other measured scene/size combinations. Samples vary
substantially, so these are exploratory host timings, not confidence intervals
or a universal speed guarantee. No second table resolution was tried.

## What changed

The reference correction computes `sigmoid(log(r)-log1p(-r)+shift)` at every band.
The equivalent real-arithmetic expression is:

`r / (r + (1-r)*exp(-shift))`

`AlgebraicV1` uses that expression with the renderer's existing deterministic
exponential and precomputes the four Bernstein basis values per wavelength.
It preserves the same normalization, K/S accumulation, pair sum, K-M inverse,
projection, gamut mapping and pure/zero-shift branches. Floating-point evaluation
order differs, so bit identity with reference is not promised.

`ExpLutV1` interpolates 513 f64 samples of the exponential on [-1.6,1.6]. With
normalized amounts and controls bounded by 0.8, absolute shift is at most
`1.6*(1-1/N)`, hence at most 1.5 for N<=16. Queries outside the table interval
fall back to the algebraic exponential. This table represents one scalar
function; it neither collapses material dimensions nor samples recipe space.

For step h=3.2/512, the real-arithmetic relative exponential interpolation error
is at most `exp(h)*h*h/8`. Convex interpolation overestimates exp, and the
corrected reflectance error is at most one quarter of that bound: approximately
{summary['real_arithmetic_reflectance_error_bound']:.9g}. This derivation excludes
floating-point roundoff and does not alone bound gamut-mapped color error.

## Frozen recipe screen

[PLAN.md](PLAN.md) records the thresholds before evaluation. Both phases use
the same 62,608 recipes: eight pures, all 28 pair ramps with tiny edge fractions,
white tints, 192 nearly pure probes, 771 dark-family tints, 16,385 dense mixtures
and 16,384 sparse-face probes. Sparse probes use cyclic contiguous subsets,
not an exhaustive enumeration of all faces. The screen spans the recipe domain;
it is not additional experimental paint data.

Maximum absolute differences against the same frozen reference:

| Metric | Algebraic | Exp lookup |
| --- | ---: | ---: |
{chr(10).join(numeric)}

Displayed OKLab distance is multiplied by 100; it is not CIEDE2000. All pure
endpoints remain bit-identical. Algebraic displayed triples are bit-identical
for 62,604/62,608 probes; the four differences are at near-zero rounding scale.
Lookup triples are bit-identical for 2,686 probes. [decode-errors.csv](decode-errors.csv)
retains family counts and mean/p95/max in both phases; p95 is the lower order
statistic `sorted[floor((n-1)*0.95)]`.

Declared algebraic limits are 2e-12 spectrum/raw-linear RGB and 0.001 displayed
OKLab*100. Lookup limits are 1e-5 spectrum, 2e-5 raw-linear RGB, 1e-4 displayed
channel and 0.01 displayed OKLab*100. Every screen passed without relaxing them.

The paired lookup-phase decode medians are {lookup_times['reference']['median']:.3f} ns
reference, {lookup_times['algebraic']['median']:.3f} ns algebraic and
{lookup_times['exp-lut']['median']:.3f} ns lookup. The lookup is
{lookup_times['algebraic']['median']/lookup_times['exp-lut']['median']:.2f}x algebraic
({100*(1-lookup_times['exp-lut']['median']/lookup_times['algebraic']['median']):.1f}% less time),
passing the declared 10% time-reduction gate. These include display conversion
on a fixed 4,096-recipe corpus: one warmup and five rotating measured rounds of
100,000 calls. [decode-timings.csv](decode-timings.csv) also retains the earlier
algebraic-only phase; do not mix timing phases to claim a gain. Preparing all
three benchmark evaluators together took 0.0572 ms in the lookup phase, one
observation rather than a stable preparation benchmark.

## Full paintings

All modes load the same previously authored OPJ2 jobs and use `paint_final`.
No target search occurs during rendering. Initialization, simulation, final
display and blur are timed; loading, hashing, error measurement and replay
checks are outside the timer. Each mode gets one warmup and three rotating
measured rounds. Times are seconds, median (min-max).

| Scene | Canvas | Reference | Algebraic | Exp lookup | Reference/lookup | Algebraic/lookup |
| --- | --- | --- | --- | --- | ---: | ---: |
{chr(10).join(rows)}

![Measured final-image rendering](timings.png)

Every pixel is checked for displayed error. The worst lookup displayed channel
difference is {lookup_channel:.9g}; the worst OKLab*100 distance is
{lookup_paint_max:.9g}. Approximately 4,096 material states per scene/size also
receive spectral and raw-linear checks. All thresholds pass. At 2048x2560 the
lookup changes the fixture's quantized 8-bit RGB at {fixture_row['changed_8bit_pixels']}
of {fixture_row['pixels']} pixels; tiny differences can cross a rounding boundary.
These files are not byte-identical images. Numerical differences from this
accelerator are very small; no controlled perceptual study was performed.

[paint-errors.csv](paint-errors.csv) records all scene/size/mode results.
[plane-checks.csv](plane-checks.csv) records 162 plane hashes. Material, height,
wetness, coverage and blurred height match the earlier pre-change baseline
exactly for every mode. Reference RGB also matches that baseline. Every timed
output matches an independently reloaded job under its selected decoder, and
transport statistics match reference. Switching back to reference restores
the original job bytes; accelerated jobs differ only in decoder tag/checksum.

## Memory and saved behavior

The lookup occupies **4,104 bytes per mixer**, with **992 bytes** of prepared
basis for 31 bands (2,592 for 81). The evaluator also owns a cloned immutable
optical model and normal object/allocation overhead; 4 KiB is not its complete
allocation. `forward_auxiliary_bytes()` counts basis plus table, excluding that
clone. Production reference mixers instantiate neither evaluator nor table;
the standalone reference microbenchmark evaluator does prepare an unused basis.

No canvas plane is added. The eight-paint 2048x2560 fixture retains 300 MiB of
canvas buffers. This validation harness additionally retains reference RGB
while comparing candidates; it is not a production process-memory measurement.

Use `job.with_forward_decoder(ForwardDecoder::ExpLutV1)?` or `AlgebraicV1`.
Both work with the existing immediate or final-only paint API. Target search
and streak-recipe authoring continue to use reference optics, so the selected
display method does not alter authored amounts. Achieved-color reports use the
selected decoder, and switching mode clears the target cache.

OPJ2 records versioned tags 0=reference, 1=algebraic-v1, 2=exp-lut-v1; preparation
is reconstructed on load and its table section remains empty. Unknown tags
are rejected. Old tag-0 jobs, OPP/OPR identities, OPJ1 and existing defaults retain
their meaning. Prepared-four OPL1 mixers reject these alternate choices.
The global engine version stays 2.0.0-dev.3: existing inputs retain their outputs,
while approximate behavior requires a new explicit decoder tag. All 31 existing
native golden cases pass. New decoder cross-host parity has not been established.

## Verification and reproduction

Renderer tests passed: 26 unit/integration cases plus one doctest across oil-mix,
oil-paint and oil-palette. New tests cover 1/4/8/10/16 materials and both 31/81
bands, extreme K/S, zero absorption, control bounds, pure/tiny/pair/dense mixtures,
table edges/fallback, invalid amounts, cache invalidation, unchanged target and
streak recipes, actual achieved colors, malformed tags and selected saved replay.
Scoped all-target Clippy passes with warnings denied.

From the sibling renderer (substitute the local package and output paths):

```text
cargo test --release --offline -p oil-mix -p oil-paint -p oil-palette
cargo clippy --offline -p oil-mix -p oil-paint -p oil-palette --all-targets -- -D warnings
cargo run --release --offline -p oil-mix --example forward_math -- <balanced.opp> <output>/algebraic algebraic
cargo run --release --offline -p oil-mix --example forward_math -- <balanced.opp> <output>/lookup lookup
cargo build --release --offline -p oil-palette --example forward_paint
cargo run --release --offline -p oil-xhost --bin xhost -- --out <output>/native-golden-check.json
```

From Ochrell, run `experiments/palette_forward_math/run-paint.ps1`, then this
`report.py` with the existing scientific Python environment. No matching or
fitting is rerun. [summary.json](summary.json) pins source, recipe, package and
saved-job hashes, timings, limits and preparation metadata. The package SHA-256
is `{package_sha}`. Raw recipes, models, saved jobs and preview PNGs remain under
ignored `target/measured-oils/forward-math/`; committed results contain numerical
summaries, hashes and the timing chart.

This pass establishes an engineering option for evaluating the existing fitted
model faster. It makes no improvement claim against physical paint measurements
and does not change the previously reported calibration tradeoffs. Prefer the
lookup for opt-in fast final rendering when its approximation is acceptable;
retain algebraic for a rounding-scale alternative and reference for audit.
"""
    (HERE / "REPORT.md").write_bytes(text.encode("utf-8"))
    print(json.dumps({"recipe_count": 62608, "paint_rounds": len(paint_times), "plane_hashes": len(checks), "native_golden_cases": 31, "recipe_maxima": max_errors, "painting_oklab100_max": lookup_paint_max}, indent=2))


if __name__ == "__main__":
    main()
