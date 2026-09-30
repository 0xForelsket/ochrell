"""Frozen Old Holland four-paint study. Separate audit, fit and evaluate commands.

Raw measurements and fitted coefficients are local research files under target/.
No download occurs implicitly; supply the author's checksum-verified ZIP.
Dependencies: the existing requirements.txt. No changes to the Rust model.
"""
import argparse
import csv
import hashlib
import io
import json
import platform
import sys
import time
import zipfile
from pathlib import Path

import numpy as np
import scipy
from scipy.optimize import least_squares

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'config/measured-oils-v1.json'
PLAN = ROOT / 'docs/measured-oils-plan.md'
HASHES = {
    'archive': 'cda35e5ab968bb18a05127c1b9fb0b2bd3c4a4bb88d4bf4ae1e4b2bb5de07538',
    'readme.txt': '3ae32534a6ac43746f9338190fb182d06e7d9dfdf30d84b4fa55fc3a6ee13ea3',
    'oilspectra.txt': '11436afe638351193eef2dbc87167ab0981464e170f4fd7e6106668adf85fc5b',
    'oilmixtureportions.txt': 'e968f8384f2ee03dcc16d34f87f895bf61cd63a67a4af99550d6144d0b1995ce',
}
NAMES = ['Scheveningen Yellow Lemon', 'Scarlet Lake extra', 'Cobalt Blue', 'Mixed White']
LABELS = ['Y', 'R', 'B', 'W']


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value, indent=2, allow_nan=False) + '\n').encode())


def research_directory(path):
    path = path.resolve()
    if not path.is_relative_to((ROOT / 'target').resolve()):
        raise ValueError('Source-derived research output must remain under ignored target/')
    path.mkdir(parents=True, exist_ok=True)
    return path


def partition(amounts):
    if amounts.shape != (286, 8) or not np.isfinite(amounts).all() or (amounts < 0).any() or (amounts.sum(axis=1) <= 0).any():
        raise ValueError('Invalid source mass portions')
    chosen = np.array([0, 2, 4, 7])
    keep = (amounts[:, [1, 3, 5, 6]] == 0).all(axis=1)
    source_rows = np.flatnonzero(keep) + 1
    c = amounts[keep][:, chosen]
    c = c / c.sum(axis=1, keepdims=True)
    counts = (c > 0).sum(axis=1)
    fit = (counts == 1) | ((counts == 2) & (c[:, 3] > 0))
    if len(c) != 45 or fit.sum() != 21 or (counts == 1).sum() != 4:
        raise ValueError('Source no longer matches the frozen 45-row / 21-24 design')
    if len(np.unique(c.round(12), axis=0)) != 45:
        raise ValueError('Duplicate normalized recipes')
    return source_rows, c, fit


def load_source(path):
    raw = path.read_bytes()
    if sha(raw) != HASHES['archive']:
        raise ValueError('Archive checksum differs from the selected source')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        files = {name: archive.read(name) for name in HASHES if name != 'archive'}
    for name, data in files.items():
        if sha(data) != HASHES[name]:
            raise ValueError(f'Unexpected member checksum: {name}')
    amounts = np.loadtxt(io.BytesIO(files['oilmixtureportions.txt']))
    reflectance = np.loadtxt(io.BytesIO(files['oilspectra.txt']))
    if reflectance.shape != (286, 31) or not np.isfinite(reflectance).all() or ((reflectance <= 0) | (reflectance >= 1)).any():
        raise ValueError('Expected finite source reflectance strictly inside (0,1)')
    rows, c, fit = partition(amounts)
    return rows, c, reflectance[rows - 1], fit


def family(c):
    return '+'.join(LABELS[i] for i in np.flatnonzero(c > 0))


def manifest(rows, c, fit):
    return {
        'experiment': 'old-holland-four-reference-v1', 'source_sha256': HASHES,
        'config_sha256': sha(CONFIG.read_bytes()), 'plan_sha256': sha(PLAN.read_bytes()),
        'source_columns_one_based': [1, 3, 5, 8], 'paint_names': NAMES,
        'wavelengths_nm': list(range(400, 701, 10)), 'amounts': 'normalized recorded tube-paint mass',
        'fit_rows_one_based': rows[fit].tolist(), 'holdout_rows_one_based': rows[~fit].tolist(),
        'family_counts': {role: {f: sum(family(x) == f for x in c[mask]) for f in sorted({family(x) for x in c[mask]})}
                          for role, mask in [('fit', fit), ('holdout', ~fit)]},
    }


