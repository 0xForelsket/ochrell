"""One frozen soft-pure revision, fitted to 21 calibration samples only.

The 24 former v1 holdouts are exposed development data. Their evaluation is
exploratory; no independent validation claim is made. See the revision plan.
"""
import argparse
import csv
import json
import math
import platform
import sys
import time
from pathlib import Path

import numpy as np
import scipy
from scipy.interpolate import BSpline
from scipy.optimize import least_squares
import measured_oils as v1

CONFIG = v1.ROOT / 'config/measured-oils-v2.json'
PLAN = v1.ROOT / 'docs/measured-oils-revision-plan.md'


def basis():
    return BSpline([400, 400, 400, 400, 550, 700, 700, 700, 700], np.eye(5), 3)(np.arange(400, 701, 10))


def pure_samples(c, r):
    rows = []
    for j in range(4):
        indices = np.flatnonzero((c[:, j] == 1) & ((c > 0).sum(axis=1) == 1))
        if len(indices) != 1:
            raise ValueError('Expected one pure observation per paint')
        rows.append(r[indices[0]])
    return np.asarray(rows)


def predict(c, pure, x):
    delta = x[93:].reshape(4, 5) @ basis().T
    corrected = pure + delta
    q = (1 - corrected) ** 2 / (2 * corrected)
    r, ratio, denominator, s, k = v1.predict(c, q, x[:93])
    return r, ratio, denominator, s, k, corrected, q, delta


def bounds(pure, settings):
    cap = settings['pure_shift_max_abs']
    floor = settings['pure_reflectance_floor']
    low = np.maximum(-cap, floor - pure.min(axis=1))
    high = np.minimum(cap, 1 - floor - pure.max(axis=1))
    if (low >= 0).any() or (high <= 0).any():
        raise ValueError('Measured pure spectrum is outside the supported interior')
    a, b = settings['log_scattering_bounds']
    return np.r_[np.full(93, a), np.repeat(low, 5)], np.r_[np.full(93, b), np.repeat(high, 5)]


def objective(c, measured, pure, settings):
    count = measured.size
    b = basis()
    d2 = np.diff(np.eye(31), n=2, axis=0)
    curve = np.kron(np.eye(3), d2) * np.sqrt(settings['curvature_weight'] / 87)
    prior = np.eye(93) * np.sqrt(settings['amplitude_weight'] / 93)
    anchor = np.kron(np.eye(4), b) * np.sqrt(settings['pure_anchor_weight'] / 124)
    penalty = np.zeros((87 + 93 + 124, 113))
    penalty[:87, :93] = curve
    penalty[87:180, :93] = prior
    penalty[180:, 93:] = anchor
    def residual(x):
        return np.r_[(predict(c, pure, x)[0] - measured).ravel() / np.sqrt(count), penalty @ x]
    def jacobian(x):
        r, ratio, denominator, s, _, corrected, q, _ = predict(c, pure, x)
        derivative = -r / np.sqrt(ratio * (ratio + 2))
        jac = np.zeros((count, 113))
        for j in range(4):
            fraction = c[:, j, None] * s[j] / denominator
            if j < 3:
                values = derivative * fraction * (q[j] - ratio)
                jac[np.arange(count), np.tile(np.arange(31) + j * 31, len(c))] = values.ravel() / np.sqrt(count)
            values = derivative * fraction * (.5 - .5 / corrected[j] ** 2)
            jac[:, 93 + j * 5:93 + (j + 1) * 5] = (values[:, :, None] * b[None, :, :]).reshape(count, 5) / np.sqrt(count)
        return np.vstack([jac, penalty])
    return residual, jacobian


