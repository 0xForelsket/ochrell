"""Frozen recipe-group validation of the existing empirical model; no retuning."""
import os
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'

import argparse
import importlib.util
import json
import platform
import sys
from fractions import Fraction
from functools import reduce
from math import gcd, lcm
from pathlib import Path

import numpy as np
import scipy

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import measured_oils as v1
import measured_oils_chromatic as v3


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


empirical = module('frozen_empirical', ROOT / 'experiments/oil_parallel/interaction/run.py')
scalar = module('scalar_reference', ROOT / 'experiments/oil_parallel/validate_comparison.py')
SOURCE = ROOT / 'target/measured-oils/source/spectralDatasets.zip'
OLD = ROOT / 'target/measured-oils/parallel/interaction/frozen-models.json'
V1 = ROOT / 'target/measured-oils/v1/fitted-model.json'
DEFAULT = ROOT / 'target/measured-oils/grouped-ratios'
EXPECTED = [[60, 61, 62], [66, 67, 68], [69, 70], [71, 72], [84, 85],
            [86, 87], [112, 114, 115], [113], [172, 173], [174, 175], [176, 177]]


def ratio_key(recipe):
    chromatic = np.asarray(recipe, dtype=float)[:3]
    if not np.isfinite(chromatic).all() or (chromatic < 0).any() or chromatic.sum() <= 0:
        raise ValueError('Expected a positive chromatic amount')
    return tuple(np.round(chromatic / chromatic.sum(), 12))


