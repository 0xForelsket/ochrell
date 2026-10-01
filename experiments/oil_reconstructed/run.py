"""Frozen external method with a separate inferred-map loader and sensitivity study."""
import os
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'

import argparse
import hashlib
import importlib.util
import itertools
import json
import platform
from pathlib import Path

import numpy as np
import scipy
from scipy.optimize import Bounds, LinearConstraint, milp

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RECOVERY = ROOT/'experiments/oil_source_recovery'
DEFAULT = ROOT/'target/measured-oils/grillini-reconstructed'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


old = module('original_external', ROOT/'experiments/oil_external/run.py')
trace = module('original_source_trace', ROOT/'experiments/oil_source_trace/trace.py')
write = old.v1.write_json
sha = old.v1.sha


def inputs():
    labels, order, amounts, nominal, nm, raw, _ = old.audit.load()
    mapping = json.loads((RECOVERY/'mapping.json').read_text())
    assert sha((RECOVERY/'mapping.json').read_bytes()) == '9e31ac91fcaa334b8bc56e9d3ae501d7ebe79de932ca066dba84ba276f9d6a22'
    assert mapping['canonical_label_order'] == labels
    assert mapping['source_archive_sha256'] == old.audit.EXPECTED_SHA
    keep = (amounts[:, [order.index(k) for k in ['V', 'O', 'G']]] == 0).all(1)
    columns = [order.index(k) for k in ['Y', 'C', 'B', 'W']]
    names = np.array(labels)[keep]
    c, intended = amounts[keep][:, columns], nominal[keep][:, columns]
    assert nm[10] <= old.GRID.min() and nm[-11] >= old.GRID.max()
    interpolated = np.array([np.interp(old.GRID, nm[10:-10], r[10:-10]) for r in raw])
    assert interpolated.shape == (175, 31) and np.isfinite(interpolated).all()
    original = old.load()
    for x, y in zip((names, c, intended, interpolated[keep]), original):
        np.testing.assert_array_equal(x, y)
    return labels, order, amounts, raw[:, 10:-10], keep, names, c, intended, interpolated


