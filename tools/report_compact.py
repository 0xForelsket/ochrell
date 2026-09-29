"""Verify the frozen compact format in Rust; retain raw data, timings and a figure.

Run with requirements-compact.txt. Default outputs go into target, never over
the checked-in evidence. --run builds/executes Rust; otherwise render saved data.
This script does not edit library sources or fit/select a new representation.
"""

import argparse
from collections import defaultdict
import csv
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

import numpy as np

from hillclimb import pin_cpu

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(args):
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"{args}\n{result.stdout}\n{result.stderr}")
    return result.stdout


def read_csv(path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", newline="") as stream:
        return list(csv.DictReader(stream))


def stats(values):
    return dict(
        count=len(values),
        mean=float(np.mean(values)),
        p95=float(np.percentile(values, 95)),
        max=float(np.max(values)),
    )


def quality(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row["case"]].append(row)
    summary = {}
    for name, group in groups.items():
        full = stats([float(r["delta_ok100_full"]) for r in group])
        reference = stats([float(r["delta_ok100_reference"]) for r in group])
        if name in ("reconstruction", "grouping_self"):
            passed = full["max"] <= 0.002
        else:
            passed = full["mean"] <= 0.01 and full["p95"] <= 0.05 and full["max"] <= 0.2
        summary[name] = dict(vs_full=full, vs_reference=reference, passed=passed)
    expected = {
        "reconstruction",
        "mixture",
        "white",
        "black",
        "weighted",
        "grouping_self",
        "canonical_trajectories",
        "repeated256",
        "repeated256_repack",
        "repeated256_then_white",
        "tiny4096",
        "tiny4096_repack",
        "tiny4096_then_white",
        "reload512",
    }
    if set(groups) != expected:
        raise ValueError("Missing/unexpected numerical cases")
    return summary


def timings(paths):
    groups = defaultdict(list)
    for path in paths:
        for row in read_csv(path):
            groups[row["operation"]].append(float(row["ns_per_operation"]))
    return {
        name: dict(
            samples=len(v), median_ns=float(np.median(v)), min_ns=min(v), max_ns=max(v)
        )
        for name, v in groups.items()
    }


def figure(rows, out):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ramps = sorted(
        (r for r in rows if r["case"] == "canonical_trajectories"),
        key=lambda r: int(r["sample"]),
    )
    names = [
        "Yellow + blue",
        "Red + blue",
        "Green + red",
        "Blue + white",
        "Red + white",
        "Black + white",
        "Magenta + cyan",
    ]
    fig, axes = plt.subplots(
        7, 2, figsize=(11, 10), gridspec_kw={"width_ratios": [2.3, 1]}
    )
    for i, name in enumerate(names):
        group = ramps[i * 1001 : (i + 1) * 1001]
        full = np.array([[float(r[f"full_{c}"]) for c in "rgb"] for r in group])
        compact = np.array([[float(r[c]) for c in "rgb"] for r in group])
        errors = np.array([float(r["delta_ok100_full"]) for r in group])
        ax, err = axes[i]
        ax.imshow(np.stack([full, compact]), aspect="auto", extent=[0, 1, 1.5, -0.5])
        ax.set_yticks([0, 1], ["Full", "Compact"])
        ax.set_title(name, loc="left", fontsize=11)
        ax.set_xticks([0, 0.5, 1])
        err.plot(np.linspace(0, 1, 1001), errors, color="#8c561b", linewidth=1.4)
        err.set_ylim(0, 0.032)
        err.set_xticks([0, 0.5, 1])
        err.set_yticks([0, 0.015, 0.030])
        err.grid(alpha=0.2)
        err.set_title(f"Max difference {errors.max():.5f}", loc="left", fontsize=10)
    axes[-1, 0].set_xlabel("Amount fraction of second color")
    axes[-1, 1].set_xlabel("Amount fraction of second color")
    fig.suptitle(
        "Ochrell full 340 B vs compact 204 B\nIdentical material amounts; error is ΔE OKLab ×100",
        fontsize=14,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(out, dpi=160)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--cpu", type=int)
    parser.add_argument(
        "--out", type=Path, default=ROOT / "target/compact-verification"
    )
    parser.add_argument("--data", type=Path, default=ROOT / "target/compact")
    parser.add_argument("--iterations", type=int, default=1000000)
    parser.add_argument("--repeats", type=int, default=9)
    args = parser.parse_args()
    out, data = args.out.resolve(), args.data.resolve()
    out.mkdir(parents=True, exist_ok=True)
    if args.run:
        pin_cpu(args.cpu)
        cargo = os.environ.get("CARGO", "cargo")
        command(
            [
                cargo,
                "build",
                "--release",
                "--offline",
                "--example",
                "compact_corpus",
                "--example",
                "compact_eval",
            ]
        )
        suffix = ".exe" if os.name == "nt" else ""
        corpus = ROOT / f"target/release/examples/compact_corpus{suffix}"
        evaluate = ROOT / f"target/release/examples/compact_eval{suffix}"
        for name, seed, count in [
            ("train", 20260930, 8192),
            ("selection", 314159, 2048),
            ("holdout", 1907, 8192),
        ]:
            command([str(corpus), str(data / name), str(seed), str(count)])
        command(
            [
                str(evaluate),
                "quality",
                str(data / "holdout"),
                str(out / "rust-quality.csv"),
            ]
        )
        for run in range(2):
            command(
                [
                    str(evaluate),
                    "bench",
                    str(data / "selection"),
                    str(out / f"benchmark-run{run}.csv"),
                    str(args.iterations),
                    str(args.repeats),
                ]
            )
        csv_path = out / "rust-quality.csv"
        # Compress only the artifact just produced, with deterministic gzip time.
        (out / "rust-quality.csv.gz").write_bytes(
            gzip.compress(csv_path.read_bytes(), mtime=0)
        )
        csv_path.unlink()
        conditions = dict(
            platform=platform.platform(),
            processor=platform.processor(),
            python=sys.version,
            numpy=np.__version__,
            cpu_affinity=args.cpu,
            rustc=command(["rustc", "-Vv"]),
            iterations=args.iterations,
            repeats=args.repeats,
            runs=2,
            warmups_per_run=1,
            stream_states=262144,
            rustflags=os.environ.get("RUSTFLAGS", ""),
            core_base="9937ec4",
            metric="delta E OKLab * 100",
        )
        if os.name == "nt":
            conditions["cpu_name"] = command(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "(Get-CimInstance Win32_Processor).Name",
                ]
            ).strip()
        sources = [
            "src/compact.rs",
            "src/optical.rs",
            "src/optical_generated.rs",
            "examples/compact_eval.rs",
            "examples/compact_corpus.rs",
            "Cargo.toml",
        ]
        conditions["source_sha256"] = {p: sha(ROOT / p) for p in sources}
        conditions["executable_sha256"] = sha(evaluate)
        conditions["corpus_sha256"] = {
            str(p.relative_to(data)): sha(p)
            for p in sorted(data.glob("*/*"))
            if p.is_file()
        }
        conditions["packages"] = {
            p.name: p.version
            for p in __import__(
                "importlib.metadata", fromlist=["distributions"]
            ).distributions()
        }
        (out / "rust-environment.json").write_text(
            json.dumps(conditions, indent=2), encoding="utf-8"
        )
    rows = read_csv(out / "rust-quality.csv.gz")
    numerical = quality(rows)
    benchmark = timings(sorted(out.glob("benchmark-run*.csv")))
    passed = all(v["passed"] for v in numerical.values())
    summary = dict(
        accepted=passed,
        rows=len(rows),
        quality=numerical,
        timings=benchmark,
        memory={
            f"{width}x{height}": {
                "full_MiB": width * height * 340 / 2**20,
                "compact_MiB": width * height * 204 / 2**20,
            }
            for width, height in [
                (1024, 1024),
                (2048, 2048),
                (3840, 2160),
                (4096, 4096),
            ]
        },
    )
    (out / "rust-summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    figure(rows, out / "canonical-comparison.png")
    print(f"Rust verification: {len(rows)} rows, accepted={passed}")
    for name, result in benchmark.items():
        print(
            f"{name}: {result['median_ns']:.2f} ns [{result['min_ns']:.2f}, {result['max_ns']:.2f}]"
        )
    if not passed:
        raise SystemExit("Compact numerical budget failed")


if __name__ == "__main__":
    main()