def fit_model(c_fit, r_fit, settings):
    """Only 21 calibration rows are supplied by the study; no evaluation input."""
    pure = pure_samples(c_fit, r_fit)
    residual, jacobian = objective(c_fit, r_fit, pure, settings)
    lower, upper = bounds(pure, settings)
    runs, solutions = [], []
    scale = np.r_[np.ones(93), np.full(20, settings['pure_shift_max_abs'])]
    for initial in settings['initial_log_scattering']:
        start = time.perf_counter()
        sol = least_squares(residual, np.r_[np.full(93, initial), np.zeros(20)], jac=jacobian, method='trf',
            bounds=(lower, upper), x_scale=scale, max_nfev=settings['max_nfev'],
            ftol=settings['ftol'], xtol=settings['xtol'], gtol=settings['gtol'])
        solutions.append(sol)
        runs.append({'initial_log_s': initial, 'success': bool(sol.success), 'status': int(sol.status),
            'message': sol.message, 'nfev': sol.nfev, 'njev': sol.njev,
            'objective': float(np.sum(sol.fun ** 2)), 'optimality': float(sol.optimality),
            'scattering_bound_variables': int(np.count_nonzero(sol.active_mask[:93])),
            'pure_control_bound_variables': int(np.count_nonzero(sol.active_mask[93:])),
            'elapsed_seconds': time.perf_counter() - start})
    converged = [i for i, run in enumerate(runs) if run['success']]
    if not converged:
        raise RuntimeError(f'No converged revision: {runs}')
    selected = min(converged, key=lambda i: (runs[i]['objective'], i))
    x = solutions[selected].x
    _, _, _, s, k, corrected, q, delta = predict(c_fit, pure, x)
    return {'settings': settings, 'q': q.tolist(), 'K': k.tolist(), 'S': s.tolist(),
        'log_relative_s': x[:93].reshape(3, 31).tolist(), 'pure_shift_controls': x[93:].reshape(4, 5).tolist(),
        'measured_pure': pure.tolist(), 'corrected_pure': corrected.tolist(), 'pure_shift': delta.tolist(),
        'control_bounds': {'lower': lower[93:].reshape(4, 5).tolist(), 'upper': upper[93:].reshape(4, 5).tolist()},
        'selected_start': selected, 'runs': runs}


