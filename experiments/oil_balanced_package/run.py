"""Final all-data fit and native package for the already evaluated balancing rule."""
import os
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
import argparse
import importlib.util
import json
from pathlib import Path
import struct
import time
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location('balanced_candidate', ROOT/'experiments/oil_balanced_calibration/run.py')
balanced = importlib.util.module_from_spec(spec)
spec.loader.exec_module(balanced)
method = balanced.method
from generate_window_projection import projection
DEFAULT = ROOT/'target/measured-oils/balanced-eight'


def inputs():
    c, r, study, _ = balanced.inputs()
    prior = json.loads((balanced.HERE/'partition.json').read_text(encoding='utf-8'))
    assert study == prior
    assessment = json.loads((balanced.HERE/'summary.json').read_text(encoding='utf-8'))
    assert assessment['bundle_sha256'] == method.old.sha((balanced.DEFAULT/'frozen-models.json').read_bytes())
    w, counts = balanced.weights(c)
    files = [HERE/'PLAN.md', Path(__file__), balanced.HERE/'partition.json', balanced.HERE/'summary.json',
        balanced.HERE/'verification.json', balanced.HERE/'score-audit.json', ROOT/'tools/generate_window_projection.py']
    frozen_hashes = {}
    for previous in (study, study['reference_manifest'], study['reference_manifest']['original_manifest']):
        for name, digest in previous['hashes'].items():
            assert method.old.sha((ROOT/name).read_bytes()) == digest, name
            frozen_hashes[name] = digest
    manifest = {'source_sha256': method.old.HASHES, 'settings': study['settings'],
        'status': 'final all-286 calibration; predictive evidence remains the prior family-exclusion study',
        'hashes': {**frozen_hashes, **{p.relative_to(ROOT).as_posix(): method.old.sha(p.read_bytes()) for p in files}},
        'fit_rows': list(range(1, 287)), 'category_counts': counts,
        'category_row_weights': {name: 278/(4*count) for name, count in counts.items()},
        'total_row_weight': float(w.sum()), 'prior_assessment_bundle_sha256': assessment['bundle_sha256']}
    return c, r, manifest


def probes(c):
    recipes = [*c, *np.eye(8)]
    for i in range(8):
        for j in range(i+1, 8):
            for t in np.r_[np.linspace(0, 1, 33), 1e-12, 1e-8, 1e-4, 1-1e-4, 1-1e-8, 1-1e-12]:
                x = np.zeros(8)
                x[i], x[j] = 1-t, t
                recipes.append(x)
    recipes.extend(np.random.default_rng(8102026).dirichlet(np.ones(8), 1024))
    recipes.append(np.ones(8)/8)
    return np.array(recipes)


def export_package(model, corrected, provenance):
    kind = 'empirical' if corrected else 'km'
    out = bytearray(b'OPP3')
    out.extend(struct.pack('<6I', 8, 31, 400, 10, 1, int(corrected)))
    for value in [f'ochrell-old-holland-eight-balanced-{kind}-v1', provenance, *method.NAMES]:
        raw = value.encode('utf-8')
        out.extend(struct.pack('<I', len(raw)))
        out.extend(raw)
    for matrix in [np.array(model['base']['K']).T, np.array(model['base']['S']).T, projection()]:
        out.extend(np.asarray(matrix, dtype='<f8').tobytes())
    controls = np.array(model['theta']).reshape(28, 4) if corrected else np.empty((0, 4))
    out.extend(struct.pack('<I', len(controls)))
    out.extend(controls.astype('<f8').tobytes())
    out.extend(bytes.fromhex(method.old.sha(out)))
    return bytes(out)


