"""Render round-one evidence without rerunning or altering historical measurements."""
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / "results/optimization/round1"
screen = json.loads((R / "screening.json").read_text())
confirm = json.loads((R / "confirmation.json").read_text())
holdout = json.loads((R / "holdout.json").read_text())
chosen = "split_both"
runs = confirm["runs"]
ops = list(runs[0]["medians_ns"])
results = {}
for op in ops:
    a = statistics.median(r["medians_ns"][op] for r in runs if r["candidate"] == "baseline")
    b = statistics.median(r["medians_ns"][op] for r in runs if r["candidate"] == chosen)
    results[op] = dict(baseline_ns=a, selected_ns=b, speedup=a / b, time_reduction_percent=100 * (1 - b / a))
exact_rows = sum(v["samples"] for v in holdout["quality"]["cases"].values())
report = [
    "# Optimization round 1: separate optics from color integration", "",
    "Baseline commit: `17531c6`. Selected candidate: `split_both`.",
    "The runtime change separates independent wavelength calculations from the",
    "ordered RGB sum in encoding and decoding. Equations, coefficient data,",
    "wavelength counts, residual, gamut mapping, public API and state size are",
    "unchanged. This is a CPU optimization, not a new color model.", "",
    "## Confirmed performance", "",
    "Windows 11 x64, Core Ultra 7 258V, rustc 1.91.1/MSVC; one process pinned to",
    "logical CPU 0 (not a claim that it is the fastest core). Release, LTO off,",
    "codegen-units=1, no target-cpu override or fast-math. Four runs per executable",
    "in ABBA then BAAB order, 500,000 operations and nine measured repetitions",
    "per operation/run; each run discards a warmup round and rotates operation",
    "order. Table values are medians of the four run medians. Seed 1907.", "",
    "| Operation | Baseline ns | Selected ns | Speedup | Time reduction |",
    "|---|---:|---:|---:|---:|",
]
for op, r in results.items():
    report.append(f"| {op} | {r['baseline_ns']:.2f} | {r['selected_ns']:.2f} | {r['speedup']:.2f}x | {r['time_reduction_percent']:.1f}% |")
report += [
    "", "The two balanced four-run blocks separately improve cached mix/decode,",
    "full RGB mixing and streamed updates. Absolute times still vary with CPU",
    "frequency/background activity. The unchanged interpolation control measured",
    "about 9% slower in this sample; that unfavorable result is retained, and no",
    "interpolation improvement is claimed. These results do not predict a renderer",
    "speedup or replace the earlier integration benchmark conditions.", "",
    "Emitted x86-64 assembly contains packed `divps` and `sqrtps` instructions in",
    "the independent optics loop. The compiler can process several wavelengths",
    "together while the RGB sum keeps its original order. Source remains portable",
    "safe Rust: no intrinsics, architecture-specific code or runtime dependency.", "",
    "The selected probe executable grew from 237,568 to 240,128 bytes (+2,560).",
    "The material remains 340 bytes. The decoder adds a stack reflectance array",
    "(41 f32 values / 81 f64 values in source); no heap allocation is introduced.", "",
    "## Numerical acceptance", "",
    f"Both seed 20260930 and independently selected holdout seed 1907 contain {exact_rows:,}",
    "records: random continuous RGB plus a 16-cubed grid, reconstruction, pair",
    "mixes, white/black addition, weighted/grouped states, full RGB calls, 256",
    "repeated updates, 4,096 tiny pickups, canonical colors and extreme valid",
    "imported K/S magnitudes. All decoded RGB bits and fast-material component",
    "fingerprints match the frozen baseline exactly in both runs. Fast/reference",
    "errors are recorded in each row and unchanged by the selected candidate.", "",
    "The existing 25 release tests passed for the selected candidate. After the",
    "experiment, a new fast/reference scale-invariance regression test was added;",
    "all 26 release tests pass. The basic example remains `[101, 152, 94]`.",
    "Exact results were verified on this compiler/host; other platforms still",
    "need their own execution measurements. No real-paint accuracy claim changes.", "",
    "## All screened candidates, including rejection", "",
    "The initial screening ran sequentially and had substantial timing drift,",
    "including changes in unchanged operations. Its first baseline was unusually",
    "slow. These raw values are for audit, not speedup claims; selection was",
    "followed by the alternating confirmation above.", "",
    "| Candidate | Existing tests | Exact numerical gate | Cached mix/decode ns | Full RGB ns |",
    "|---|---|---|---:|---:|",
]
for name, v in screen["candidates"].items():
    report.append(f"| {name} | {'pass' if v['tests_pass'] else 'fail'} | {'pass' if v['quality']['exact'] else 'fail'} | {v['medians_ns']['cached_mix_decode']:.2f} | {v['medians_ns']['full_rgb']:.2f} |")
report += [
    "", "The one-division algebraic decoder was rejected. It passed the old unit",
    "tests but changed many RGB bits; valid imported coefficient scales caused",
    "product overflow/underflow, with worst reference discrepancy near 100",
    "DEOK100. Small ordinary-color errors would have hidden that domain failure.",
    "The added scale-invariance test protects it explicitly. Inlining variants",
    "were not promoted; broader inlining also increased executable size. Their",
    "screening alone is insufficient to claim they are universally slower.", "",
    "## Reproduce", "",
    "From a Git checkout retaining baseline `17531c6`, with Rust and Python:", "",
    "```powershell",
    "python tools/hillclimb.py --cpu 0 --out target/hillclimb/reproduce-round1",
    "python tools/hillclimb.py --cpu 0 --out target/hillclimb/reproduce-round1 --confirm split_both --iterations 500000 --repeats 9",
    "python tools/hillclimb.py --cpu 0 --out target/hillclimb/reproduce-round1 --holdout split_both",
    "cargo test --release --offline",
    "cargo run --release --offline --example basic",
    "```", "",
    "The runner reads baseline source from Git, temporarily applies each recorded",
    "transformation, and restores the starting working file in a finally block.",
    "It refuses to overwrite an unexpected concurrent edit. Separate output",
    "directories get separate temporary executables. Omit `--cpu` on platforms",
    "without affinity support; doing so changes benchmark conditions. The new",
    "regression test makes the algebraic candidate fail in a fresh reproduction,",
    "as intended; the retained original screen predates that test.", "",
    "Raw timing CSVs, compressed numerical records, patches, logs, source/executable",
    "hashes, environment, confirmation and holdout summaries are under",
    "`results/optimization/round1`. `python tools/report_hillclimb.py` regenerates",
    "this report. Frozen integration and paper results were not overwritten.", "",
    "## Next climb", "",
    "Keep this as the new CPU baseline. State storage is still the main memory",
    "problem: 340 bytes per material is unchanged. The next separate research",
    "round should compare compact representations and full-precision accumulators",
    "under reconstruction, tint, grouping and tiny-update/reload gates. It must",
    "retain a full-state reference and not repeat the naive-f16 failure. Renderer",
    "transport, appearance and snapshot IO remain in the renderer workstream.", "",
]
(ROOT / "docs/optimization-round1.md").write_text("\n".join(report), encoding="utf-8")
(R / "decision.json").write_text(json.dumps(dict(selected=chosen,base_commit=screen["environment"]["base_commit"],
    exact_selection_records=exact_rows,exact_holdout_records=exact_rows,confirmation=results,
    reason="Exact numerical gate and repeatable gains in cached/full RGB and streamed workloads; no model/state/API change",
    caveats=["unchanged interpolation control slower in this sample","state size unchanged","one compiler/host measured"]),indent=2))
print(ROOT / "docs/optimization-round1.md")