def pure_ratios(c, measured):
    pure = []
    for paint in range(4):
        indices = np.flatnonzero((c[:, paint] == 1) & ((c > 0).sum(axis=1) == 1))
        if len(indices) != 1:
            raise ValueError('Exactly one measured pure sample per paint is required')
        pure.append(measured[indices[0]])
    pure = np.asarray(pure)
    return (1 - pure) ** 2 / (2 * pure)


def predict(c, q, u):
    s = np.vstack([np.exp(u.reshape(3, 31)), np.ones(31)])
    k = q * s
    denominator = c @ s
    ratio = (c @ k) / denominator
    r = 1 / (1 + ratio + np.sqrt(ratio * (ratio + 2)))
    return r, ratio, denominator, s, k


def objective(c, measured, q, settings):
    count = measured.size
    d2 = np.diff(np.eye(31), n=2, axis=0)
    curve = np.kron(np.eye(3), d2) * np.sqrt(settings['curvature_weight'] / (3 * 29))
    prior = np.eye(93) * np.sqrt(settings['amplitude_weight'] / 93)
    def residual(u):
        prediction = predict(c, q, u)[0]
        return np.concatenate([(prediction - measured).ravel() / np.sqrt(count), curve @ u, prior @ u])
    def jacobian(u):
        r, ratio, denominator, s, _ = predict(c, q, u)
        derivative = -r / np.sqrt(ratio * (ratio + 2))
        jac = np.zeros((count, 93))
        for paint in range(3):
            values = derivative * c[:, paint, None] * s[paint] * (q[paint] - ratio) / denominator
            jac[np.arange(count), np.tile(np.arange(31) + paint * 31, len(c))] = values.ravel() / np.sqrt(count)
        return np.vstack([jac, curve, prior])
    return residual, jacobian


def fit_model(c_fit, r_fit, settings):
    """Only fitting samples cross this interface; there is no holdout argument."""
    q = pure_ratios(c_fit, r_fit)
    residual, jacobian = objective(c_fit, r_fit, q, settings)
    runs, solutions = [], []
    for initial in settings['initial_log_scattering']:
        start = time.perf_counter()
        sol = least_squares(residual, np.full(93, initial), jac=jacobian, method='trf',
                            bounds=settings['log_scattering_bounds'], max_nfev=settings['max_nfev'],
                            ftol=settings['ftol'], xtol=settings['xtol'], gtol=settings['gtol'])
        runs.append({'initial_log_s': initial, 'success': bool(sol.success), 'status': int(sol.status),
                     'message': sol.message, 'nfev': sol.nfev, 'njev': sol.njev,
                     'objective': float(np.sum(sol.fun ** 2)), 'optimality': float(sol.optimality),
                     'bound_variables': int(np.count_nonzero(sol.active_mask)),
                     'elapsed_seconds': time.perf_counter() - start})
        solutions.append(sol)
    converged = [i for i, x in enumerate(runs) if x['success']]
    if not converged:
        raise RuntimeError(f'No converged fit: {runs}')
    selected = min(converged, key=lambda i: (runs[i]['objective'], i))
    u = solutions[selected].x
    _, _, _, s, k = predict(c_fit, q, u)
    return {'q': q.tolist(), 'log_relative_s': u.reshape(3, 31).tolist(), 'K': k.tolist(), 'S': s.tolist(),
            'runs': runs, 'selected_start': selected, 'settings': settings,
            'scattering_range': [float(s.min()), float(s.max())]}


def colorimetry():
    import colour
    with (ROOT / 'data/cie_380_780_1nm.csv').open(newline='') as f:
        cie = {int(r['nm']): r for r in csv.DictReader(f)}
    weights = np.array([[float(cie[nm]['D65']) * float(cie[nm][ch]) for ch in ['xbar', 'ybar', 'zbar']]
                        for nm in range(400, 701, 10)])
    weights[[0, -1]] *= 0.5
    weights /= weights[:, 1].sum()
    white = weights.sum(axis=0)
    xy = white[:2] / white.sum()
    def lab(spectra):
        return colour.XYZ_to_Lab(spectra @ weights, illuminant=xy)
    return weights, white, lab