def enumerate_variants(data):
    labels, order, amounts, spectra, keep, *_ = data
    base = np.array(json.loads((RECOVERY/'mapping.json').read_text())['canonical_to_source'])
    audit = json.loads((RECOVERY/'pair-ambiguity-audit.json').read_text())
    assert audit['base_mapping'] == base.tolist()
    ref = json.loads((RECOVERY/'figure6-vector-ticks.json').read_text())
    target = np.array(list(ref['MSE'].values()))
    pure = np.array([labels.index(k) for k in order])
    mixture = (amounts > 0).sum(1) > 1
    predicted = np.array(list(trace.models(amounts, spectra[base[pure]]).values()))

    def stats(p):
        assert sorted(p.tolist()) == list(range(175))
        np.testing.assert_array_equal(p[pure], base[pure])
        errors = np.mean((predicted-spectra[p][None])**2, axis=2)
        assert np.max(errors[:, ~mixture]) < 1e-25
        errors[:, ~mixture] = 0
        return (errors[:, mixture].mean(1),
                np.bincount(errors.argmin(0), minlength=7),
                np.bincount(errors.argmax(0), minlength=7))

    # Build additive pair contributions without imposing the pure constraint on
    # forbidden trial flips; those variables are fixed to zero in the solver.
    mean, best, worst = stats(base)
    ds, db, dw = [], [], []
    upper = np.ones(87)
    for k in range(87):
        if any(i in [2*k, 2*k+1] for i in pure):
            upper[k] = 0
            ds.append(np.zeros(7)); db.append(np.zeros(7)); dw.append(np.zeros(7))
            continue
        p = base.copy(); p[2*k:2*k+2] = p[2*k:2*k+2][::-1]
        a, b, w = stats(p)
        ds.append(a-mean); db.append(b-best); dw.append(w-worst)
    matrix = np.vstack([np.array(ds).T*1e6, np.array(db).T, np.array(dw).T])
    variants = [{'id': 'base', 'mapping': base.tolist(), 'tolerances': [], 'witnesses': [], 'changed_subset_labels': []}]
    known = {tuple(base[keep]): 0}
    cases = []
    for case in audit['cases']:
        assert not case['unresolved_solver_cases'] and case['tested_pairs'] == 81
        tolerance = case['tolerance']
        mutable = [x['pair'] for x in case['ambiguous_pairs']]
        selected = [k for k in mutable if keep[2*k:2*k+2].any()]
        # Pairs outside the audited mutable set cannot change at this tolerance.
        ub = np.zeros(87); ub[mutable] = upper[mutable]
        lower_constraints = np.r_[(target-mean-tolerance)*1e6, np.array(ref['counts']['best'])-best, np.array(ref['counts']['worst'])-worst]
        upper_constraints = np.r_[(target-mean+tolerance)*1e6, np.array(ref['counts']['best'])-best, np.array(ref['counts']['worst'])-worst]
        constraint = LinearConstraint(matrix, lower_constraints, upper_constraints)
        outcomes = []
        for bits in itertools.product([0, 1], repeat=len(selected)):
            lb = np.zeros(87); hi = ub.copy()
            lb[selected] = bits; hi[selected] = bits
            sol = milp(np.zeros(87), integrality=np.ones(87), bounds=Bounds(lb, hi),
                       constraints=constraint, options={'time_limit': 60})
            if sol.x is None:
                assert sol.status == 2, f'Unresolved mapping feasibility: {sol.message}'
                outcomes.append({'bits': list(bits), 'feasible': False})
                continue
            assert np.max(abs(sol.x-np.round(sol.x))) < 1e-6
            p = base.copy()
            for k in np.flatnonzero(sol.x > .5):
                p[2*k:2*k+2] = p[2*k:2*k+2][::-1]
            a, b, w = stats(p)
            difference = float(abs(a-target).max())
            assert difference <= tolerance+1e-12
            assert b.tolist() == ref['counts']['best'] and w.tolist() == ref['counts']['worst']
            key = tuple(p[keep])
            if key not in known:
                known[key] = len(variants)
                variants.append({'id': f'variant-{len(variants):02}', 'mapping': p.tolist(),
                                 'tolerances': [], 'witnesses': [],
                                 'changed_subset_labels': np.array(labels)[keep & (p != base)].tolist()})
            variant = variants[known[key]]
            variant['tolerances'].append(tolerance)
            variant['witnesses'].append({'tolerance': tolerance, 'mapping': p.tolist(),
                                         'maximum_absolute_MSE_difference': difference})
            outcomes.append({'bits': list(bits), 'feasible': True, 'variant': variant['id']})
        cases.append({'tolerance': tolerance, 'selected_mutable_pairs': selected, 'outcomes': outcomes})
        print('mapping enumeration', tolerance, 'feasible', sum(x['feasible'] for x in outcomes), '/', len(outcomes), flush=True)
    return {'scope': 'All distinct Y/C/B/W assignments within the previously audited paired-scan family; fixed pures and counts.',
            'cases': cases, 'variants': variants}


def provenance(names, folds):
    previous = json.loads((ROOT/'experiments/oil_external/summary.json').read_text())['manifest']
    current = old.provenance(names, folds)
    assert previous == current, 'Original method, settings, source or partitions changed'
    files = [Path(__file__), HERE/'PLAN.md', RECOVERY/'mapping.json', RECOVERY/'pair-ambiguity-audit.json',
             RECOVERY/'figure6-vector-ticks.json', Path(trace.__file__)]
    return {'original_method': current, 'hashes': {p.relative_to(ROOT).as_posix(): sha(p.read_bytes()) for p in files},
            'settings': current['settings'], 'environment': {'python': platform.python_version(), 'numpy': np.__version__,
             'scipy': scipy.__version__, 'colour': old.colour.__version__}}


def design(data):
    return old.design(data[5], data[6], data[7])


