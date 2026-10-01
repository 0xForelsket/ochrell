"""One balanced-category calibration candidate on frozen recipe-family exclusions."""
import os
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import importlib.util
import json
from pathlib import Path
import time
import numpy as np
from scipy.optimize import least_squares

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location('previous_comparison', ROOT/'experiments/oil_multicolor_calibration/run.py')
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)
method = previous.method
DEFAULT = ROOT/'target/measured-oils/balanced-calibration'
REFERENCE_SHA = 'c80814e3a14e7379c399104a0fdcc4acee69f0e44e100b3c875c0cd01d3ee595'
CATEGORIES = ('chromatic_binary', 'white_tint', 'multicolor_no_white', 'multicolor_with_white')
MODEL_NAMES = previous.MODEL_NAMES + ('balanced_km', 'balanced_empirical')


def categories(c):
    c = np.asarray(c)
    assert c.ndim == 2 and c.shape[1] == 8
    assert np.isfinite(c).all() and (c >= 0).all() and (c.sum(1) > 0).all()
    chromatic = (c[:, :7] > 0).sum(1)
    white = c[:, 7] > 0
    result = np.full(len(c), -1, dtype=int)
    result[(chromatic == 2) & ~white] = 0
    result[(chromatic == 1) & white] = 1
    result[(chromatic >= 3) & ~white] = 2
    result[(chromatic >= 2) & white] = 3
    np.testing.assert_array_equal(result == -1, (c > 0).sum(1) == 1)
    return result


def weights(c):
    labels = categories(c)
    m = int((labels >= 0).sum())
    result = np.ones(len(c))
    counts = {}
    for g, name in enumerate(CATEGORIES):
        mask = labels == g
        count = int(mask.sum())
        if not count:
            raise ValueError(f'Missing training category: {name}')
        result[mask] = m / (4 * count)
        counts[name] = count
    np.testing.assert_allclose(result.sum(), len(c), rtol=0, atol=1e-10)
    return result, counts


def weighted_objective(objective, row_weights, bands):
    """Scale only original spectral residuals/Jacobian rows; leave priors intact."""
    fun, jac = objective
    scale = np.repeat(np.sqrt(row_weights), bands)
    count = len(scale)
    def residual(z):
        value = fun(z)
        value[:count] *= scale
        return value
    def jacobian(z):
        value = jac(z)
        value[:count] *= scale[:, None]
        return value
    return residual, jacobian


def fit(c, target, settings, row_weights=None):
    if row_weights is None:
        row_weights, _ = weights(c)
    row_weights = np.asarray(row_weights, dtype=float)
    assert row_weights.shape == (len(c),) and np.isfinite(row_weights).all() and (row_weights > 0).all()
    q = method.pure_q(c, target)
    n, bands = q.shape
    residual, jac = weighted_objective(method.base_objective(c, target, q, settings), row_weights, bands)
    runs, solutions = [], []
    for start in settings['initial_log_scattering']:
        now = time.perf_counter()
        sol = least_squares(residual, np.full((n-1)*bands, start), jac=jac, method='trf',
            bounds=settings['log_scattering_bounds'], max_nfev=settings['max_nfev'],
            ftol=settings['ftol'], xtol=settings['xtol'], gtol=settings['gtol'])
        runs.append({'initial_log_s': start, 'success': bool(sol.success), 'nfev': sol.nfev,
            'objective': float(sol.fun@sol.fun), 'optimality': float(sol.optimality),
            'bound_variables': int(np.count_nonzero(sol.active_mask)), 'elapsed_seconds': time.perf_counter()-now})
        solutions.append(sol)
    good = [i for i, run in enumerate(runs) if run['success']]
    if not good:
        raise RuntimeError(str(runs))
    selected = min(good, key=lambda i: (runs[i]['objective'], i))
    u = solutions[selected].x
    _, _, _, scattering, absorption = method.forward(c, q, u)
    base = {'q': q.tolist(), 'log_relative_s': u.reshape(n-1, bands).tolist(),
        'K': absorption.tolist(), 'S': scattering.tolist(), 'runs': runs, 'selected_start': selected}
    c, x = method.features(c)
    reflectance = method.forward(c, q, u)[0]
    active = np.max(abs(x), axis=(0, 1)) > 0
    residual, jac = weighted_objective(method.emp.objective(reflectance, x, target, active), row_weights, bands)
    now = time.perf_counter()
    sol = least_squares(residual, np.zeros(active.sum()), jac=jac, bounds=(-.8, .8),
        max_nfev=2000, ftol=1e-10, xtol=1e-10, gtol=1e-10)
    meta = {'success': bool(sol.success), 'nfev': sol.nfev, 'objective': float(sol.fun@sol.fun),
        'bound_variables': int(np.count_nonzero(sol.active_mask)), 'elapsed_seconds': time.perf_counter()-now}
    if not sol.success:
        raise RuntimeError(str(meta))
    theta = np.zeros(x.shape[2])
    theta[active] = sol.x
    return {'base': base, 'theta': theta.tolist(), 'active': active.tolist(), 'optimizer': meta}