def errors(measured, predicted, lab):
    import colour
    difference = predicted - measured
    return {'spectral_rmse': np.sqrt(np.mean(difference ** 2, axis=1)),
            'spectral_mae': np.mean(np.abs(difference), axis=1),
            'spectral_max_abs': np.max(np.abs(difference), axis=1),
            'delta_e_2000': colour.delta_E(lab(measured), lab(predicted), method='CIE 2000')}


def summarize(metrics, mask):
    return {'count': int(mask.sum()), **{key: {'mean': float(np.mean(value[mask])),
            'median': float(np.median(value[mask])), 'p95': float(np.quantile(value[mask], .95)),
            'max': float(np.max(value[mask]))} for key, value in metrics.items()}}


def evaluate(rows, c, measured, fit, model):
    q = np.asarray(model['q'])
    fitted = predict(c, q, np.asarray(model['log_relative_s']).ravel())[0]
    baseline = predict(c, q, np.zeros(93))[0]
    _, white, lab = colorimetry()
    values = {name: errors(measured, predicted, lab) for name, predicted in [('fitted', fitted), ('equal_s_baseline', baseline)]}
    summary = {'colorimetry': 'CIE 1931 2deg / D65; 400-700nm at 10nm trapezoid; truncated white; unclipped XYZ/Lab',
               'truncated_white_xyz': white.tolist(), 'models': {}}
    for name, metrics in values.items():
        summary['models'][name] = {role: summarize(metrics, mask) for role, mask in
                                  [('fit_all', fit), ('fit_tints', fit & ((c > 0).sum(axis=1) == 2)), ('holdout', ~fit)]}
        summary['models'][name]['families'] = {role: {f: summarize(metrics, mask & np.array([family(x) == f for x in c]))
                for f in sorted({family(x) for x in c[mask]})} for role, mask in [('fit', fit), ('holdout', ~fit)]}
        worst = sorted(np.flatnonzero(~fit), key=lambda i: (-metrics['delta_e_2000'][i], int(rows[i])))[:5]
        summary['models'][name]['worst_holdout'] = [{'source_row': int(rows[i]), 'family': family(c[i]),
            **{key: float(val[i]) for key, val in metrics.items()}} for i in worst]
    h = summary['models']['fitted']['holdout']
    screen_values = {'mean_spectral_rmse': h['spectral_rmse']['mean'], 'p95_spectral_rmse': h['spectral_rmse']['p95'],
                     'mean_delta_e_2000': h['delta_e_2000']['mean'], 'p95_delta_e_2000': h['delta_e_2000']['p95'],
                     'max_delta_e_2000': h['delta_e_2000']['max']}
    summary['quality_screen'] = {name: {'actual': value, 'limit': model['settings']['quality_screen'][name],
        'passed': value <= model['settings']['quality_screen'][name]} for name, value in screen_values.items()}
    summary['passed_quality_screen'] = all(x['passed'] for x in summary['quality_screen'].values())
    return summary, values, fitted, baseline