def jobs_for(data, variants, folds, pool):
    _, _, _, _, keep, names, c, _, interpolated = data
    jobs, plans = {}, {}
    for v in variants['variants']:
        measured = interpolated[np.array(v['mapping'])[keep]]
        model_ids = {}; primary = None
        for group, f in folds.items():
            mask = f['train']
            # Cache identity includes only calibration inputs, never held-out data.
            h = hashlib.sha256(json.dumps(names[mask].tolist()).encode())
            h.update(c[mask].tobytes()); h.update(measured[mask].tobytes())
            key = h.hexdigest()
            if key not in jobs:
                jobs[key] = {'variant': v['id'], 'group': group, 'train': mask,
                             'measured': measured, 'train_labels': names[mask].tolist()}
            else:
                np.testing.assert_array_equal(jobs[key]['measured'][mask], measured[mask])
                np.testing.assert_array_equal(jobs[key]['train'], mask)
            model_ids[group] = key
            if np.array_equal(mask, pool): primary = key
        assert primary is not None and len(set(model_ids.values())) == 10
        plans[v['id']] = {'fold_models': model_ids, 'primary_model': primary}
    return jobs, plans


def fit_one(key, c, measured, settings):
    model = old.empirical.fit(c.copy(), measured.copy(), settings)
    return key, model


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=['prepare', 'fit', 'verify', 'evaluate'])
    parser.add_argument('--out', type=Path, default=DEFAULT)
    parser.add_argument('--workers', type=int, default=3)
    args = parser.parse_args()
    out = old.v1.research_directory(args.out)
    data = inputs(); names, c = data[5:7]
    anchors, pairs, multi, pool, folds = design(data)
    manifest = provenance(names, folds)
    partition, variant_file, frozen = out/'partition.json', out/'variants.json', out/'frozen-models.json'
    if args.phase == 'prepare':
        assert not partition.exists() and not frozen.exists(), 'Refusing preparation overwrite'
        variants = enumerate_variants(data)
        write(variant_file, variants)
        manifest['variants_sha256'] = sha(variant_file.read_bytes())
        write(partition, manifest)
        write(HERE/'variants.json', variants)
        jobs, _ = jobs_for(data, variants, folds, pool)
        print('Prepared', len(variants['variants']), 'subset mappings and', len(jobs), 'unique calibration sets', flush=True)
        return
    manifest['variants_sha256'] = sha(variant_file.read_bytes())
    assert json.loads(partition.read_text()) == manifest
    variants = json.loads(variant_file.read_text())
    jobs, plans = jobs_for(data, variants, folds, pool)
    if args.phase == 'fit':
        from concurrent.futures import ProcessPoolExecutor, as_completed
        assert not frozen.exists(), 'Refusing frozen model overwrite'
        models = {}
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            pending = {executor.submit(fit_one, k, c[j['train']], j['measured'][j['train']], manifest['settings']): k for k, j in jobs.items()}
            for future in as_completed(pending):
                k, model = future.result(); models[k] = model
                print('fit', len(models), '/', len(jobs), jobs[k]['variant'], jobs[k]['group'], 'base nfev', [r['nfev'] for r in model['base']['runs']], flush=True)
        write(frozen, {'manifest': manifest, 'models': {k: models[k] for k in sorted(models)}, 'variants': plans})
        print('Frozen SHA256', sha(frozen.read_bytes()), flush=True)
        return
    raw = frozen.read_bytes(); bundle = json.loads(raw)
    assert bundle['manifest'] == manifest and bundle['variants'] == plans
    assert set(bundle['models']) == set(jobs)
    if args.phase == 'verify':
        from concurrent.futures import ProcessPoolExecutor, as_completed
        scalar_error = pure_error = 0.0
        pure = (c > 0).sum(1) == 1
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            pending = {}
            for k, j in jobs.items():
                model = bundle['models'][k]
                predicted = old.empirical.predict(c, model)
                reference = np.array([[old.scalar.interaction(recipe, model, b) for b in range(31)] for recipe in c])
                scalar_error = max(scalar_error, float(abs(predicted-reference).max()))
                pure_error = max(pure_error, float(abs(predicted[pure]-j['measured'][pure]).max()))
                assert np.isfinite(predicted).all() and (predicted > 0).all() and (predicted < 1).all()
                altered = j['measured'].copy()
                altered[~j['train']] = np.random.default_rng(309).uniform(.02, .98, altered[~j['train']].shape)
                pending[executor.submit(fit_one, k, c[j['train']], altered[j['train']], manifest['settings'])] = k
            done = 0
            for future in as_completed(pending):
                k, again = future.result(); original = bundle['models'][k]
                for field in ['theta', 'active']:
                    np.testing.assert_array_equal(again[field], original[field])
                for field in ['q', 'log_relative_s', 'K', 'S']:
                    np.testing.assert_array_equal(again['base'][field], original['base'][field])
                done += 1
                print('verified perturbation refit', done, '/', len(jobs), flush=True)
        assert scalar_error < 1e-12 and pure_error < 1e-12
        result = {'manifest': manifest, 'model_bundle_sha256': sha(raw), 'unique_fits': len(jobs),
                  'subset_mappings': len(variants['variants']), 'scalar_max_abs': scalar_error, 'pure_max_abs': pure_error,
                  'excluded_target_perturbation_coefficient_change': 0, 'finite_bounded_all34_all_models': True}
        write(out/'verification.json', result); write(HERE/'verification.json', result)
        print(json.dumps({k: v for k, v in result.items() if k != 'manifest'}, indent=2))
    else:
        verification = json.loads((out/'verification.json').read_text())
        assert verification['manifest'] == manifest and verification['model_bundle_sha256'] == sha(raw)
        results, records = {}, []
        for v in variants['variants']:
            measured = data[8][np.array(v['mapping'])[data[4]]]
            view = {'manifest': manifest, 'models': bundle['models'], **plans[v['id']]}
            result, rows = old.evaluate(names, c, measured, multi, pairs, pool, folds, view)
            result.pop('manifest'); result.pop('optimizer')
            results[v['id']] = {**result, 'tolerances': v['tolerances'], 'changed_subset_labels': v['changed_subset_labels']}
            records.extend({'variant': v['id'], **r} for r in rows)
        ranges = {}
        for tolerance in [2e-6, 5e-6, 1e-5]:
            subset = {k: r for k, r in results.items() if tolerance in r['tolerances']}
            roles = {}
            for role in ['ternary12', 'pairs9', 'pooled21']:
                values = []
                for k, r in subset.items():
                    km = r['grouped'][role]['km']['spectral_rmse']['mean']
                    empirical = r['grouped'][role]['empirical']['spectral_rmse']['mean']
                    values.append({'variant': k, 'km': km, 'empirical': empirical, 'difference': empirical-km,
                                   'improvement_percent': 100*(km-empirical)/km})
                roles[role] = {'values': values, 'ranges': {metric: [min(x[metric] for x in values), max(x[metric] for x in values)]
                                                        for metric in ['km', 'empirical', 'difference', 'improvement_percent']}}
            ranges[str(tolerance)] = {'subset_mappings': len(subset), 'roles': roles}
        result = {'status': 'Conditional evaluation using inferred labels; aggregate publication statistics informed reconstruction.',
                  'manifest': manifest, 'model_bundle_sha256': sha(raw), 'unique_fits': len(jobs), 'variants': results, 'sensitivity': ranges,
                  'optimizer': {k: {'train_labels': jobs[k]['train_labels'], 'base': m['base']['runs'], 'empirical': m['optimizer']}
                                for k, m in bundle['models'].items()}}
        for dest in [out, HERE]:
            write(dest/'summary.json', result); old.v3.write_csv(dest/'errors.csv', records)
        print(json.dumps({'base': results['base']['grouped'], 'sensitivity': {k: v['roles']['ternary12']['ranges'] for k, v in ranges.items()}}, indent=2))
    assert frozen.read_bytes() == raw


if __name__ == '__main__':
    main()