def inputs():
    c, r, original = previous.inputs()
    assert json.loads((previous.DEFAULT/'partition.json').read_text(encoding='utf-8')) == original
    assert json.loads((previous.HERE/'partition.json').read_text(encoding='utf-8')) == original
    raw = (previous.DEFAULT/'frozen-models.json').read_bytes()
    assert method.old.sha(raw) == REFERENCE_SHA
    reference = json.loads(raw)
    assert reference['manifest_sha256'] == method.old.sha((previous.DEFAULT/'partition.json').read_bytes())
    for name, digest in original['hashes'].items():
        assert method.old.sha((ROOT/name).read_bytes()) == digest, name
    labels = categories(c)
    assert [int((labels == i).sum()) for i in (-1, 0, 1, 2, 3)] == [8, 50, 45, 56, 127]
    jobs, folds = {}, {}
    for key, fold in original['folds'].items():
        ref_id = fold['models']['expanded']
        model_id = ref_id.replace('expanded-', 'balanced-')
        rows = original['jobs'][ref_id]['train_rows']
        w, counts = weights(c[np.array(rows)-1])
        jobs[model_id] = {'train_rows': rows, 'category_counts': counts,
            'row_weights': w.tolist(), 'total_weight': float(w.sum())}
        folds[key] = {**fold, 'models': {**fold['models'], 'balanced': model_id}}
    files = [HERE/'PLAN.md', Path(__file__), HERE/'test_protocol.py',
        previous.HERE/'partition.json', previous.HERE/'summary.json', previous.HERE/'errors.csv',
        previous.HERE/'verification.json', previous.DEFAULT/'frozen-models.json']
    manifest = {'experiment': 'equal category weighting with preserved total data weight',
        'reference_manifest': original, 'hashes': {p.relative_to(ROOT).as_posix(): method.old.sha(p.read_bytes()) for p in files},
        'folds': folds, 'jobs': jobs, 'settings': original['original_manifest']['settings'],
        'primary_rows': original['primary_rows'], 'binary_assessment_rows': original['binary_assessment_rows'],
        'weight_rule': 'nonpure m/(4*n_g); pure 1; original residual denominator and all priors unchanged'}
    assert len(jobs) == 107
    return c, r, manifest, reference['results']


