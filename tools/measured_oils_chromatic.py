"""Frozen v3: add chromatic-pair calibration without changing the v1 model.

All assessments are exploratory. Four fits are frozen before evaluation: one
29-row primary model and three complete-pair-family validation refits.
"""
import argparse
import csv
import json
import platform
import sys
from pathlib import Path

import numpy as np
import scipy
import measured_oils as v1

CONFIG = v1.ROOT / 'config/measured-oils-v3.json'
PLAN = v1.ROOT / 'docs/measured-oils-v3-plan.md'
FAMILIES = ['Y+R', 'Y+B', 'R+B']


def design(c, original_fit):
    counts = (c > 0).sum(axis=1)
    pairs = (counts == 2) & (c[:, 3] == 0)
    multi = counts >= 3
    primary = original_fit | pairs
    if len(c) != 45 or original_fit.sum() != 21 or pairs.sum() != 8 or multi.sum() != 16:
        raise ValueError('Expected the fixed 21 + 8 + 16 study design')
    if (primary & multi).any() or not (primary | multi).all():
        raise ValueError('Training/evaluation overlap or missing samples')
    folds = {}
    for family, expected in zip(FAMILIES, [5, 1, 2]):
        test = np.array([v1.family(row) == family for row in c])
        train = primary & ~test
        if test.sum() != expected or (test & train).any() or (train & multi).any():
            raise ValueError('Invalid whole-family exclusion')
        folds[family] = (train, test)
    return primary, pairs, multi, folds


def reflectance_jacobian(c, q, u):
    r, ratio, denominator, s, _ = v1.predict(c, q, u)
    derivative = -r / np.sqrt(ratio * (ratio + 2))
    return np.stack([derivative * c[:, j, None] * s[j] * (q[j] - ratio) / denominator for j in range(3)], axis=-1)


def sensitivity(c, original_fit, primary, baseline):
    q = np.asarray(baseline['q']); u = np.asarray(baseline['log_relative_s']).ravel()
    rows = []
    singular = {}
    for name, mask in [('white_tints21', original_fit), ('with_pairs29', primary)]:
        jac = reflectance_jacobian(c[mask], q, u)
        singular[name] = np.array([np.linalg.svd(jac[:, b, :], compute_uv=False) for b in range(31)])
    for band, nm in enumerate(range(400, 701, 10)):
        row = {'wavelength_nm': nm}
        for name, values in singular.items():
            row[name + '_largest_singular_value'] = float(values[band, 0])
            row[name + '_smallest_singular_value'] = float(values[band, -1])
            row[name + '_condition_number'] = float(values[band, 0] / values[band, -1])
        rows.append(row)
    summary = {name: {'median_condition': float(np.median(values[:, 0] / values[:, -1])),
                     'max_condition': float(np.max(values[:, 0] / values[:, -1])),
                     '700nm_smallest_singular_value': float(values[-1, -1]),
                     '700nm_condition': float(values[-1, 0] / values[-1, -1])} for name, values in singular.items()}
    return rows, summary


def predicted(c, model):
    return v1.predict(c, np.asarray(model['q']), np.asarray(model['log_relative_s']).ravel())[0]


def independent_check(c, model, expected):
    k, s = np.asarray(model['K']), np.asarray(model['S'])
    reference = np.empty_like(expected)
    for i, recipe in enumerate(c):
        for band in range(31):
            ratio = sum(float(w) * float(k[j, band]) for j, w in enumerate(recipe)) / sum(float(w) * float(s[j, band]) for j, w in enumerate(recipe))
            reference[i, band] = 1 + ratio - (ratio * ratio + 2 * ratio) ** .5
    error = float(np.max(np.abs(reference - expected)))
    if error > 1e-12 or not np.isfinite(expected).all() or (expected < 0).any() or (expected > 1).any():
        raise AssertionError(f'Scalar reference mismatch: {error}')
    return error


