"""Round-two authoring/screening; uses only Rust-exported Ochrell synthetic states.

Run with the NumPy environment documented in docs/optimization-round2-plan.md.
Runtime library changes are separate and must pass a Rust verification stage.
"""

import os

for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[key] = "1"
import argparse
import hashlib
import json
from pathlib import Path
import time
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / "results/optimization/round2"
DATA = ROOT / "target/compact"


def corpus(name):
    p = DATA / name
    return (
        np.fromfile(p / "colors.f32", dtype="<f4").reshape(-1, 3),
        np.fromfile(p / "fast.f32", dtype="<f4").reshape(-1, 85),
        np.fromfile(p / "reference.f64", dtype="<f8").reshape(-1, 165),
    )


def raw(z, weights):
    n = len(weights)
    k = z[..., :n]
    s = z[..., n : 2 * n]
    q = k / s
    refl = 1 / (1 + q + np.sqrt(q * (q + 2)))
    # Preserve Rust's order, not BLAS's unordered dot-product reduction.
    out = np.zeros(z.shape[:-1] + (3,), dtype=weights.dtype)
    for i in range(n):
        out += refl[..., i, None] * weights[i]
    return out.astype(np.float64)


def linear(z, weights):
    return raw(z, weights) + z[..., -3:].astype(np.float64)


def gamut(x):
    y = np.clip(x @ np.array([0.2126, 0.7152, 0.0722]), 0, 1)
    d = x - y[..., None]
    a = np.ones_like(y)
    for i in range(3):
        ratio = np.ones_like(y)
        np.divide(1 - y, d[..., i], out=ratio, where=d[..., i] > 0)
        np.divide(-y, d[..., i], out=ratio, where=d[..., i] < 0)
        a = np.minimum(a, ratio)
    return np.clip(y[..., None] + a[..., None] * d, 0, 1)


def rgb(z, weights):
    x = gamut(linear(z, weights))
    return np.where(x <= 0.0031308, 12.92 * x, 1.055 * x ** (1 / 2.4) - 0.055).astype(
        np.float32
    )


def lab(c):
    c = c.astype(np.float64)
    x = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    lms = (
        x
        @ np.array(
            [
                [0.4122214708, 0.5363325363, 0.0514459929],
                [0.2119034982, 0.6806995451, 0.1073969566],
                [0.0883024619, 0.2817188376, 0.6299787005],
            ]
        ).T
    )
    return (
        np.cbrt(lms)
        @ np.array(
            [
                [0.2104542553, 0.793617785, -0.0040720468],
                [1.9779984951, -2.428592205, 0.4505937099],
                [0.0259040371, 0.7827717662, -0.808675766],
            ]
        ).T
        * 100
    )


def error(a, b):
    return np.linalg.norm(lab(a) - lab(b), axis=-1)


def stats(x):
    return dict(
        mean=float(np.mean(x)), p95=float(np.percentile(x, 95)), max=float(np.max(x))
    )


class Knots:
    def __init__(self, indices, weights, name=None):
        self.indices = np.array(sorted(indices), dtype=int)
        self.weights = weights
        self.n = len(indices)
        self.name = name or f"knots{self.n}"
        self.bytes = (2 * self.n + 3) * 4
        self.bad = 0
        self.matrix = np.array(
            [
                np.interp(np.arange(41), self.indices, np.eye(self.n)[j])
                for j in range(self.n)
            ],
            np.float32,
        )

    def expand(self, c):
        return np.concatenate(
            [
                c[..., : self.n] @ self.matrix,
                c[..., self.n : 2 * self.n] @ self.matrix,
                c[..., -3:],
            ],
            axis=-1,
        )

    def pack(self, z, correct=True):
        c = np.concatenate(
            [z[..., self.indices], z[..., 41 + self.indices], z[..., -3:]], axis=-1
        )
        if correct:
            c[..., -3:] = (
                linear(z, self.weights) - raw(self.expand(c), self.weights)
            ).astype(np.float32)
        return c


