"""Reproducible, core-only candidate experiment. Python standard library only.

Uses temporary, guarded edits of src/optical.rs; restores it before returning.
No renderer modifications. See docs/optimization-plan.md for acceptance rules.
"""
import argparse
import csv
import ctypes
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/optical.rs"
WORK = ROOT / "target/hillclimb"
OUTPUT = ROOT / "results/optimization/round1"


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError("candidate no longer matches baseline source")
    return text.replace(old, new, 1)


def inline(text, methods):
    for method in methods:
        needle = "            pub fn " + method + "("
        text = replace_once(text, needle, "            #[inline]\n" + needle)
    return text


def split_decode(text):
    old = """                for i in 0..$n {
                    let q = z.k[i] / z.s[i];
                    let r = 1. / (1. + q + (q * (q + 2.)).sqrt());
                    for ch in 0..3 {
                        x[ch] += r * $rgb[i][ch];
                    }
                }"""
    new = """                // Compute independent optics first; retain the original ordered
                // colorimetric reduction and all floating-point expressions.
                let reflectance: [$ty; $n] = std::array::from_fn(|i| {
                    let q = z.k[i] / z.s[i];
                    1. / (1. + q + (q * (q + 2.)).sqrt())
                });
                for i in 0..$n {
                    for ch in 0..3 {
                        x[ch] += reflectance[i] * $rgb[i][ch];
                    }
                }"""
    return replace_once(text, old, new)


def split_encode(text):
    old = """                    // KM inversion recovers r algebraically. Integrate r directly;
                    // f32 roundoff is checked against the full f64 reference.
                    for ch in 0..3 {
                        raw[ch] += r[i] * $rgb[i][ch];
                    }
                }"""
    new = """                }
                // Separate independent K/S inference from the ordered projection.
                // KM inversion recovers r algebraically; integrate r directly.
                for i in 0..$n {
                    for ch in 0..3 {
                        raw[ch] += r[i] * $rgb[i][ch];
                    }
                }"""
    return replace_once(text, old, new)


def algebraic_decode(text):
    return replace_once(text,
        """                    let q = z.k[i] / z.s[i];
                    let r = 1. / (1. + q + (q * (q + 2.)).sqrt());""",
        """                    let k = z.k[i];
                    let s = z.s[i];
                    let r = s / (k + s + (k * (k + 2. * s)).sqrt());""")


def variants(baseline):
    hot = ("interpolate", "encode", "decode_linear", "decode", "mix")
    both = split_encode(split_decode(baseline))
    return {
        "baseline": baseline,
        "inline_decode": inline(baseline, ("decode_linear", "decode")),
        "inline_hot": inline(baseline, hot),
        "split_decode": split_decode(baseline),
        "split_encode": split_encode(baseline),
        "split_both": both,
        "split_both_inline": inline(both, hot),
        "algebraic_decode": algebraic_decode(baseline),
    }


def pin_cpu(cpu):
    if cpu is None:
        return None
    if sys.platform == "win32":
        from ctypes import wintypes
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        k.GetCurrentProcess.restype = wintypes.HANDLE
        k.SetProcessAffinityMask.argtypes = [wintypes.HANDLE, ctypes.c_size_t]
        k.SetProcessAffinityMask.restype = wintypes.BOOL
        if not k.SetProcessAffinityMask(k.GetCurrentProcess(), 1 << cpu):
            raise ctypes.WinError(ctypes.get_last_error())
    elif hasattr(os, "sched_setaffinity"):
        os.sched_setaffinity(0, {cpu})
    else:
        raise RuntimeError("CPU affinity unsupported; omit --cpu")
    return cpu


def command(cmd, log=None):
    r = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    if log:
        log.write_text(r.stdout + r.stderr, encoding="utf-8")
    if r.returncode:
        raise RuntimeError(f"command failed ({r.returncode}): {cmd}\n{r.stderr[-2000:]}")
    return r.stdout