def preflight(c, r, manifest, reference):
    reproduced, records = previous.evaluate(c, r, manifest['reference_manifest'], reference)
    archived = json.loads((previous.HERE/'summary.json').read_text(encoding='utf-8'))
    for key in ('subsets', 'comparisons', 'equal_family_means', 'groups'):
        assert reproduced[key] == archived[key], key
    import csv
    with (previous.HERE/'errors.csv').open(encoding='utf-8', newline='') as stream:
        archived_rows = list(csv.DictReader(stream))
    assert len(records) == len(archived_rows) == 233
    for a, b in zip(records, archived_rows):
        for key in a:
            assert str(a[key]) == b[key], (a['source_row'], key)
    key = sorted(manifest['reference_manifest']['jobs'])[51]  # First expanded pool.
    assert key.startswith('expanded-')
    idx = np.array(manifest['reference_manifest']['jobs'][key]['train_rows'])-1
    candidate = fit(c[idx].copy(), r[idx].copy(), manifest['settings'], np.ones(len(idx)))
    diff = previous.coefficient_difference(candidate, reference[key]['model'])
    assert max(diff.values()) == 0
    return {'reference_statistics_and_rows_reproduced_exactly': True, 'uniform_weight_reference': key,
        'uniform_weight_coefficients_max_abs': diff, 'reference_bundle_sha256': REFERENCE_SHA}


def worker(key, c, r, job, settings, perturb):
    idx = np.array(job['train_rows'])-1
    try:
        if perturb:
            r = r.copy()
            excluded = np.ones(len(c), dtype=bool)
            excluded[idx] = False
            seed = int(method.old.sha(key.encode())[:8], 16)
            r[excluded] = np.random.default_rng(seed).uniform(.01, .99, r[excluded].shape)
        w, counts = weights(c[idx])
        np.testing.assert_array_equal(w, job['row_weights'])
        assert counts == job['category_counts']
        model = fit(c[idx].copy(), r[idx].copy(), settings)
        return key, {'status': 'success', 'model': model}
    except Exception as error:
        return key, {'status': 'failed', 'error_type': type(error).__name__, 'message': str(error)}


def fit_jobs(c, r, manifest, out, workers, perturb=False):
    checkpoint = out/('verification-refits' if perturb else 'fits')
    checkpoint.mkdir(exist_ok=True)
    identity = method.old.sha((out/'partition.json').read_bytes())
    results, pending = {}, {}
    for key, job in manifest['jobs'].items():
        path = checkpoint/f'{key}.json'
        if path.exists():
            saved = json.loads(path.read_text(encoding='utf-8'))
            assert saved['manifest_sha256'] == identity
            results[key] = saved['result']
        else:
            pending[key] = job
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(worker, key, c, r, job, manifest['settings'], perturb) for key, job in pending.items()]
        for future in as_completed(futures):
            key, result = future.result()
            results[key] = result
            method.old.write_json(checkpoint/f'{key}.json', {'manifest_sha256': identity, 'result': result})
            if len(results) % 10 == 0 or len(results) == len(manifest['jobs']) or result['status'] != 'success':
                print('verification refits' if perturb else 'fits', len(results), '/', len(manifest['jobs']), key, result['status'], flush=True)
    return dict(sorted(results.items()))


def verify(c, r, manifest, results, out, workers):
    assert all(item['status'] == 'success' for item in results.values())
    repeated = fit_jobs(c, r, manifest, out, workers, True)
    dense = np.vstack([np.random.default_rng(20261001).dirichlet(np.ones(8), 256), np.ones((1, 8))/8])
    pure = np.flatnonzero((c > 0).sum(1) == 1)
    checks = {'coefficient_max_abs': 0., 'scalar_max_abs': 0., 'pure_max_abs': 0., 'dense_min': 1., 'dense_max': 0.}
    details = {}
    for key, item in results.items():
        assert repeated[key]['status'] == 'success'
        model = item['model']
        diff = previous.coefficient_difference(model, repeated[key]['model'])
        assert max(diff.values()) == 0
        test_rows = sorted({row for fold in manifest['folds'].values() if fold['models']['balanced'] == key for row in fold['test_rows']})
        probes = np.vstack([c[np.array(sorted(set(test_rows)|set((pure+1).tolist())))-1], dense[:2], dense[-1:]])
        for corrected in (False, True):
            actual = method.predict(probes, model, corrected)
            expected = np.array([method.scalar(x, model, corrected) for x in probes])
            delta = float(abs(actual-expected).max())
            assert delta < 1e-12
            checks['scalar_max_abs'] = max(checks['scalar_max_abs'], delta)
            delta = float(abs(method.predict(c[pure], model, corrected)-r[pure]).max())
            assert delta < 1e-12
            checks['pure_max_abs'] = max(checks['pure_max_abs'], delta)
            spectrum = method.predict(np.vstack([c, dense]), model, corrected)
            assert np.isfinite(spectrum).all() and (spectrum > 0).all() and (spectrum < 1).all()
            checks['dense_min'] = min(checks['dense_min'], float(spectrum.min()))
            checks['dense_max'] = max(checks['dense_max'], float(spectrum.max()))
        details[key] = {'training_count': len(manifest['jobs'][key]['train_rows']),
            'base_runs': model['base']['runs'], 'correction': model['optimizer'], 'active_controls': int(sum(model['active']))}
    return {'checks': checks, 'refitted_models': len(repeated), 'additional_dense_recipes_per_model': len(dense), 'models': details}