def compare(rows, c, measured, original_fit, baseline, models):
    primary, pairs, multi, folds = design(c, original_fit)
    p1 = predicted(c, baseline)
    p3 = predicted(c, models['primary29'])
    cross = p3.copy()
    checks = {'primary29': independent_check(c, models['primary29'], p3)}
    for family, (_, test) in folds.items():
        values = predicted(c[test], models[family])
        checks[family] = independent_check(c[test], models[family], values)
        cross[test] = values
    _, _, lab = v1.colorimetry()
    metrics = {name: v1.errors(measured, p, lab) for name, p in [('v1', p1), ('v3_primary', p3), ('v3_cross_fitted', cross)]}
    m1, m3, mc = metrics.values()
    pure = (c > 0).sum(axis=1) == 1
    summary = {'evaluation_status': 'exploratory development evidence; all evaluation rows were previously exposed',
        'primary_multicolor16': {'v1': v1.summarize(m1, multi), 'v3': v1.summarize(m3, multi)},
        'calibration29': {'v1': v1.summarize(m1, primary), 'v3': v1.summarize(m3, primary)},
        'calibration_pure4': {'v1': v1.summarize(m1, pure), 'v3': v1.summarize(m3, pure)},
        'pair_family_cv8': {'v1': v1.summarize(m1, pairs), 'v3': v1.summarize(mc, pairs)},
        'cross_fitted24': {'v1': v1.summarize(m1, ~original_fit), 'v3': v1.summarize(mc, ~original_fit)},
        'cross_fitted24_interpretation': '16 primary-model predictions plus 8 predictions from three withheld-family models; not one deployable artifact',
        'folds': {}, 'families_multicolor16': {}, 'independent_scalar_max_abs_error': checks}
    for family, (train, test) in folds.items():
        if not np.array_equal(np.asarray(models[family]['q']), np.asarray(baseline['q'])):
            raise AssertionError('Fold changed pure K/S ratios')
        summary['folds'][family] = {'fit_count': int(train.sum()), 'test_count': int(test.sum()),
            'fit_rows': rows[train].tolist(), 'test_rows': rows[test].tolist(),
            'v1': v1.summarize(m1, test), 'v3': v1.summarize(mc, test)}
    for family in sorted({v1.family(row) for row in c[multi]}):
        mask = np.array([v1.family(row) == family for row in c])
        summary['families_multicolor16'][family] = {'v1': v1.summarize(m1, mask), 'v3': v1.summarize(m3, mask)}
    summary['pair_family_macro_mean'] = {name: {key: float(np.mean([f[name][key]['mean'] for f in summary['folds'].values()]))
        for key in ['spectral_rmse', 'delta_e_2000']} for name in ['v1', 'v3']}
    summary['changes'] = {}
    for role, mask, target in [('primary_multicolor16', multi, m3), ('pair_family_cv8', pairs, mc), ('cross_fitted24', ~original_fit, mc)]:
        change = target['delta_e_2000'] - m1['delta_e_2000']
        worse = sorted(np.flatnonzero(mask & (change > 1e-12)), key=lambda i: -change[i])
        summary['changes'][role] = {'color_improved': int(np.sum(change[mask] < -1e-12)),
            'color_worsened': int(np.sum(change[mask] > 1e-12)),
            'spectral_rmse_improved': int(np.sum(target['spectral_rmse'][mask] < m1['spectral_rmse'][mask])),
            'worst_color_regressions': [{'source_row': int(rows[i]), 'family': v1.family(c[i]), 'increase': float(change[i]),
                'v1': float(m1['delta_e_2000'][i]), 'v3': float(target['delta_e_2000'][i])} for i in worse[:5]]}
    h = summary['primary_multicolor16']['v3']
    values = {'mean_spectral_rmse': h['spectral_rmse']['mean'], 'p95_spectral_rmse': h['spectral_rmse']['p95'],
        'mean_delta_e_2000': h['delta_e_2000']['mean'], 'p95_delta_e_2000': h['delta_e_2000']['p95'], 'max_delta_e_2000': h['delta_e_2000']['max']}
    summary['original_screen_on_primary16_exploratory'] = {key: {'actual': value, 'limit': baseline['settings']['quality_screen'][key],
        'passed': value <= baseline['settings']['quality_screen'][key]} for key, value in values.items()}
    if not np.array_equal(np.asarray(models['primary29']['q']), np.asarray(baseline['q'])) or h['count'] != 16:
        raise AssertionError('Primary model changed the fixed-pure reference or assessment set')
    if summary['calibration_pure4']['v3']['spectral_max_abs']['max'] > 1e-12:
        raise AssertionError('Pure spectra moved')
    return summary, metrics


