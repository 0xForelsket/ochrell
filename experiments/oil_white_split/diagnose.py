"""Attribute frozen errors; no fitting, coefficient changes, or label search."""
import os
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
import csv
import importlib.util
import itertools
import json
import math
from pathlib import Path

import numpy as np
from scipy.special import expit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location('reconstructed', ROOT/'experiments/oil_reconstructed/run.py')
study = importlib.util.module_from_spec(spec)
spec.loader.exec_module(study)
old = study.old
PAIRS = old.empirical.PAIRS
PAIR_NAMES = ['YCBW'[a]+'YCBW'[b] for a, b in PAIRS]
WHITE = np.array([3 in p for p in PAIRS])
OUT = ROOT/'target/measured-oils/white-split-diagnosis'
BUNDLE = study.DEFAULT/'frozen-models.json'


def prohibited_fit(*args, **kwargs):
    raise RuntimeError('Refitting is prohibited in this diagnosis')


old.empirical.fit = prohibited_fit
old.v1.fit_model = prohibited_fit


def compose(base, shift):
    return np.where(shift == 0, base, expit(np.log(base)-np.log1p(-base)+shift))


def decompose(c, model):
    c, features = old.empirical.features(c)
    weights = np.array([4*c[:, a]*c[:, b] for a, b in PAIRS]).T
    curves = old.empirical.B @ np.array(model['theta']).reshape(6, 4).T
    terms = weights[:, None, :]*curves[None, :, :]
    np.testing.assert_allclose(terms.sum(2), features @ model['theta'], rtol=0, atol=5e-16)
    km = old.v3.predicted(c, model['base'])
    return km, weights, terms


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    raw = BUNDLE.read_bytes()
    assert study.sha(raw) == '8090dd57ce49b584fcae15cdb85eafbe942a4181c97f53b27a95d22265bc1ced'
    bundle = json.loads(raw)
    saved = json.loads((ROOT/'experiments/oil_reconstructed/summary.json').read_text(encoding='utf-8'))
    assert saved['model_bundle_sha256'] == study.sha(raw)
    manifest = bundle['manifest']
    for group in [manifest['hashes'], manifest['original_method']['hashes']]:
        for name, digest in group.items():
            assert study.sha((ROOT/name).read_bytes()) == digest, name
    variants_path = ROOT/'experiments/oil_reconstructed/variants.json'
    assert study.sha(variants_path.read_bytes()) == manifest['variants_sha256']
    variants = json.loads(variants_path.read_text(encoding='utf-8'))
    data = study.inputs()
    names, c, nominal = data[5:8]
    anchors, pairs, multi, pool, folds = study.design(data)
    jobs, plans = study.jobs_for(data, variants, folds, pool)
    assert plans == bundle['variants']
    _, features = old.empirical.features(c)
    training_activity = (features[pool].reshape(pool.sum(), 31, 6, 4) != 0).any(axis=(1, 3))
    assert (training_activity.sum(1) <= 1).all()
    x = features[pool].reshape(-1, 24)
    gram = x.T @ x
    off_block = np.fromfunction(lambda i, j: i//4 != j//4, (24, 24))
    assert abs(gram[off_block]).max() == 0
    lab, _ = old.colorimetry()
    previous = {(r['variant'], r['sample']): r for r in csv.DictReader((ROOT/'experiments/oil_reconstructed/errors.csv').open(newline=''))}
    records, components, calibration, coverage, regions, spectra = [], [], [], [], [], {}
    checks = {'saved_error_max_abs': 0.0, 'scalar_max_abs': 0.0, 'recombination_max_abs': 0.0,
              'shapley_sum_max_abs': 0.0, 'mse_identity_max_abs': 0.0, 'pure_max_abs': 0.0,
              'calibration_off_pair_gram_max_abs': float(abs(gram[off_block]).max()),
              'all_counterfactuals_finite_bounded': True, 'no_fitting_calls': True}

    for model_id, job in jobs.items():
        model = bundle['models'][model_id]
        train = job['train']; measured = job['measured']
        km, weights, terms = decompose(c, model)
        full = compose(km, terms.sum(2))
        metrics = {k: old.v1.errors(measured, p, lab) for k, p in [('km', km), ('full', full)]}
        for i in np.flatnonzero(train):
            active = np.flatnonzero(weights[i])
            assert len(active) <= 1
            calibration.append({'model': model_id, 'sample': str(names[i]), 'pair': PAIR_NAMES[active[0]] if len(active) else 'pure',
                **{k+'_'+metric: float(value[i]) for k, errors in metrics.items() for metric, value in errors.items()}})
        pure = (c > 0).sum(1) == 1
        checks['pure_max_abs'] = max(checks['pure_max_abs'], float(abs(full[pure]-measured[pure]).max()))

    for variant in variants['variants']:
        variant_id = variant['id']
        measured = data[8][np.array(variant['mapping'])[data[4]]]
        for group, fold in folds.items():
            model_id = plans[variant_id]['fold_models'][group]
            model = bundle['models'][model_id]
            km, weights, terms = decompose(c, model)
            full = compose(km, terms.sum(2))
            replay = old.empirical.predict(c, model)
            checks['recombination_max_abs'] = max(checks['recombination_max_abs'], float(abs(full-replay).max()))
            for i in np.flatnonzero(fold['test']):
                active = np.flatnonzero(weights[i]).tolist()
                group_kind = 'pair' if pairs[i] else 'white_ternary' if c[i, 3] else 'chromatic_ternary'
                predictions = {'km': km[i], 'full': full[i],
                    'chromatic_only': compose(km[i], terms[i][:, ~WHITE].sum(1)),
                    'white_only': compose(km[i], terms[i][:, WHITE].sum(1))}
                for p in range(6):
                    predictions['only_'+PAIR_NAMES[p]] = compose(km[i], terms[i, :, p])
                    predictions['without_'+PAIR_NAMES[p]] = compose(km[i], terms[i].sum(1)-terms[i, :, p])
                    if p not in active:
                        np.testing.assert_array_equal(predictions['without_'+PAIR_NAMES[p]], full[i])
                for value in predictions.values():
                    assert np.isfinite(value).all() and (value > 0).all() and (value < 1).all()
                scalar = np.array([old.scalar.interaction(c[i], model, b) for b in range(31)])
                checks['scalar_max_abs'] = max(checks['scalar_max_abs'], float(abs(scalar-full[i]).max()))
                metrics = {k: old.v1.errors(measured[i:i+1], p[None], lab) for k, p in predictions.items()}
                for prefix, saved_prefix in [('km', 'km'), ('full', 'empirical')]:
                    for metric, value in metrics[prefix].items():
                        checks['saved_error_max_abs'] = max(checks['saved_error_max_abs'], abs(float(value[0])-float(previous[variant_id, str(names[i])][saved_prefix+'_'+metric])))
                d = full[i]-km[i]; needed = measured[i]-km[i]
                energy = float(np.mean(d*d)); cross = float(np.mean(d*needed))
                identity = energy-2*cross
                direct = float(np.mean((full[i]-measured[i])**2)-np.mean((km[i]-measured[i])**2))
                checks['mse_identity_max_abs'] = max(checks['mse_identity_max_abs'], abs(identity-direct))
                alpha = cross/energy if energy else None
                cos = float(np.dot(d, needed)/(np.linalg.norm(d)*np.linalg.norm(needed))) if energy and np.linalg.norm(needed) else None
                rec = {'variant': variant_id, 'sample': str(names[i]), 'group': group, 'kind': group_kind,
                       'model': model_id, 'white_fraction': float(c[i, 3]), 'pair_weight_sum': float(weights[i].sum()),
                       'correction_rms': float(np.sqrt(energy)), 'needed_rms': float(np.sqrt(np.mean(needed**2))),
                       'correction_projection_alpha': alpha, 'correction_cosine': cos, 'correction_energy': energy,
                       'twice_alignment': 2*cross, 'mse_change': direct,
                       'diagnosis': 'zero' if alpha is None else 'opposite_direction' if alpha <= 0 else 'overshoot' if alpha < .5 else 'improves',
                       **{k+'_'+metric: float(value[0]) for k, errors in metrics.items() for metric, value in errors.items()}}
                records.append(rec)
                if multi[i]: assert weights[i].sum() == 1.25
                regional_sum = 0.0
                for lo, hi in [(440, 500), (510, 590), (600, 740)]:
                    band = (old.GRID >= lo) & (old.GRID <= hi)
                    contribution = float(np.sum((d*d-2*d*needed)[band])/31)
                    regional_sum += contribution
                    regions.append({'variant': variant_id, 'sample': str(names[i]), 'kind': group_kind,
                        'lo_nm': lo, 'hi_nm': hi, 'contribution_to_total_MSE_change': contribution,
                        'mean_needed_displacement': float(needed[band].mean()),
                        'mean_actual_displacement': float(d[band].mean())})
                assert abs(regional_sum-direct) < 1e-12

                subset_mse = {}
                for bits in itertools.product([0, 1], repeat=len(active)):
                    included = frozenset(p for p, bit in zip(active, bits) if bit)
                    shift = terms[i][:, sorted(included)].sum(1) if included else np.zeros(31)
                    prediction = compose(km[i], shift)
                    subset_mse[included] = float(np.mean((prediction-measured[i])**2))
                shapleys = []
                for p in active:
                    value = 0.0
                    for subset, mse in subset_mse.items():
                        if p in subset: continue
                        k = len(subset); n = len(active)
                        factor = math.factorial(k)*math.factorial(n-k-1)/math.factorial(n)
                        value += factor*(mse-subset_mse[subset | {p}])
                    shapleys.append(value)
                    components.append({'variant': variant_id, 'sample': str(names[i]), 'kind': group_kind, 'pair': PAIR_NAMES[p],
                        'weight': float(weights[i, p]), 'logit_shift_rms': float(np.sqrt(np.mean(terms[i, :, p]**2))),
                        'logit_shift_mean': float(terms[i, :, p].mean()), 'mse_reduction_shapley': value,
                        'only_pair_rmse': rec['only_'+PAIR_NAMES[p]+'_spectral_rmse'],
                        'without_pair_rmse': rec['without_'+PAIR_NAMES[p]+'_spectral_rmse']})
                    a, b = PAIRS[p]
                    train_pair = fold['train'] & (c[:, a] > 0) & (c[:, b] > 0)
                    target_ratio = nominal[i, a]/(nominal[i, a]+nominal[i, b])
                    ratios = nominal[train_pair, a]/(nominal[train_pair, a]+nominal[train_pair, b])
                    coverage.append({'variant': variant_id, 'sample': str(names[i]), 'pair': PAIR_NAMES[p],
                        'nominal_first_fraction_within_pair': float(target_ratio),
                        'same_nominal_ratio_in_calibration': bool(np.isclose(ratios, target_ratio, rtol=0, atol=1e-12).any()),
                        'calibration_labels': ','.join(names[train_pair]),
                        'calibration_first_fractions': ','.join(f'{x:.12g}' for x in ratios),
                        'calibration_rows': int(train_pair.sum())})
                checks['shapley_sum_max_abs'] = max(checks['shapley_sum_max_abs'], abs(sum(shapleys)+direct))
                if variant_id == 'base':
                    spectra[str(names[i])+'_measured'] = measured[i]
                    spectra[str(names[i])+'_terms'] = terms[i]
                    for k, value in predictions.items(): spectra[str(names[i])+'_'+k] = value

    assert len(records) == len(previous) == 147
    assert len({(r['variant'], r['sample']) for r in records}) == 147
    for key in ['recombination_max_abs', 'scalar_max_abs', 'pure_max_abs', 'mse_identity_max_abs', 'shapley_sum_max_abs']:
        assert checks[key] < 1e-12, key
    assert checks['saved_error_max_abs'] < 1e-11
    for filename, items in [('components.csv', components), ('observations.csv', records), ('calibration.csv', calibration), ('coverage.csv', coverage), ('spectral-regions.csv', regions)]:
        old.v3.write_csv(HERE/filename, items)
    np.savez_compressed(OUT/'spectra.npz', **spectra)
    grouped = {}
    for variant in variants['variants']:
        key = variant['id']; grouped[key] = {}
        for kind in ['white_ternary', 'chromatic_ternary', 'pair']:
            selected = [r for r in records if r['variant'] == key and r['kind'] == kind]
            grouped[key][kind] = {'samples': [r['sample'] for r in selected], 'count': len(selected),
                'means': {p: {metric: float(np.mean([r[p+'_'+metric] for r in selected]))
                             for metric in ['spectral_rmse', 'delta_e_2000']}
                          for p in ['km', 'full', 'chromatic_only', 'white_only']},
                'diagnoses': {label: sum(r['diagnosis'] == label for r in selected) for label in ['opposite_direction', 'overshoot', 'improves']},
                'shapley_MSE_reduction_sum': {p: float(sum(r['mse_reduction_shapley'] for r in components if r['variant'] == key and r['kind'] == kind and r['pair'] == p)) for p in PAIR_NAMES}}
    hashes = {p.relative_to(ROOT).as_posix(): study.sha(p.read_bytes()) for p in
              [Path(__file__), HERE/'PLAN.md', BUNDLE, ROOT/'experiments/oil_reconstructed/summary.json',
               ROOT/'experiments/oil_reconstructed/errors.csv', variants_path]}
    result = {'status': 'Post-evaluation attribution of frozen models; no fitted revision or new validation.',
              'hashes': hashes, 'upstream_manifest': manifest, 'checks': checks, 'groups': grouped,
              'training': {'unique_models': len(jobs), 'pool_count': int(pool.sum()), 'pure': int(((c[pool]>0).sum(1)==1).sum()),
                           'binary': int(((c[pool]>0).sum(1)==2).sum()), 'ternary': 0,
                           'max_active_pairs_per_training_row': int(training_activity.sum(1).max())}}
    study.write(HERE/'summary.json', result)
    assert BUNDLE.read_bytes() == raw
    for name, digest in hashes.items(): assert study.sha((ROOT/name).read_bytes()) == digest
    print(json.dumps({'checks': checks, 'training': result['training'], 'base': grouped['base']}, indent=2))


if __name__ == '__main__': main()