def evaluate(c, r, manifest, results, reference):
    assert len(results) == 107 and all(x['status'] == 'success' for x in results.values())
    predictions = {name: np.full_like(r, np.nan) for name in MODEL_NAMES}
    record_folds = {}
    counts = (c > 0).sum(1)
    for key, fold in manifest['folds'].items():
        idx = np.array(fold['test_rows'])-1
        for i in idx:
            assert int(i) not in record_folds
            record_folds[int(i)] = key
        for approach in ('binary', 'expanded', 'balanced'):
            item = (results if approach == 'balanced' else reference)[fold['models'][approach]]
            assert item['status'] == 'success'
            for suffix, corrected in [('km', False), ('empirical', True)]:
                predictions[f'{approach}_{suffix}'][idx] = method.predict(c[idx], item['model'], corrected)
    idx = np.array(sorted(record_folds))
    assert len(idx) == 233
    _, _, lab = method.old.colorimetry()
    metrics = {name: method.old.errors(r[idx], p[idx], lab) for name, p in predictions.items()}
    masks = {'multicolor183': counts[idx] >= 3, 'binary50': counts[idx] == 2, 'all233': np.ones(len(idx), dtype=bool),
        'multicolor_no_white': (counts[idx] >= 3)&(c[idx, 7] == 0), 'multicolor_with_white': (counts[idx] >= 3)&(c[idx, 7] > 0)}
    masks.update({f'{i}_paints': counts[idx] == i for i in range(3, 8)})
    np.testing.assert_array_equal(idx[masks['multicolor183']]+1, manifest['primary_rows'])
    np.testing.assert_array_equal(idx[masks['binary50']]+1, manifest['binary_assessment_rows'])
    groups = {}
    for key, fold in manifest['folds'].items():
        mask = np.isin(idx+1, fold['test_rows'])
        primary = mask & masks['multicolor183']
        groups[key] = {'test_rows': fold['test_rows'], 'ratio': fold['ratio'],
            'all': {name: method.old.summarize(m, mask) for name, m in metrics.items()},
            'multicolor': {name: method.old.summarize(m, primary) for name, m in metrics.items()} if primary.any() else None}
    summary = {'status': 'predeclared balanced-category candidate; same-source development evidence',
        'subsets': {role: {name: method.old.summarize(m, mask) for name, m in metrics.items()} for role, mask in masks.items()},
        'groups': groups, 'comparisons': {}, 'equal_family_means': {},
        'colorimetry': '31 measured bands, 400-700 nm; truncated D65/2 degree, matching white, unclipped XYZ/Lab'}
    comparisons = [('balanced_empirical', f'{ref}_empirical', f'balanced_vs_{ref}') for ref in ('binary', 'expanded')]
    comparisons += [('balanced_km', f'{ref}_km', f'base_vs_{ref}') for ref in ('binary', 'expanded')]
    comparisons += [('balanced_empirical', 'balanced_km', 'balanced_correction_vs_base')]
    for role, mask in masks.items():
        summary['comparisons'][role] = {}
        for a, b, label in comparisons:
            summary['comparisons'][role][label] = {}
            for metric in ('spectral_rmse', 'delta_e_2000'):
                x, y = metrics[a][metric][mask], metrics[b][metric][mask]
                delta = x-y
                summary['comparisons'][role][label][metric] = {'mean_error_change_percent': float(100*(x.mean()/y.mean()-1)),
                    'improved': int((delta < -1e-12).sum()), 'worsened': int((delta > 1e-12).sum()), 'tied': int((abs(delta) <= 1e-12).sum())}
    for role in ('multicolor', 'all'):
        selected = [g[role] for g in groups.values() if g[role] is not None]
        summary['equal_family_means'][role] = {'families': len(selected), 'scores': {name: {
            metric: float(np.mean([g[name][metric]['mean'] for g in selected]))
            for metric in ('spectral_rmse', 'delta_e_2000')} for name in MODEL_NAMES}}
    archived = json.loads((previous.HERE/'summary.json').read_text(encoding='utf-8'))
    for role, scores in summary['subsets'].items():
        for name in previous.MODEL_NAMES:
            assert scores[name] == archived['subsets'][role][name]
    records = [{'source_row': int(i+1), 'family': record_folds[int(i)], 'paint_count': int(counts[i]), 'white_fraction': float(c[i, 7]),
        **{f'{name}_{metric}': float(values[j]) for name, m in metrics.items() for metric, values in m.items()}} for j, i in enumerate(idx)]
    return summary, records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=['prepare', 'fit', 'verify', 'evaluate'])
    parser.add_argument('--out', type=Path, default=DEFAULT)
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.workers <= 8:
        raise ValueError('Use 1-8 worker processes')
    out = method.old.research_directory(args.out)
    c, r, manifest, reference = inputs()
    partition, frozen = out/'partition.json', out/'frozen-models.json'
    if args.phase == 'prepare':
        assert not partition.exists() and not frozen.exists(), 'Use a fresh output directory'
        check = preflight(c, r, manifest, reference)
        for dest in (out, HERE):
            method.old.write_json(dest/'preflight.json', check)
            method.old.write_json(dest/'partition.json', manifest)
        print(json.dumps(check, indent=2))
        return
    assert json.loads(partition.read_text(encoding='utf-8')) == manifest
    identity = method.old.sha(partition.read_bytes())
    if args.phase == 'fit':
        assert not frozen.exists(), 'Refusing frozen-model overwrite'
        results = fit_jobs(c, r, manifest, out, args.workers)
        method.old.write_json(frozen, {'manifest_sha256': identity, 'results': results})
        print('Frozen', method.old.sha(frozen.read_bytes()), 'failures', sum(x['status'] != 'success' for x in results.values()))
        return
    raw = frozen.read_bytes()
    bundle = json.loads(raw)
    assert bundle['manifest_sha256'] == identity
    if args.phase == 'verify':
        result = verify(c, r, manifest, bundle['results'], out, args.workers)
        result.update({'manifest_sha256': identity, 'bundle_sha256': method.old.sha(raw)})
        for dest in (out, HERE):
            method.old.write_json(dest/'verification.json', result)
        print(json.dumps(result['checks'], indent=2))
    if args.phase == 'evaluate':
        verified = json.loads((out/'verification.json').read_text(encoding='utf-8'))
        assert verified['manifest_sha256'] == identity and verified['bundle_sha256'] == method.old.sha(raw)
        summary, records = evaluate(c, r, manifest, bundle['results'], reference)
        summary.update({'manifest_sha256': identity, 'bundle_sha256': method.old.sha(raw), 'unique_candidate_fits': len(bundle['results'])})
        for dest in (out, HERE):
            method.old.write_json(dest/'summary.json', summary)
            method.old_chromatic.write_csv(dest/'errors.csv', records)
        print(json.dumps(summary['comparisons']['multicolor183'], indent=2))
    assert frozen.read_bytes() == raw
    for name, digest in manifest['hashes'].items():
        assert method.old.sha((ROOT/name).read_bytes()) == digest, name


if __name__ == '__main__':
    main()