def plots(out, rows, masks, metrics, sensitivity_rows):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 4), layout='constrained')
    wavelengths = [r['wavelength_nm'] for r in sensitivity_rows]
    for name, label, color in [('white_tints21', 'Original 21 recipes', '#9aa7b4'), ('with_pairs29', 'Add eight chromatic pairs', '#246b77')]:
        ax.plot(wavelengths, [r[name + '_condition_number'] for r in sensitivity_rows], label=label, color=color)
    ax.set_xlabel('Wavelength (nm)'); ax.set_ylabel('Data Jacobian condition number'); ax.legend(); ax.grid(alpha=.2)
    ax.set_title('Local conditioning at frozen V1 coefficients; lower is better')
    fig.savefig(out / 'calibration-conditioning.png', dpi=170); plt.close(fig)
    multi, pairs = masks
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), layout='constrained')
    for ax, mask, name, title in zip(axes, [multi, pairs], ['v3_primary', 'v3_cross_fitted'],
            ['Primary model: 16 multicolor mixtures', 'Withheld pair families: 8 mixtures']):
        idx = np.flatnonzero(mask); x = np.arange(len(idx))
        ax.bar(x - .18, metrics['v1']['delta_e_2000'][idx], .36, label='V1', color='#9aa7b4')
        ax.bar(x + .18, metrics[name]['delta_e_2000'][idx], .36, label='V3 protocol', color='#246b77')
        ax.set_xticks(x, rows[idx], rotation=90); ax.set_ylabel('CIEDE2000 (truncated D65)'); ax.set_xlabel('Source row')
        ax.set_title(title); ax.legend(); ax.grid(axis='y', alpha=.2)
    fig.suptitle('Exploratory assessments: every scored row excluded from its fit')
    fig.savefig(out / 'exploratory-errors.png', dpi=170); plt.close(fig)