def read_rows(path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def compress(path):
    with path.open("rb") as f, gzip.open(str(path) + ".gz", "wb") as out:
        shutil.copyfileobj(f, out)
    path.unlink()  # Only the exact generated CSV, after its gzip was written.


def compare_quality(base, new):
    assert len(base) == len(new)
    result = {}
    for a, b in zip(base, new):
        assert (a["case"], a["sample"]) == (b["case"], b["sample"])
        r = result.setdefault(a["case"], dict(samples=0, changed_rgb=0, changed_state=0, max_reference_de_ok100=0.))
        r["samples"] += 1
        r["changed_rgb"] += any(a[k] != b[k] for k in ("r_bits", "g_bits", "b_bits"))
        r["changed_state"] += a["state_hash"] != b["state_hash"]
        r["max_reference_de_ok100"] = max(r["max_reference_de_ok100"], float(b["delta_e_ok100_reference"]))
    return dict(exact=all(v["changed_rgb"] == 0 and v["changed_state"] == 0 for v in result.values()), cases=result)


def timings(binary, dest, seed, iterations, repeats):
    command([str(binary), "bench", str(dest), str(seed), str(iterations), str(repeats)])
    rows = read_rows(dest)
    return {op: statistics.median(float(r["ns_per_operation"]) for r in rows if r["operation"] == op)
            for op in sorted({r["operation"] for r in rows})}


def main():
    global OUTPUT, WORK
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cpu", type=int, default=None)
    p.add_argument("--iterations", type=int, default=200000)
    p.add_argument("--repeats", type=int, default=7)
    p.add_argument("--candidates", default=None)
    p.add_argument("--baseline-ref", default="17531c6", help="Frozen baseline Git commit containing src/optical.rs")
    p.add_argument("--out", type=Path, default=OUTPUT, help="Evidence directory; use a new directory to preserve prior runs")
    action = p.add_mutually_exclusive_group()
    action.add_argument("--confirm", default=None, help="Use previously built binaries for alternating baseline/candidate confirmation")
    action.add_argument("--holdout", default=None, help="Compare a screened candidate with baseline on seed 1907")
    args = p.parse_args()
    default_output = OUTPUT.resolve()
    OUTPUT = args.out.resolve()
    if OUTPUT != default_output:
        # Reproduction runs must not replace the frozen round's executables.
        WORK = WORK / hashlib.sha256(str(OUTPUT).encode()).hexdigest()[:12]
    OUTPUT.mkdir(parents=True, exist_ok=True); WORK.mkdir(parents=True, exist_ok=True)
    cpu = pin_cpu(args.cpu)
    if args.confirm or args.holdout:
        chosen = args.confirm or args.holdout
        screening_path = OUTPUT / "screening.json"
        screening = json.loads(screening_path.read_text())
        for name in ("baseline", chosen):
            candidate = screening["candidates"][name]
            binary = WORK / (name + (".exe" if os.name == "nt" else ""))
            if not candidate["tests_pass"] or not candidate["quality"]["exact"]:
                raise ValueError("confirmation requires a candidate that passed the exact-quality gate")
            if hashlib.sha256(binary.read_bytes()).hexdigest() != candidate["binary_sha256"]:
                raise ValueError("candidate executable no longer matches recorded build")
        if args.holdout:
            rows = {}
            for name in ("baseline", chosen):
                binary = WORK / (name + (".exe" if os.name == "nt" else ""))
                path = OUTPUT / f"{name}-holdout.csv"
                command([str(binary), "quality", str(path), "1907"])
                rows[name] = read_rows(path)
                compress(path)
            quality = compare_quality(rows["baseline"], rows[chosen])
            (OUTPUT / "holdout.json").write_text(json.dumps(dict(seed=1907,candidate=chosen,quality=quality),indent=2))
            if not quality["exact"]:
                raise RuntimeError("holdout exact-output gate failed")
            print("Holdout matches baseline exactly")
            return
        summaries = []
        # ABBA then BAAB, two independent order-balanced blocks.
        for i, label in enumerate(["baseline", args.confirm, args.confirm, "baseline", args.confirm, "baseline", "baseline", args.confirm]):
            print(f"Confirm {i+1}/8: {label}", flush=True)
            binary = WORK / (label + (".exe" if os.name == "nt" else ""))
            result = timings(binary, OUTPUT / f"confirm-{i}-{label}.csv", 1907, args.iterations, args.repeats)
            summaries.append(dict(block=i, candidate=label, medians_ns=result))
        (OUTPUT / "confirmation.json").write_text(json.dumps(dict(cpu=cpu,iterations=args.iterations,repeats=args.repeats,
            screening_sha256=hashlib.sha256(screening_path.read_bytes()).hexdigest(),runs=summaries),indent=2))
        return
    original = SOURCE.read_bytes()
    baseline = command(["git", "show", f"{args.baseline_ref}:src/optical.rs"])
    candidates = variants(baseline)
    names = args.candidates.split(",") if args.candidates else list(candidates)
    if names[0] != "baseline":
        raise ValueError("screening must start with baseline")
    env = dict(seed=20260930, holdout_seed=1907, cpu_affinity=cpu, iterations=args.iterations, repeats=args.repeats,
        rustc=command(["rustc", "-Vv"]), platform=platform.platform(), python=sys.version,
        base_commit=command(["git", "rev-parse", args.baseline_ref]).strip(),
        working_tree_head=command(["git", "rev-parse", "HEAD"]).strip(),
        profile="release opt-level=3, lto=false, codegen-units=1; no explicit SIMD/fast-math; same flags for all candidates",
        probe_sha256=hashlib.sha256((ROOT/"examples/hillclimb.rs").read_bytes()).hexdigest(),
        original_source_sha256=hashlib.sha256(baseline.encode("utf-8")).hexdigest(),
        restored_source_sha256=hashlib.sha256(original).hexdigest())
    results = {}; base_rows = None; owned = original
    try:
        for name in names:
            if SOURCE.read_bytes() != owned:
                raise RuntimeError("optical.rs changed externally; refusing to overwrite it")
            owned = candidates[name].encode("utf-8")
            SOURCE.write_bytes(owned)
            patch = command(["git", "diff", "--", "src/optical.rs"])
            (OUTPUT / f"{name}.patch").write_text(patch, encoding="utf-8")
            print(f"Build/test {name}", flush=True)
            command(["cargo", "build", "--release", "--offline", "--example", "hillclimb"], OUTPUT / f"{name}-build.txt")
            binary = WORK / (name + (".exe" if os.name == "nt" else ""))
            shutil.copy2(ROOT / "target/release/examples" / ("hillclimb.exe" if os.name == "nt" else "hillclimb"), binary)
            tests = subprocess.run(["cargo","test","--release","--offline"],cwd=ROOT,text=True,capture_output=True)
            (OUTPUT / f"{name}-tests.txt").write_text(tests.stdout+tests.stderr,encoding="utf-8")
            q = OUTPUT / f"{name}-quality.csv"
            command([str(binary), "quality", str(q), str(env["seed"])])
            qr = read_rows(q)
            if base_rows is None: base_rows = qr
            quality = compare_quality(base_rows, qr)
            compress(q)
            timing = timings(binary, OUTPUT / f"{name}-timing.csv", env["seed"], args.iterations, args.repeats)
            results[name] = dict(tests_pass=tests.returncode == 0, quality=quality, medians_ns=timing,
                source_sha256=hashlib.sha256(owned).hexdigest(), binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest())
            (OUTPUT / "screening.json").write_text(json.dumps(dict(environment=env,candidates=results),indent=2))
            print(f"{name}: tests={tests.returncode == 0}, exact={quality['exact']}, ns={timing}", flush=True)
    finally:
        if SOURCE.read_bytes() == owned:
            SOURCE.write_bytes(original)
        else:
            print("External edit detected: original file NOT restored over it",file=sys.stderr)


if __name__ == "__main__": main()