def compare(rows, c, measured, fit, baseline, revision):
    old = v1.predict(c, np.asarray(baseline['q']), np.asarray(baseline['log_relative_s']).ravel())[0]
    x = np.r_[np.asarray(revision['log_relative_s']).ravel(), np.asarray(revision['pure_shift_controls']).ravel()]
    new = predict(c, np.asarray(revision['measured_pure']), x)[0]
    _, _, lab = v1.colorimetry()
    metrics = {name: v1.errors(measured, r, lab) for name, r in [('v1', old), ('v2_soft_pure', new)]}
    pure = fit & ((c > 0).sum(axis=1) == 1)
    masks = {'calibration_all': fit, 'calibration_pure': pure, 'calibration_tints': fit & ~pure, 'exposed_24': ~fit}
    result = {'evaluation_status': 'exploratory; the 24 former holdouts informed this revision',
        'colorimetry': 'CIEDE2000, unmodified v1 31-band truncated D65 / 2-degree XYZ/Lab',
        'models': {name: {role: v1.summarize(m, mask) for role, mask in masks.items()} for name, m in metrics.items()}}
    for name, m in metrics.items():
        result['models'][name]['families'] = {role: {f: v1.summarize(m, mask & np.array([v1.family(recipe) == f for recipe in c]))
            for f in sorted({v1.family(recipe) for recipe in c[mask]})} for role, mask in [('calibration', fit), ('exposed_24', ~fit)]}
    result['pure_changes'] = [{'paint': v1.LABELS[j], 'max_abs_shift': float(np.max(np.abs(np.asarray(revision['pure_shift'])[j]))),
        'rms_shift': float(np.sqrt(np.mean(np.asarray(revision['pure_shift'])[j] ** 2))),
        'delta_e_2000': float(metrics['v2_soft_pure']['delta_e_2000'][np.flatnonzero(c[:, j] == 1)[0]])} for j in range(4)]
    delta = metrics['v2_soft_pure']['delta_e_2000'] - metrics['v1']['delta_e_2000']
    result['exposed_comparison'] = {'color_improved': int(np.sum(delta[~fit] < 0)), 'color_worsened': int(np.sum(delta[~fit] > 0)),
        'spectral_rmse_improved': int(np.sum(metrics['v2_soft_pure']['spectral_rmse'][~fit] < metrics['v1']['spectral_rmse'][~fit])),
        'worst_regressions': [{'source_row': int(rows[i]), 'family': v1.family(c[i]), 'delta_e_increase': float(delta[i]),
            'v1_delta_e': float(metrics['v1']['delta_e_2000'][i]), 'v2_delta_e': float(metrics['v2_soft_pure']['delta_e_2000'][i])}
            for i in sorted(np.flatnonzero(~fit), key=lambda i: -delta[i])[:5]]}
    h = result['models']['v2_soft_pure']['exposed_24']
    values = {'mean_spectral_rmse': h['spectral_rmse']['mean'], 'p95_spectral_rmse': h['spectral_rmse']['p95'],
        'mean_delta_e_2000': h['delta_e_2000']['mean'], 'p95_delta_e_2000': h['delta_e_2000']['p95'], 'max_delta_e_2000': h['delta_e_2000']['max']}
    result['original_quality_screen_exploratory'] = {key: {'actual': value, 'limit': baseline['settings']['quality_screen'][key],
        'passed': value <= baseline['settings']['quality_screen'][key]} for key, value in values.items()}
    pure_max = result['models']['v2_soft_pure']['calibration_pure']['delta_e_2000']['max']
    result['pure_color_screen'] = {'actual_max_delta_e_2000': pure_max, 'limit': revision['settings']['pure_color_screen_max_delta_e_2000'],
        'passed': pure_max <= revision['settings']['pure_color_screen_max_delta_e_2000']}
    # Independent scalar K-M from the saved K/S, using the subtractive equation.
    k, s = np.asarray(revision['K']), np.asarray(revision['S'])
    independent = np.empty_like(new)
    for i, recipe in enumerate(c):
        for band in range(31):
            q = sum(float(w) * float(k[j, band]) for j, w in enumerate(recipe)) / sum(float(w) * float(s[j, band]) for j, w in enumerate(recipe))
            independent[i, band] = 1 + q - math.sqrt(q * q + 2 * q)
    difference = float(np.max(np.abs(independent - new)))
    if difference > 1e-12:
        raise AssertionError('Independent scalar validation failed')
    result['independent_scalar_max_abs_error'] = difference
    return result, metrics