def write_csv(path, rows):
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator='\n'); writer.writeheader(); writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['prepare', 'fit', 'evaluate'])
    parser.add_argument('--source', type=Path, default=v1.ROOT / 'target/measured-oils/source/spectralDatasets.zip')
    parser.add_argument('--baseline', type=Path, default=v1.ROOT / 'target/measured-oils/v1/fitted-model.json')
    parser.add_argument('--out', type=Path, default=v1.ROOT / 'target/measured-oils/v3-chromatic')
    args = parser.parse_args(); out = v1.research_directory(args.out)
    baseline = json.loads(args.baseline.read_text())
    settings = json.loads(v1.CONFIG.read_text())
    if (baseline['source_sha256'] != v1.HASHES['archive'] or baseline['settings'] != settings
            or baseline['implementation_sha256'] != v1.sha(Path(v1.__file__).read_bytes())):
        raise ValueError('Expected a frozen v1 baseline')
    rows, c, measured, original_fit = v1.load_source(args.source)
    primary, pairs, multi, folds = design(c, original_fit)
    manifest = {'experiment': json.loads(CONFIG.read_text()), 'baseline_model_sha256': v1.sha(args.baseline.read_bytes()),
        'source_sha256': v1.HASHES['archive'], 'config_sha256': v1.sha(CONFIG.read_bytes()), 'plan_sha256': v1.sha(PLAN.read_bytes()),
        'fitting_settings_sha256': v1.sha(v1.CONFIG.read_bytes()), 'v1_implementation_sha256': v1.sha(Path(v1.__file__).read_bytes()),
        'primary_fit_rows': rows[primary].tolist(), 'primary_evaluation_rows': rows[multi].tolist(),
        'folds': {f: {'fit_rows': rows[train].tolist(), 'evaluation_rows': rows[test].tolist()} for f, (train, test) in folds.items()}}
    manifest_path = out / 'partition.json'; model_path = out / 'frozen-models.json'
    if args.phase == 'prepare':
        if model_path.exists(): raise ValueError('Models already frozen; use a fresh directory')
        v1.write_json(manifest_path, manifest)
        diag_rows, diag = sensitivity(c, original_fit, primary, baseline)
        write_csv(out / 'sensitivity.csv', diag_rows); v1.write_json(out / 'sensitivity-summary.json', diag)
        print(json.dumps({'primary_fit': int(primary.sum()), 'primary_test': int(multi.sum()), 'sensitivity': diag}, indent=2)); return
    if json.loads(manifest_path.read_text()) != manifest: raise ValueError('Prepared source/configuration/plan differs')
    if args.phase == 'fit':
        if model_path.exists(): raise ValueError('Refusing to overwrite frozen models')
        models = {}
        for name, train in [('primary29', primary)] + [(f, train) for f, (train, _) in folds.items()]:
            model = v1.fit_model(c[train].copy(), measured[train].copy(), settings)
            model['fit_rows'] = rows[train].tolist(); models[name] = model
            print(f"Fitted {name}: {train.sum()} rows; selected start {model['selected_start']}", flush=True)
        artifact = {'models': models, 'manifest': manifest, 'implementation_sha256': v1.sha(Path(__file__).read_bytes()),
                    'environment': {'python': sys.version, 'numpy': np.__version__, 'scipy': scipy.__version__, 'platform': platform.platform()}}
        v1.write_json(model_path, artifact)
        print('Frozen model bundle SHA-256:', v1.sha(model_path.read_bytes())); return
    artifact = json.loads(model_path.read_text()); frozen_hash = v1.sha(model_path.read_bytes())
    if artifact['manifest'] != manifest or artifact['implementation_sha256'] != v1.sha(Path(__file__).read_bytes()):
        raise ValueError('Frozen fit or implementation differs')
    for name, mask in [('primary29', primary)] + [(f, train) for f, (train, _) in folds.items()]:
        if artifact['models'][name]['fit_rows'] != rows[mask].tolist(): raise ValueError('Fit rows differ from manifest')
    summary, metrics = compare(rows, c, measured, original_fit, baseline, artifact['models'])
    old = json.loads((v1.ROOT / 'results/measured-oils-v1/summary.json').read_text())
    if abs(summary['cross_fitted24']['v1']['delta_e_2000']['mean'] - old['models']['fitted']['holdout']['delta_e_2000']['mean']) > 1e-12:
        raise AssertionError('V1 evaluation drifted')
    summary.update({'manifest': manifest, 'model_bundle_sha256': frozen_hash, 'implementation_sha256': artifact['implementation_sha256'],
        'optimizer': {name: {'runs': model['runs'], 'selected_start': model['selected_start']} for name, model in artifact['models'].items()},
        'environment': artifact['environment']})
    v1.write_json(out / 'summary.json', summary)
    error_rows = []
    for i, row in enumerate(rows):
        item = {'source_row': int(row), 'family': v1.family(c[i]),
                'role': 'original_calibration' if original_fit[i] else 'pair_family_cv' if pairs[i] else 'primary_multicolor_evaluation'}
        item.update({f'{name}_{key}': float(value[i]) for name, m in metrics.items() for key, value in m.items()})
        error_rows.append(item)
    write_csv(out / 'errors.csv', error_rows)
    diag_rows, _ = sensitivity(c, original_fit, primary, baseline)
    plots(out, rows, (multi, pairs), metrics, diag_rows)
    if v1.sha(model_path.read_bytes()) != frozen_hash: raise AssertionError('Evaluation modified the models')
    print(json.dumps({role: {name: {key: value[key] for key in ['count', 'spectral_rmse', 'delta_e_2000']}
        for name, value in summary[role].items()} for role in ['primary_multicolor16', 'pair_family_cv8', 'cross_fitted24']}, indent=2))


if __name__ == '__main__':
    main()