def verify_model(c, r, model, manifest):
    repeated = balanced.fit(c.copy(), r.copy(), manifest['settings'])
    diff = balanced.previous.coefficient_difference(model, repeated)
    assert max(diff.values()) == 0
    recipes = probes(c)
    pure = (c > 0).sum(1) == 1
    _, _, lab = method.old.colorimetry()
    checks, diagnostics = {}, {}
    for name, corrected in [('km', False), ('empirical', True)]:
        prediction = method.predict(recipes, model, corrected)
        scalar = np.array([method.scalar(x, model, corrected) for x in recipes])
        delta = float(abs(prediction-scalar).max())
        endpoint = float(abs(method.predict(c[pure], model, corrected)-r[pure]).max())
        assert delta < 1e-12 and endpoint < 1e-12
        assert np.isfinite(prediction).all() and (prediction > 0).all() and (prediction < 1).all()
        checks[name] = {'scalar_max_abs': delta, 'pure_max_abs': endpoint,
            'min_reflectance': float(prediction.min()), 'max_reflectance': float(prediction.max())}
        metrics = method.old.errors(r, prediction[:286], lab)
        diagnostics[name] = method.old.summarize(metrics, np.ones(286, dtype=bool))
    return {'exact_refit_coefficients_max_abs': diff, 'recipes': len(recipes), 'checks': checks,
        'calibration_diagnostics_NOT_validation': diagnostics,
        'base_runs': model['base']['runs'], 'correction': model['optimizer']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=['fit', 'export', 'verify-runtime'])
    parser.add_argument('--out', type=Path, default=DEFAULT)
    args = parser.parse_args()
    out = method.old.research_directory(args.out)
    c, r, manifest = inputs()
    path = out/'frozen-model.json'
    if args.phase == 'fit':
        assert not path.exists(), 'Refusing to replace frozen final model'
        start = time.perf_counter()
        model = balanced.fit(c.copy(), r.copy(), manifest['settings'])
        elapsed = time.perf_counter()-start
        method.old.write_json(path, {'manifest': manifest, 'model': model})
        checks = verify_model(c, r, model, manifest)
        checks.update({'fit_sha256': method.old.sha(path.read_bytes()), 'fit_wall_seconds': elapsed,
            'manifest': manifest, 'verification': 'full-data repeat/scalar checks; no held-out rows in this final fit'})
        for dest in (out, HERE):
            method.old.write_json(dest/'fit-verification.json', checks)
        print(json.dumps({'fit_sha256': checks['fit_sha256'], 'fit_seconds': elapsed, 'recipes': checks['recipes'], 'checks': checks['checks']}, indent=2))
        return
    raw = path.read_bytes()
    artifact = json.loads(raw)
    assert artifact['manifest'] == manifest
    verification = json.loads((out/'fit-verification.json').read_text(encoding='utf-8'))
    assert verification['fit_sha256'] == method.old.sha(raw) and verification['manifest'] == manifest
    model = artifact['model']
    recipes = probes(c)
    if args.phase == 'export':
        provenance = json.dumps({'source': 'Asadi Shahmirzadi et al. 2020 Old Holland oil dataset',
            'source_sha256': method.old.HASHES['archive'], 'fit_sha256': method.old.sha(raw),
            'calibration_samples': 286, 'calibration': 'equal total weight across four nonpure recipe categories',
            'accuracy_evidence': 'prior 107-family exclusion study; final-fit residuals are training diagnostics',
            'amounts': 'normalized tube-paint mass portions',
            'status': 'Experimental local measured-palette candidate; not independently validated',
            'display': '400-700 nm windowed D65 preview; no extrapolated spectral tails'}, separators=(',', ':'))
        packages = {}
        for name, corrected in [('km', False), ('empirical', True)]:
            file = out/f'old-holland-eight-balanced-{name}.opp'
            data = export_package(model, corrected, provenance)
            if file.exists():
                assert file.read_bytes() == data
            else:
                file.write_bytes(data)
            packages[name] = {'file': file.name, 'bytes': len(data), 'sha256': method.old.sha(data), 'identity': data[-32:].hex()}
        (out/'recipes.f64').write_bytes(recipes.astype('<f8').tobytes())
        info = {'fit_sha256': method.old.sha(raw), 'packages': packages, 'recipe_count': len(recipes),
            'recipes_sha256': method.old.sha((out/'recipes.f64').read_bytes())}
        method.old.write_json(out/'packages.json', info)
        print(json.dumps(info, indent=2))
        return
    packages = json.loads((out/'packages.json').read_text(encoding='utf-8'))
    assert packages['fit_sha256'] == method.old.sha(raw)
    assert (out/'recipes.f64').read_bytes() == recipes.astype('<f8').tobytes()
    checks = {}
    for name, corrected in [('km', False), ('empirical', True)]:
        assert method.old.sha((out/packages['packages'][name]['file']).read_bytes()) == packages['packages'][name]['sha256']
        actual = np.frombuffer((out/f'{name}-predictions.f64').read_bytes(), dtype='<f8').reshape(len(recipes), 34)
        expected = method.predict(recipes, model, corrected)
        checks[name] = {'spectral_max_abs': float(abs(actual[:, :31]-expected).max()),
            'linear_rgb_max_abs': float(abs(actual[:, 31:]-expected@np.asarray(projection())).max())}
        assert max(checks[name].values()) < 1e-12
    files = [ROOT/'src/palette.rs', ROOT/'src/palette_package.rs', ROOT/'src/palette_window.rs', ROOT/'examples/measured_palette_probe.rs']
    result = {'packages': packages, 'checks': checks, 'runtime_hashes': {p.relative_to(ROOT).as_posix(): method.old.sha(p.read_bytes()) for p in files}}
    for dest in (out, HERE):
        method.old.write_json(dest/'package-verification.json', result)
    print(json.dumps(checks, indent=2))


if __name__ == '__main__':
    main()