def plots(out, rows, fit, metrics):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), layout='constrained')
    idx = np.flatnonzero(~fit); x = np.arange(len(idx))
    for ax, key, title in zip(axes, ['spectral_rmse', 'delta_e_2000'], ['Spectral RMSE', 'CIEDE2000 (truncated D65)']):
        ax.bar(x - .18, metrics['v1'][key][idx], .36, label='V1 fixed pure', color='#9aa7b4')
        ax.bar(x + .18, metrics['v2_soft_pure'][key][idx], .36, label='V2 constrained soft pure', color='#246b77')
        ax.set_xticks(x, rows[idx], rotation=90); ax.set_ylabel(title); ax.set_xlabel('Source row (one-based)')
        ax.legend(fontsize=8); ax.grid(axis='y', alpha=.2)
    fig.suptitle('Exploratory comparison on 24 previously exposed mixtures')
    fig.savefig(out / 'exploratory-errors.png', dpi=170); plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['prepare', 'fit', 'evaluate'])
    parser.add_argument('--source', type=Path, default=v1.ROOT / 'target/measured-oils/source/spectralDatasets.zip')
    parser.add_argument('--baseline', type=Path, default=v1.ROOT / 'target/measured-oils/v1/fitted-model.json')
    parser.add_argument('--out', type=Path, default=v1.ROOT / 'target/measured-oils/v2-soft-pure')
    args = parser.parse_args(); out = v1.research_directory(args.out)
    baseline_sha = v1.sha(args.baseline.read_bytes())
    baseline = json.loads(args.baseline.read_text())
    if (baseline['source_sha256'] != v1.HASHES['archive']
            or baseline['settings'] != json.loads(v1.CONFIG.read_text())
            or baseline['implementation_sha256'] != v1.sha(Path(v1.__file__).read_bytes())):
        raise ValueError('Expected a coefficient artifact from the frozen v1 study')
    rows, c, measured, fit = v1.load_source(args.source)
    if baseline['fit_rows'] != rows[fit].tolist():
        raise ValueError('Calibration partition differs')
    settings = json.loads(CONFIG.read_text())
    manifest = {'experiment': settings['experiment'], 'source_sha256': v1.HASHES['archive'], 'baseline_model_sha256': baseline_sha,
        'plan_sha256': v1.sha(PLAN.read_bytes()), 'config_sha256': v1.sha(CONFIG.read_bytes()),
        'v1_implementation_sha256': v1.sha(Path(v1.__file__).read_bytes()),
        'calibration_rows': rows[fit].tolist(), 'exposed_evaluation_rows': rows[~fit].tolist()}
    manifest_path = out / 'partition.json'; model_path = out / 'fitted-model.json'
    if args.phase == 'prepare':
        if model_path.exists():
            raise ValueError('This directory already has a frozen revision')
        v1.write_json(manifest_path, manifest); print(json.dumps(manifest, indent=2)); return
    if json.loads(manifest_path.read_text()) != manifest:
        raise ValueError('Configuration/plan/source differs from preparation')
    if args.phase == 'fit':
        if model_path.exists():
            raise ValueError('Refusing to overwrite a frozen revision')
        model = fit_model(c[fit].copy(), measured[fit].copy(), settings)
        model.update({'fit_rows': rows[fit].tolist(), 'partition_sha256': v1.sha(manifest_path.read_bytes()),
            'implementation_sha256': v1.sha(Path(__file__).read_bytes()),
            'environment': {'python': sys.version, 'numpy': np.__version__, 'scipy': scipy.__version__, 'platform': platform.platform()}})
        v1.write_json(model_path, model)
        print(json.dumps({'model_sha256': v1.sha(model_path.read_bytes()), 'selected_start': model['selected_start'], 'runs': model['runs']}, indent=2)); return
    model = json.loads(model_path.read_text()); frozen_hash = v1.sha(model_path.read_bytes())
    if model['partition_sha256'] != v1.sha(manifest_path.read_bytes()) or model['settings'] != settings:
        raise ValueError('Frozen revision differs from experiment')
    if model['implementation_sha256'] != v1.sha(Path(__file__).read_bytes()):
        raise ValueError('Implementation changed after fitting; preserve the original experiment')
    result, metrics = compare(rows, c, measured, fit, baseline, model)
    old_summary = json.loads((v1.ROOT / 'results/measured-oils-v1/summary.json').read_text())
    if abs(result['models']['v1']['exposed_24']['delta_e_2000']['mean'] - old_summary['models']['fitted']['holdout']['delta_e_2000']['mean']) > 1e-12:
        raise AssertionError('Baseline color evaluation drifted')
    result.update({'manifest': manifest, 'model_sha256': frozen_hash, 'implementation_sha256': model['implementation_sha256'],
        'optimizer': {'runs': model['runs'], 'selected_start': model['selected_start']}, 'environment': model['environment']})
    v1.write_json(out / 'summary.json', result)
    fields = ['source_row', 'role', 'family'] + [f'{name}_{key}' for name, m in metrics.items() for key in m]
    with (out / 'errors.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n'); writer.writeheader()
        for i, row in enumerate(rows):
            writer.writerow({'source_row': int(row), 'role': 'calibration' if fit[i] else 'exposed_evaluation', 'family': v1.family(c[i]),
                **{f'{name}_{key}': float(values[i]) for name, m in metrics.items() for key, values in m.items()}})
    plots(out, rows, fit, metrics)
    if v1.sha(model_path.read_bytes()) != frozen_hash:
        raise AssertionError('Evaluation altered the fit')
    print(json.dumps({'models': {name: {role: m[role] for role in ['calibration_pure', 'calibration_tints', 'exposed_24']} for name, m in result['models'].items()},
        'pure_color_screen': result['pure_color_screen'], 'exposed_comparison': result['exposed_comparison']}, indent=2))


if __name__ == '__main__':
    main()