def plots(out, rows, measured, fitted, baseline, fit, metrics):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    wavelengths = np.arange(400, 701, 10)
    idx = np.flatnonzero(~fit)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), layout='constrained')
    for ax, key, label in zip(axes, ['spectral_rmse', 'delta_e_2000'], ['Spectral RMSE (reflectance)', 'CIEDE2000 (truncated D65)']):
        x = np.arange(len(idx))
        ax.bar(x - .18, metrics['equal_s_baseline'][key][idx], .36, label='Equal-S baseline', color='#9aa7b4')
        ax.bar(x + .18, metrics['fitted'][key][idx], .36, label='Fitted to pure + white tints', color='#246b77')
        ax.set_xticks(x, rows[idx], rotation=90); ax.set_xlabel('Held-out source row (one-based)'); ax.set_ylabel(label)
        ax.legend(fontsize=8); ax.grid(axis='y', alpha=.2)
    fig.suptitle('Old Holland four-paint reference: all 24 held-out mixtures')
    fig.savefig(out / 'holdout-errors.png', dpi=170); plt.close(fig)
    worst = sorted(idx, key=lambda i: -metrics['fitted']['delta_e_2000'][i])[:4]
    fig, axes = plt.subplots(2, 2, figsize=(10, 7), layout='constrained')
    for ax, i in zip(axes.flat, worst):
        ax.plot(wavelengths, measured[i], color='black', label='Measured')
        ax.plot(wavelengths, fitted[i], color='#246b77', label='Fitted model')
        ax.plot(wavelengths, baseline[i], '--', color='#9aa7b4', label='Equal-S baseline')
        ax.set_title(f"Row {rows[i]}: DE00 {metrics['fitted']['delta_e_2000'][i]:.2f}")
        ax.set_xlabel('Wavelength (nm)'); ax.set_ylabel('Reflectance'); ax.legend(fontsize=8); ax.grid(alpha=.2)
    fig.savefig(out / 'worst-spectra.png', dpi=170); plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['audit', 'fit', 'evaluate'])
    parser.add_argument('--source', type=Path, default=ROOT / 'target/measured-oils/source/spectralDatasets.zip')
    parser.add_argument('--out', type=Path, default=ROOT / 'target/measured-oils/v1')
    args = parser.parse_args()
    out = research_directory(args.out)
    rows, c, measured, fit = load_source(args.source)
    audit = manifest(rows, c, fit)
    manifest_path = out / 'partition.json'
    if args.phase == 'audit':
        write_json(manifest_path, audit)
        print(json.dumps(audit, indent=2)); return
    if not manifest_path.exists() or json.loads(manifest_path.read_text()) != audit:
        raise ValueError('Run audit first; source/design differs from the frozen partition')
    model_path = out / 'fitted-model.json'
    if args.phase == 'fit':
        if model_path.exists():
            raise ValueError('Refusing to overwrite a frozen fit; use a fresh research directory')
        settings = json.loads(CONFIG.read_text())
        model = fit_model(c[fit].copy(), measured[fit].copy(), settings)
        model.update({'partition_sha256': sha(manifest_path.read_bytes()), 'fit_rows': rows[fit].tolist(),
            'source_sha256': HASHES['archive'], 'implementation_sha256': sha(Path(__file__).read_bytes()),
            'environment': {'python': sys.version, 'numpy': np.__version__, 'scipy': scipy.__version__, 'platform': platform.platform()},
            'reuse_status': 'Separate dataset redistribution terms unresolved; local research only'})
        write_json(model_path, model)
        print(json.dumps({'model_sha256': sha(model_path.read_bytes()), 'selected_start': model['selected_start'],
                          'runs': model['runs']}, indent=2)); return
    model = json.loads(model_path.read_text())
    if model['partition_sha256'] != sha(manifest_path.read_bytes()) or model['settings'] != json.loads(CONFIG.read_text()):
        raise ValueError('Frozen model does not match the audited source/design')
    summary, metrics, fitted, baseline = evaluate(rows, c, measured, fit, model)
    summary.update({'experiment': audit['experiment'], 'source_sha256': HASHES['archive'],
        'partition_sha256': sha(manifest_path.read_bytes()), 'model_sha256': sha(model_path.read_bytes()),
        'fit_implementation_sha256': model['implementation_sha256'], 'evaluation_implementation_sha256': sha(Path(__file__).read_bytes()),
        'plan_sha256': audit['plan_sha256'], 'config_sha256': audit['config_sha256'],
        'cie_sha256': sha((ROOT / 'data/cie_380_780_1nm.csv').read_bytes()),
        'optimizer': {'runs': model['runs'], 'selected_start': model['selected_start'], 'scattering_range': model['scattering_range']},
        'environment': model['environment'], 'reuse_status': model['reuse_status']})
    write_json(out / 'summary.json', summary)
    fields = ['source_row', 'role', 'family'] + [f'{name}_{key}' for name in metrics for key in metrics[name]]
    with (out / 'errors.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n'); writer.writeheader()
        for i in range(len(c)):
            writer.writerow({'source_row': int(rows[i]), 'role': 'fit' if fit[i] else 'holdout', 'family': family(c[i]),
                **{f'{name}_{key}': float(val[i]) for name in metrics for key, val in metrics[name].items()}})
    # Full spectral residuals are research-only, never in the distributable report.
    np.savetxt(out / 'holdout-spectral-residuals.csv', fitted[~fit] - measured[~fit], delimiter=',')
    plots(out, rows, measured, fitted, baseline, fit, metrics)
    print(json.dumps({'passed_quality_screen': summary['passed_quality_screen'], 'quality_screen': summary['quality_screen'],
                      'fitted_holdout': summary['models']['fitted']['holdout'], 'baseline_holdout': summary['models']['equal_s_baseline']['holdout']}, indent=2))


if __name__ == '__main__':
    main()