def ratio_label(key):
    rational = [Fraction(float(x)).limit_denominator(10000) for x in key]
    denominator = lcm(*(x.denominator for x in rational))
    integers = [x.numerator * (denominator // x.denominator) for x in rational]
    common = reduce(gcd, integers)
    return ':'.join(str(x // common) for x in integers)


def design(rows, c, original):
    primary, pairs, multi, _ = v3.design(c, original)
    groups = {}
    for i in np.flatnonzero(~original):
        groups.setdefault(ratio_key(c[i]), []).append(i)
    folds = {}
    for key, indices in groups.items():
        test = np.zeros(len(c), dtype=bool)
        test[indices] = True
        train = primary & ~test
        name = f'ratio-{int(rows[indices[0]])}'
        folds[name] = {'train': train, 'test': test, 'ratio': ratio_label(key)}
        assert not (train & test).any() and (train[original]).all()
        assert all(ratio_key(row) != key for row in c[train] if row[:3].sum() > 0)
    assert [rows[f['test']].tolist() for f in folds.values()] == EXPECTED
    counts = np.sum([f['test'] for f in folds.values()], axis=0)
    np.testing.assert_array_equal(counts, (~original).astype(int))
    assert sum(f['train'].sum() == 28 for f in folds.values()) == 8
    assert sum(f['train'].sum() == 29 for f in folds.values()) == 3
    return primary, pairs, multi, folds


def manifest(rows, c, original):
    _, _, _, folds = design(rows, c, original)
    files = [HERE / 'PLAN.md', HERE / 'run.py', HERE / 'test_protocol.py',
             Path(empirical.__file__), Path(scalar.__file__), Path(v1.__file__),
             Path(v3.__file__), v1.CONFIG, ROOT / 'data/cie_380_780_1nm.csv',
             SOURCE, OLD, V1, ROOT / 'experiments/oil_parallel/interaction/summary.json',
             ROOT / 'results/measured-oils-v1/summary.json']
    return {'experiment': 'chromatic-ratio-groups-matched-training-pool',
            'status': 'exploratory; all assessment samples previously exposed',
            'hashes': {p.relative_to(ROOT).as_posix(): v1.sha(p.read_bytes()) for p in files},
            'settings': json.loads(v1.CONFIG.read_text()),
            'anchor_rows': rows[original].tolist(),
            'folds': {name: {'chromatic_ratio_Y_R_B': f['ratio'],
                            'train_rows': rows[f['train']].tolist(),
                            'test_rows': rows[f['test']].tolist()} for name, f in folds.items()}}


def fit_training(c, measured, mask, settings):
    # The fitting implementation never receives arrays for excluded rows.
    return empirical.fit(c[mask].copy(), measured[mask].copy(), settings)


def numerical_difference(actual, expected):
    differences = [abs(actual[key][stat] - expected[key][stat])
                   for key in ('spectral_rmse', 'spectral_mae', 'spectral_max_abs', 'delta_e_2000')
                   for stat in ('mean', 'median', 'p95', 'max')]
    assert actual['count'] == expected['count']
    result = max(differences)
    if result > 1e-10:
        raise AssertionError(f'Aggregate reproduction drift: {result}')
    return result


def baseline_check(c, measured, original, multi):
    old = json.loads(OLD.read_text())['models']['primary29']
    summary = json.loads((ROOT / 'experiments/oil_parallel/interaction/summary.json').read_text())
    _, _, lab = v1.colorimetry()
    checks = {}
    for label, prediction in [('v3', v3.predicted(c, old['base'])),
                              ('interaction', empirical.predict(c, old))]:
        stats = v1.summarize(v1.errors(measured, prediction, lab), multi)
        checks[label] = numerical_difference(stats, summary['primary16'][label])
    base = json.loads(V1.read_text())
    stats = v1.summarize(v1.errors(measured, v3.predicted(c, base), lab), ~original)
    previous = json.loads((ROOT / 'results/measured-oils-v1/summary.json').read_text())
    checks['v1_24'] = numerical_difference(stats, previous['models']['fitted']['holdout'])
    return {'aggregate_statistics_checked': 48, 'max_abs_difference': max(checks.values())}


def fitted_bundle(out, current):
    path = out / 'frozen-models.json'
    bundle = json.loads(path.read_text())
    if bundle['manifest'] != current:
        raise ValueError('Frozen provenance differs')
    return bundle, v1.sha(path.read_bytes())


def assess(out, rows, c, measured, original, folds, bundle, bundle_hash):
    _, pairs, multi, _ = v3.design(c, original)
    # Pure values are placeholders on unscored anchor rows only.
    predictions = {name: measured.copy() for name in ('km', 'interaction')}
    for name, f in folds.items():
        model = bundle['models'][bundle['fold_models'][name]]
        predictions['km'][f['test']] = v3.predicted(c[f['test']], model['base'])
        predictions['interaction'][f['test']] = empirical.predict(c[f['test']], model)
    predictions['v1_reference'] = v3.predicted(c, json.loads(V1.read_text()))
    _, _, lab = v1.colorimetry()
    metrics = {name: v1.errors(measured, p, lab) for name, p in predictions.items()}
    masks = {'multicolor16': multi, 'parent_pairs8': pairs, 'pooled24': ~original}
    summary = {'status': bundle['manifest']['status'], 'model_bundle_sha256': bundle_hash,
               'manifest': bundle['manifest'], 'environment': bundle['environment'],
               'unique_fits': len(bundle['models']),
               'subsets': {role: {name: v1.summarize(m, mask) for name, m in metrics.items()}
                           for role, mask in masks.items()},
               'groups': {name: {'ratio': f['ratio'], 'model': bundle['fold_models'][name],
                                'train_count': int(f['train'].sum()), 'test_rows': rows[f['test']].tolist(),
                                'metrics': {label: v1.summarize(m, f['test']) for label, m in metrics.items()}}
                          for name, f in folds.items()},
               'optimizer': {key: {'base': m['base']['runs'], 'selected_start': m['base']['selected_start'],
                                   'correction': m['optimizer']} for key, m in bundle['models'].items()}}
    summary['equal_group_macro_mean'] = {name: {key: float(np.mean([
        group['metrics'][name][key]['mean'] for group in summary['groups'].values()]))
        for key in ('delta_e_2000', 'spectral_rmse')} for name in metrics}
    old = json.loads((ROOT / 'experiments/oil_parallel/interaction/summary.json').read_text())
    summary['previous_parent_available16'] = {name: old['primary16'][name] for name in ('v3', 'interaction')}
    summary['changes'] = {}
    for role, mask in masks.items():
        delta = metrics['interaction']['delta_e_2000'] - metrics['km']['delta_e_2000']
        summary['changes'][role] = {'color_improved': int(np.sum(delta[mask] < -1e-12)),
                                   'color_worsened': int(np.sum(delta[mask] > 1e-12)),
                                   'color_tied': int(np.sum(abs(delta[mask]) <= 1e-12)),
                                   'spectral_rmse_improved': int(np.sum((metrics['interaction']['spectral_rmse'] < metrics['km']['spectral_rmse'])[mask]))}
    h = summary['subsets']['multicolor16']['interaction']
    values = {'mean_spectral_rmse': h['spectral_rmse']['mean'], 'p95_spectral_rmse': h['spectral_rmse']['p95'],
              'mean_delta_e_2000': h['delta_e_2000']['mean'], 'p95_delta_e_2000': h['delta_e_2000']['p95'],
              'max_delta_e_2000': h['delta_e_2000']['max']}
    limits = bundle['manifest']['settings']['quality_screen']
    summary['screens_multicolor16'] = {key: {'actual': value, 'limit': limits[key], 'passed': value <= limits[key]}
                                       for key, value in values.items()}
    records = []
    for name, f in folds.items():
        for i in np.flatnonzero(f['test']):
            rec = {'source_row': int(rows[i]), 'group': name, 'ratio_Y_R_B': f['ratio'],
                   'paint_family': v1.family(c[i]), 'role': 'parent_pair' if pairs[i] else 'multicolor'}
            rec.update({f'{label}_{key}': float(values[i]) for label, m in metrics.items() for key, values in m.items()})
            records.append(rec)
    records.sort(key=lambda r: r['source_row'])
    for destination in (out, HERE):
        v1.write_json(destination / 'summary.json', summary)
        v3.write_csv(destination / 'errors.csv', records)
    return summary


def verify(rows, c, measured, original, folds, bundle):
    result = {'unique_fits': len(bundle['models']), 'pure_max_abs': 0.0,
              'independent_scalar_max_abs': 0.0, 'perturbed_target_coefficient_max_abs': 0.0,
              'finite_bounded_all_models_all45': True, 'folds': {}}
    pure = (c > 0).sum(1) == 1
    checked = set()
    for name, f in folds.items():
        model_id = bundle['fold_models'][name]
        if model_id in checked:
            continue
        checked.add(model_id)
        model = bundle['models'][model_id]
        vector = empirical.predict(c, model)
        independent = np.array([[scalar.interaction(recipe, model, band) for band in range(31)] for recipe in c])
        error = float(abs(vector - independent).max())
        np.testing.assert_allclose(vector, independent, atol=1e-12, rtol=0)
        assert np.isfinite(vector).all() and (vector > 0).all() and (vector < 1).all()
        pure_error = float(abs(vector[pure] - measured[pure]).max())
        assert pure_error < 1e-12
        altered = measured.copy()
        altered[~f['train']] = np.random.default_rng(713).uniform(.02, .98, altered[~f['train']].shape)
        again = fit_training(c, altered, f['train'], bundle['manifest']['settings'])
        np.testing.assert_array_equal(again['base']['log_relative_s'], model['base']['log_relative_s'])
        np.testing.assert_array_equal(again['theta'], model['theta'])
        result['independent_scalar_max_abs'] = max(result['independent_scalar_max_abs'], error)
        result['pure_max_abs'] = max(result['pure_max_abs'], pure_error)
        result['folds'][model_id] = {'scalar_max_abs': error, 'pure_max_abs': pure_error,
                                   'nontraining_target_perturbation_coefficient_change': 0.0}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['prepare', 'fit', 'evaluate', 'verify'])
    parser.add_argument('--out', type=Path, default=DEFAULT)
    args = parser.parse_args()
    out = v1.research_directory(args.out)
    rows, c, measured, original = v1.load_source(SOURCE)
    _, _, multi, folds = design(rows, c, original)
    current = manifest(rows, c, original)
    prepared = out / 'partition.json'
    frozen = out / 'frozen-models.json'
    if args.phase == 'prepare':
        if frozen.exists():
            raise ValueError('Frozen models exist; use a fresh output directory')
        checks = baseline_check(c, measured, original, multi)
        v1.write_json(prepared, current)
        v1.write_json(HERE / 'baseline-check.json', checks)
        print(json.dumps({'folds': current['folds'], 'baseline': checks}, indent=2))
        return
    if json.loads(prepared.read_text()) != current:
        raise ValueError('Prepared provenance differs')
    if args.phase == 'fit':
        if frozen.exists():
            raise ValueError('Refusing frozen-model overwrite')
        models, fold_models, known = {}, {}, {}
        for name, f in folds.items():
            key = tuple(rows[f['train']])
            if key not in known:
                known[key] = name
                models[name] = fit_training(c, measured, f['train'], current['settings'])
                print(name, 'fit rows', len(key), 'correction', models[name]['optimizer'], flush=True)
            fold_models[name] = known[key]
        assert len(models) == 9
        v1.write_json(frozen, {'manifest': current, 'models': models, 'fold_models': fold_models,
                              'environment': {'python': sys.version, 'numpy': np.__version__,
                                              'scipy': scipy.__version__, 'platform': platform.platform()}})
        print('Frozen bundle SHA-256:', v1.sha(frozen.read_bytes()))
        return
    bundle, bundle_hash = fitted_bundle(out, current)
    if args.phase == 'evaluate':
        summary = assess(out, rows, c, measured, original, folds, bundle, bundle_hash)
        print(json.dumps({'subsets': summary['subsets'], 'macro': summary['equal_group_macro_mean']}, indent=2))
    else:
        checks = verify(rows, c, measured, original, folds, bundle)
        v1.write_json(out / 'verification.json', checks)
        v1.write_json(HERE / 'verification.json', checks)
        print(json.dumps(checks, indent=2))
    assert v1.sha(frozen.read_bytes()) == bundle_hash


if __name__ == '__main__':
    main()