class Basis:
    def __init__(self, mean, scale, basis, weights):
        self.mean = mean.astype(np.float32)
        self.scale = scale.astype(np.float32)
        self.basis = basis.astype(np.float32)
        self.weights = weights
        self.name = f"pca{len(basis)}"
        self.bytes = (len(basis) + 3) * 4
        self.bad = 0

    def expand(self, c):
        opt = (c[..., :-3] @ self.basis) * self.scale + self.mean
        self.bad += int(
            np.count_nonzero(
                np.any(opt[..., :41] < 0, axis=-1) | np.any(opt[..., 41:] <= 0, axis=-1)
            )
        )
        # Measured failure control only; any required clipping fails acceptance.
        opt[..., :41] = np.maximum(opt[..., :41], 0)
        opt[..., 41:] = np.maximum(opt[..., 41:], 1e-10)
        return np.concatenate([opt, c[..., -3:]], axis=-1)

    def pack(self, z, correct=True):
        co = ((z[..., :82] - self.mean) / self.scale) @ self.basis.T
        c = np.concatenate([co, z[..., -3:]], axis=-1).astype(np.float32)
        if correct:
            c[..., -3:] = (
                linear(z, self.weights) - raw(self.expand(c), self.weights)
            ).astype(np.float32)
        return c


def adaptive_indices(train, weights):
    # Fit only optical shape. Positive nonuniform interpolation with endpoints.
    # Weight errors by colorimetric importance, emphasize low-S regions.
    v = train[:, :82].astype(np.float64)
    importance = np.sum(np.abs(weights), axis=1) + 1e-5
    norm = np.maximum(np.mean(v, axis=0), 0.02)
    selected = [0, 40]
    sequence = [0, 40]
    while len(selected) < 31:
        best = None
        for j in range(1, 40):
            if j in selected:
                continue
            k = Knots(sorted(selected + [j]), weights)
            approx = k.expand(k.pack(train, correct=False))[..., :82].astype(np.float64)
            errors = (approx - v) / norm
            loss = float(np.mean(errors * errors * np.tile(importance, 2)))
            if best is None or loss < best[0]:
                best = (loss, j)
        selected.append(best[1])
        sequence.append(best[1])
    return sequence


def evaluate(model, colors, z, reference, weights, rweights, full=False):
    model.bad = 0
    n = len(z)
    ind = np.arange(n)
    j = (ind * 73 + 19) % n
    k = (ind * 101 + 11) % n
    a = model.pack(z)
    b = model.pack(z[j])
    c = model.pack(z[k])
    cases = {}
    raw_records = {}
    white = np.broadcast_to(z[-1], z.shape)
    black = np.broadcast_to(z[-256], z.shape)
    rw = np.broadcast_to(reference[-1], reference.shape)
    rb = np.broadcast_to(reference[-256], reference.shape)
    cw = model.pack(white)
    cb = model.pack(black)
    t = ((ind % 997 + 1) / 999).astype(np.float32)[:, None]

    def put(name, packed, target, ref=None):
        expanded = model.expand(packed)
        value = rgb(expanded, weights)
        de = error(value, rgb(target, weights))
        cases[name] = dict(vs_full=stats(de))
        raw_records[name] = de
        if ref is not None:
            cases[name]["vs_reference"] = stats(error(value, rgb(ref, rweights)))

    put("reconstruction", a, z, reference)
    pair = (1 - t) * a + t * b
    zp = (1 - t) * z + t * z[j]
    rp = (1 - t) * reference + t * reference[j]
    put("mixture", pair, zp, rp)
    put("white", 0.3 * pair + 0.7 * cw, 0.3 * zp + 0.7 * white, 0.3 * rp + 0.7 * rw)
    put("black", 0.9 * pair + 0.1 * cb, 0.9 * zp + 0.1 * black, 0.9 * rp + 0.1 * rb)
    # Explicit canonical trajectories, not just random pair selection at corners.
    corners = np.arange(n - 264, n - 256)
    pairs = [(3, 4), (1, 4), (2, 1), (4, 7), (1, 7), (0, 7), (5, 6)]
    ca = []
    cz = []
    cr = []
    ramp = np.linspace(0, 1, 1001, dtype=np.float32)[:, None]
    for u, v in pairs:
        ai, bi = corners[u], corners[v]
        ca.append((1 - ramp) * a[ai] + ramp * a[bi])
        cz.append((1 - ramp) * z[ai] + ramp * z[bi])
        cr.append((1 - ramp) * reference[ai] + ramp * reference[bi])
    put(
        "canonical_trajectories",
        np.concatenate(ca),
        np.concatenate(cz),
        np.concatenate(cr),
    )
    grouped = ((2 * a + 3 * b) / 5 * 5 + 5 * c) / 10
    direct = (2 * a + 3 * b + 5 * c) / 10
    put(
        "weighted",
        grouped,
        (2 * z + 3 * z[j] + 5 * z[k]) / 10,
        (2 * reference + 3 * reference[j] + 5 * reference[k]) / 10,
    )
    gd = error(rgb(model.expand(grouped), weights), rgb(model.expand(direct), weights))
    cases["grouping_self"] = dict(vs_full=stats(gd))
    raw_records["grouping_self"] = gd
    idx = np.r_[
        np.arange(32 if not full else 128),
        np.arange(n - 264, n - 256),
        np.arange(n - 256, n, 32),
    ]
    # Include ordinary, dark, saturated, corner and gray controls in long chains.
    a0 = a[idx]
    b0 = b[idx]
    z0 = z[idx]
    z1 = z[j[idx]]
    r0 = reference[idx]
    r1 = reference[j[idx]]
    for steps, frac, label in [(256, 0.03, "repeated256"), (4096, 0.0001, "tiny4096")]:
        accum = a0.copy()
        repack = a0.copy()
        target = z0.copy()
        ref = r0.copy()
        for step in range(steps):
            accum = (np.float32(1) - np.float32(frac)) * accum + np.float32(frac) * b0
            updated = (np.float32(1) - np.float32(frac)) * repack + np.float32(
                frac
            ) * b0
            repack = model.pack(model.expand(updated))
            target = (np.float32(1) - np.float32(frac)) * target + np.float32(frac) * z1
            ref = (1 - frac) * ref + frac * r1
        put(label, accum, target, ref)
        put(label + "_repack", repack, target, ref)
        put(
            label + "_then_white",
            0.5 * accum + 0.5 * cw[idx],
            0.5 * target + 0.5 * white[idx],
            0.5 * ref + 0.5 * rw[idx],
        )
    # Pure repeated expansion/repacking must not destroy existing material.
    re = a0.copy()
    for _ in range(512):
        re = model.pack(model.expand(re))
    put("reload512", re, z0, r0)
    bad = model.bad
    accepted = model.bytes <= 256 and bad == 0
    for name, case in cases.items():
        v = case["vs_full"]
        if name in ("reconstruction", "grouping_self"):
            passed = v["max"] <= 0.002
        else:
            passed = v["mean"] <= 0.01 and v["p95"] <= 0.05 and v["max"] <= 0.2
        case["pass"] = bool(passed)
        accepted = accepted and passed
    return dict(
        bytes=model.bytes,
        invalid_reconstructions=bad,
        accepted=bool(accepted),
        cases=cases,
    ), raw_records


def main():
    global R, DATA
    p = argparse.ArgumentParser()
    p.add_argument("--holdout", action="store_true")
    p.add_argument("--only", default=None)
    p.add_argument("--out", type=Path, default=ROOT / "target/compact-screen")
    p.add_argument("--data", type=Path, default=DATA)
    args = p.parse_args()
    R = args.out.resolve()
    DATA = args.data.resolve()
    R.mkdir(parents=True, exist_ok=True)
    weights = np.fromfile(DATA / "train/fast_rgb.f32", dtype="<f4").reshape(41, 3)
    rweights = np.fromfile(DATA / "train/reference_rgb.f64", dtype="<f8").reshape(81, 3)
    _, train, _ = corpus("train")
    provenance = dict(
        training_sha256=hashlib.sha256(
            (DATA / "train/fast.f32").read_bytes()
        ).hexdigest(),
        quadrature_sha256=hashlib.sha256(
            (DATA / "train/fast_rgb.f32").read_bytes()
        ).hexdigest(),
        core_generated_sha256=hashlib.sha256(
            (ROOT / "src/optical_generated.rs").read_bytes()
        ).hexdigest(),
    )
    if (R / "fitting.npz").exists():
        if json.loads((R / "fitting-provenance.json").read_text()) != provenance:
            raise ValueError(
                "Fitted data no longer match the corpus/model. Use a fresh --out directory."
            )
    else:
        print("Fitting optical-only knot order and scaled PCA", flush=True)
        order = adaptive_indices(train, weights)
        v = train[:, :82].astype(np.float64)
        mean = v.mean(axis=0)
        scale = np.maximum(v.std(axis=0), 1e-5)
        _, singular, basis = np.linalg.svd((v - mean) / scale, full_matrices=False)
        for row in basis:
            if row[np.argmax(np.abs(row))] < 0:
                row *= -1
        np.savez(
            R / "fitting.npz",
            order=order,
            mean=mean,
            scale=scale,
            basis=basis,
            singular=singular,
        )
        (R / "fitting-provenance.json").write_text(json.dumps(provenance, indent=2))
    fit = np.load(R / "fitting.npz")
    models = []
    for n in (11, 16, 21, 22, 23, 24, 26, 28, 30, 31):
        models.append(
            Knots(np.round(np.linspace(0, 40, n)).astype(int), weights, f"uniform{n}")
        )
        models.append(Knots(fit["order"][:n], weights, f"adaptive{n}"))
    for n in (8, 12, 16, 24, 32):
        models.append(Basis(fit["mean"], fit["scale"], fit["basis"][:n], weights))
    models.append(Knots(np.arange(41), weights, "full41_control"))
    if args.only:
        models = [m for m in models if m.name in args.only.split(",")]
    colors, z, ref = corpus("holdout" if args.holdout else "selection")
    stage = "holdout" if args.holdout else "screening"
    path = R / f"{stage}.json"
    summary = json.loads(path.read_text()) if path.exists() else {}
    for model in models:
        started = time.perf_counter()
        s, records = evaluate(
            model, colors, z, ref, weights, rweights, full=args.holdout
        )
        s["seconds"] = time.perf_counter() - started
        if isinstance(model, Knots):
            s["indices"] = model.indices.tolist()
        summary[model.name] = s
        np.savez_compressed(R / f"{stage}-{model.name}-errors.npz", **records)
        (R / f"{stage}.json").write_text(json.dumps(summary, indent=2))
        worst = max(v["vs_full"]["max"] for v in s["cases"].values())
        print(
            model.name,
            "bytes",
            model.bytes,
            "accepted",
            s["accepted"],
            "worst",
            round(worst, 5),
            "invalid",
            model.bad,
            "seconds",
            round(s["seconds"], 1),
            flush=True,
        )
    env = dict(
        numpy=np.__version__,
        metric="delta E OKLab * 100",
        core_base="9937ec4",
        threads=1,
        training_seed=20260930,
        selection_seed=314159,
        holdout_seed=1907,
        core_generated_sha256=hashlib.sha256(
            (ROOT / "src/optical_generated.rs").read_bytes()
        ).hexdigest(),
    )
    (R / "environment.json").write_text(json.dumps(env, indent=2))


if __name__ == "__main__":
    main()
