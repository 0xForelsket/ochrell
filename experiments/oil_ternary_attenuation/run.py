"""One frozen scalar attenuation rule; no refitting of K-M or pair curves."""
import os
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
import argparse
import csv
import importlib.util
import json
import math
from pathlib import Path

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.special import expit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location('reconstructed', ROOT/'experiments/oil_reconstructed/run.py')
study = importlib.util.module_from_spec(spec)
spec.loader.exec_module(study)
old = study.old
OUT = ROOT/'target/measured-oils/ternary-attenuation'
UPSTREAM = study.DEFAULT/'frozen-models.json'
EXPECTED = '8090dd57ce49b584fcae15cdb85eafbe942a4181c97f53b27a95d22265bc1ced'
WHITE_CONTROLS = np.array([3 in pair for pair in old.empirical.PAIRS]).repeat(4)
CHROMATIC_LABELS = ['Bcy', 'bCy', 'bcY']


def prohibited_fit(*args, **kwargs):
    raise RuntimeError('The K-M and pair-curve fits must remain frozen')


old.empirical.fit = prohibited_fit
old.v1.fit_model = prohibited_fit


def terms(c, model):
    c, x = old.empirical.features(c)
    theta = np.array(model['theta'])
    km = old.v3.predicted(c, model['base'])
    original = old.empirical.forward(km, x, theta)
    chromatic = x[:, :, ~WHITE_CONTROLS] @ theta[~WHITE_CONTROLS]
    white = x[:, :, WHITE_CONTROLS] @ theta[WHITE_CONTROLS]
    gate = 27*np.prod(c[:, :3], axis=1)
    assert (gate >= 0).all() and (gate <= 1+1e-14).all()
    return km, original, chromatic, white, gate


def decode(t, strength):
    assert 0 <= strength <= 1
    km, original, chromatic, white, gate = t
    shift = (1-strength*gate[:, None])*chromatic+white
    result = np.where(shift == 0, km, expit(np.log(km)-np.log1p(-km)+shift))
    # Preserve existing decoder bits exactly on unaffected faces and lambda=0.
    return np.where(((gate == 0) | (strength == 0))[:, None], original, result)


def predict(c, model, strength):
    return decode(terms(c, model), strength)


def scalar(c, model, strength, band):
    c = [float(x)/sum(c) for x in c]
    q = model['base']['q']; logs = model['base']['log_relative_s']
    scattering = [math.exp(logs[p][band]) if p < 3 else 1.0 for p in range(4)]
    ratio = sum(c[p]*q[p][band]*scattering[p] for p in range(4))/sum(c[p]*scattering[p] for p in range(4))
    km = 1/(1+ratio+math.sqrt(ratio*(ratio+2)))
    x = band/30; basis = [(1-x)**3, 3*x*(1-x)**2, 3*x*x*(1-x), x**3]
    chromatic = white = 0.0
    for k, (a, b) in enumerate([(0,1),(0,2),(0,3),(1,2),(1,3),(2,3)]):
        value = 4*c[a]*c[b]*sum(basis[j]*model['theta'][4*k+j] for j in range(4))
        if b == 3: white += value
        else: chromatic += value
    shift = (1-strength*27*c[0]*c[1]*c[2])*chromatic+white
    if shift == 0: return km
    return 1/(1+math.exp(-(math.log(km)-math.log1p(-km)+shift)))


def fit_strength(c_calibration, target_calibration, model):
    assert c_calibration.shape == (2, 4) and target_calibration.shape == (2, 31)
    t = terms(c_calibration, model)
    def objective(value):
        return float(np.mean((decode(t, value)-target_calibration)**2))
    solution = minimize_scalar(objective, bounds=(0, 1), method='bounded', options={'xatol': 1e-12, 'maxiter': 1000})
    assert solution.success, solution.message
    candidates = [(objective(value), value) for value in [0.0, float(solution.x), 1.0]]
    loss, strength = min(candidates)
    grid = np.linspace(0, 1, 1001)
    profile = np.array([objective(float(value)) for value in grid])
    assert loss <= profile.min()+1e-13
    return {'lambda': strength, 'calibration_mse': loss, 'original_calibration_mse': objective(0.0),
            'upper_endpoint_calibration_mse': objective(1.0), 'bounded_optimizer_x': float(solution.x),
            'optimizer_success': bool(solution.success), 'optimizer_message': solution.message,
            'nfev': int(solution.nfev), 'at_lower_bound': strength == 0, 'at_upper_bound': strength == 1,
            'profile_min': float(profile.min()), 'profile_nondecreasing_steps': int((np.diff(profile) >= 0).sum())}, profile


def load():
    raw = UPSTREAM.read_bytes(); assert study.sha(raw) == EXPECTED
    bundle = json.loads(raw)
    upstream = bundle['manifest']
    for hashes in [upstream['hashes'], upstream['original_method']['hashes']]:
        for name, digest in hashes.items(): assert study.sha((ROOT/name).read_bytes()) == digest, name
    variants_path = ROOT/'experiments/oil_reconstructed/variants.json'
    assert study.sha(variants_path.read_bytes()) == upstream['variants_sha256']
    variants = json.loads(variants_path.read_text(encoding='utf-8'))
    data = study.inputs()
    names, c = data[5:7]
    indices = [names.tolist().index(label) for label in CHROMATIC_LABELS]
    assert np.array_equal(27*np.prod(c[indices, :3], axis=1), np.full(3, 27/32))
    folds = {label: {'train': [k for k in indices if k != i], 'test': i} for label, i in zip(CHROMATIC_LABELS, indices)}
    for v in variants['variants']:
        plan = bundle['variants'][v['id']]
        assert all(plan['fold_models'][label] == plan['primary_model'] for label in CHROMATIC_LABELS)
    paths = [Path(__file__), HERE/'PLAN.md', UPSTREAM, variants_path,
             ROOT/'experiments/oil_reconstructed/summary.json', ROOT/'experiments/oil_reconstructed/errors.csv',
             ROOT/'experiments/oil_white_split/summary.json']
    manifest = {'status': 'Exploratory scalar revision after observing assessment failures.', 'upstream_manifest': upstream,
        'hashes': {p.relative_to(ROOT).as_posix(): study.sha(p.read_bytes()) for p in paths},
        'rule': 'chromatic_logit_shift * (1-lambda*27*cY*cC*cB) + unchanged white_logit_shift',
        'lambda_bounds': [0, 1], 'folds': {label: {'train': names[f['train']].tolist(), 'test': str(names[f['test']])} for label, f in folds.items()},
        'grid_nm': old.GRID.tolist(), 'environment': upstream['environment']}
    return raw, bundle, variants, data, folds, manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=['prepare', 'fit', 'verify', 'evaluate'])
    parser.add_argument('--out', type=Path, default=OUT)
    args = parser.parse_args(); out = old.v1.research_directory(args.out)
    raw_upstream, bundle, variants, data, folds, manifest = load()
    names, c = data[5:7]
    partition, frozen = out/'partition.json', out/'frozen-attenuation.json'
    if args.phase == 'prepare':
        assert not partition.exists() and not frozen.exists(), 'Refusing overwrite'
        study.write(partition, manifest)
        print(json.dumps({'rule': manifest['rule'], 'folds': manifest['folds'], 'variants': len(variants['variants'])}, indent=2))
        return
    assert json.loads(partition.read_text(encoding='utf-8')) == manifest
    if args.phase == 'fit':
        assert not frozen.exists(), 'Refusing frozen attenuation overwrite'
        models, profiles = {}, {}
        for v in variants['variants']:
            measured = data[8][np.array(v['mapping'])[data[4]]]
            model_id = bundle['variants'][v['id']]['primary_model']; model = bundle['models'][model_id]
            for label, f in folds.items():
                key = v['id']+'/'+label
                result, profile = fit_strength(c[f['train']].copy(), measured[f['train']].copy(), model)
                models[key] = {'base_model_id': model_id, 'train': names[f['train']].tolist(), 'test': label, **result}
                profiles[key] = profile
                print(key, 'lambda', result['lambda'], 'calibration MSE', result['calibration_mse'], flush=True)
        study.write(frozen, {'manifest': manifest, 'fits': models})
        np.savez_compressed(out/'calibration-profiles.npz', **profiles)
        print('Frozen attenuation SHA256', study.sha(frozen.read_bytes()))
        assert UPSTREAM.read_bytes() == raw_upstream
        return
    raw = frozen.read_bytes(); fitted = json.loads(raw)
    assert fitted['manifest'] == manifest
    if args.phase == 'verify':
        checks = {'scalar_max_abs': 0.0, 'gate_zero_max_abs': 0.0, 'lambda_zero_max_abs': 0.0,
                  'excluded_target_lambda_change': 0.0, 'excluded_target_objective_change': 0.0,
                  'dense_min': 1.0, 'dense_max': 0.0, 'pure_max_abs': 0.0, 'equal_thirds_full_attenuation_km_max_abs': 0.0}
        rng = np.random.default_rng(621)
        dense = np.vstack([rng.dirichlet(np.ones(4), 1024), np.eye(4), [[1/3,1/3,1/3,0]]])
        faces = []
        for missing in range(3):
            face = rng.dirichlet(np.ones(3), 100)
            recipes = np.zeros((100, 4)); recipes[:, [p for p in range(4) if p != missing]] = face; faces.append(recipes)
        for a in range(4):
            for b in range(a+1,4):
                recipes = np.zeros((101, 4)); recipes[:, a] = np.linspace(0,1,101); recipes[:, b] = 1-recipes[:, a]; faces.append(recipes)
        faces = np.vstack(faces)
        scalar_recipes = np.vstack([c, np.eye(4), [[1/3,1/3,1/3,0]], rng.dirichlet(np.ones(4), 16)])
        checked = set(); continuity = []
        for v in variants['variants']:
            measured = data[8][np.array(v['mapping'])[data[4]]]
            model_id = bundle['variants'][v['id']]['primary_model']; model = bundle['models'][model_id]
            for label, f in folds.items():
                fit = fitted['fits'][v['id']+'/'+label]; strength = fit['lambda']
                assert fit['base_model_id'] == model_id
                altered = measured.copy(); altered[f['test']] = rng.uniform(.02,.98,31)
                again, _ = fit_strength(c[f['train']].copy(), altered[f['train']].copy(), model)
                assert again == {k: fit[k] for k in again}
                identity = (model_id, strength)
                if identity in checked: continue
                checked.add(identity)
                pred = predict(scalar_recipes, model, strength)
                reference = np.array([[scalar(r, model, strength, b) for b in range(31)] for r in scalar_recipes])
                checks['scalar_max_abs'] = max(checks['scalar_max_abs'], float(abs(pred-reference).max()))
                np.testing.assert_array_equal(predict(faces, model, strength), old.empirical.predict(faces, model))
                np.testing.assert_array_equal(predict(dense, model, 0), old.empirical.predict(dense, model))
                for value in [0.0, .5, 1.0, strength]:
                    p = predict(dense, model, value)
                    assert np.isfinite(p).all() and (p > 0).all() and (p < 1).all()
                    checks['dense_min'] = min(checks['dense_min'], float(p.min())); checks['dense_max'] = max(checks['dense_max'], float(p.max()))
                pure = (c > 0).sum(1) == 1
                checks['pure_max_abs'] = max(checks['pure_max_abs'], float(abs(predict(c[pure], model, strength)-measured[pure]).max()))
                third = np.array([[1/3,1/3,1/3,0]])
                checks['equal_thirds_full_attenuation_km_max_abs'] = max(checks['equal_thirds_full_attenuation_km_max_abs'],
                    float(abs(predict(third, model, 1)-old.v3.predicted(third, model['base'])).max()))
                for missing in range(3):
                    for epsilon in [1e-3,1e-6,1e-9,1e-12]:
                        recipe = np.zeros((1,4)); recipe[0, :3] = (1-epsilon)/2; recipe[0, missing] = epsilon
                        difference = float(abs(predict(recipe, model, 1)-old.empirical.predict(recipe, model)).max())
                        # Logistic slope <= 1/4; original pair controls are <= .8.
                        assert difference <= 4*epsilon+1e-15
                        continuity.append({'model': model_id, 'missing_pigment': missing, 'epsilon': epsilon, 'max_prediction_change': difference})
        assert checks['scalar_max_abs'] < 1e-12 and checks['pure_max_abs'] < 1e-12
        assert checks['equal_thirds_full_attenuation_km_max_abs'] < 1e-12
        verification = {'manifest': manifest, 'frozen_sha256': study.sha(raw), 'checks': checks, 'scalar_fits_repeated': 21,
            'unique_model_strengths_checked': len(checked), 'dense_recipes_per_check': len(dense), 'unaffected_face_recipes_per_check': len(faces), 'continuity': continuity}
        study.write(out/'verification.json', verification); study.write(HERE/'verification.json', verification)
        print(json.dumps({k: value for k, value in verification.items() if k not in ['manifest','continuity']}, indent=2))
    else:
        verify = json.loads((out/'verification.json').read_text(encoding='utf-8'))
        assert verify['manifest'] == manifest and verify['frozen_sha256'] == study.sha(raw)
        previous = {(r['variant'], r['sample']): r for r in csv.DictReader((ROOT/'experiments/oil_reconstructed/errors.csv').open(newline=''))}
        anchors, pairs, multi, pool, grouped = study.design(data)
        lab, _ = old.colorimetry(); results = {}; records = []; fit_records = []; replay_error = 0.0
        for v in variants['variants']:
            measured = data[8][np.array(v['mapping'])[data[4]]]
            predictions = {k: measured.copy() for k in ['km','original','attenuated']}
            for group, f in grouped.items():
                model_id = bundle['variants'][v['id']]['fold_models'][group]; model = bundle['models'][model_id]
                subset = f['test']
                predictions['km'][subset] = old.v3.predicted(c[subset], model['base'])
                predictions['original'][subset] = old.empirical.predict(c[subset], model)
                if group in CHROMATIC_LABELS:
                    fit = fitted['fits'][v['id']+'/'+group]
                    assert fit['base_model_id'] == model_id and subset.sum() == 1
                    predictions['attenuated'][subset] = predict(c[subset], model, fit['lambda'])
                    fit_records.append({'variant': v['id'], 'excluded': group, **fit})
                else:
                    # All three fitted strengths must leave this fold unaffected.
                    for label in CHROMATIC_LABELS:
                        candidate = predict(c[subset], model, fitted['fits'][v['id']+'/'+label]['lambda'])
                        np.testing.assert_array_equal(candidate, predictions['original'][subset])
                    predictions['attenuated'][subset] = predictions['original'][subset]
            metrics = {key: old.v1.errors(measured, p, lab) for key, p in predictions.items()}
            chromatic = multi & (c[:, 3] == 0); white = multi & (c[:, 3] > 0)
            masks = {'chromatic3_primary': chromatic, 'white9_unchanged': white, 'pairs9_unchanged': pairs,
                     'ternary12_composite': multi, 'all21_composite': multi|pairs}
            results[v['id']] = {'tolerances': v['tolerances'], 'changed_subset_labels': v['changed_subset_labels'],
                'assessments': {role: {key: old.v1.summarize(m, mask) for key, m in metrics.items()} for role, mask in masks.items()}}
            for i in np.flatnonzero(~anchors):
                rec = {'variant': v['id'], 'sample': str(names[i]), 'role': 'chromatic3' if chromatic[i] else 'white9' if white[i] else 'pair9'}
                rec.update({key+'_'+metric: float(value[i]) for key, errors in metrics.items() for metric, value in errors.items()})
                for prefix, saved_prefix in [('km','km'),('original','empirical')]:
                    for metric in metrics[prefix]: replay_error = max(replay_error, abs(rec[prefix+'_'+metric]-float(previous[v['id'],str(names[i])][saved_prefix+'_'+metric])))
                records.append(rec)
        assert len(records) == 147 and len(fit_records) == 21 and replay_error < 1e-11
        ranges = {}
        for tol in [2e-6,5e-6,1e-5]:
            selected = [v for v in results.values() if tol in v['tolerances']]
            values = {}
            for comparator in ['km','original']:
                for metric in ['spectral_rmse','delta_e_2000']:
                    differences = [v['assessments']['chromatic3_primary']['attenuated'][metric]['mean']-v['assessments']['chromatic3_primary'][comparator][metric]['mean'] for v in selected]
                    improvements = [100*(1-v['assessments']['chromatic3_primary']['attenuated'][metric]['mean']/v['assessments']['chromatic3_primary'][comparator][metric]['mean']) for v in selected]
                    values[comparator+'_'+metric] = {'difference_range': [min(differences),max(differences)], 'improvement_percent_range': [min(improvements),max(improvements)]}
            ranges[str(tol)] = {'mappings': len(selected), 'primary_comparison': values}
        result = {'status': 'Exploratory exposed-data scalar revision; not independent validation.', 'manifest': manifest,
            'frozen_sha256': study.sha(raw), 'fits': fit_records, 'variants': results, 'sensitivity': ranges,
            'original_assessment_replay_max_abs': replay_error, 'unchanged_assessment_count': 126}
        for destination in [HERE, out]:
            study.write(destination/'summary.json', result); old.v3.write_csv(destination/'errors.csv', records)
        print(json.dumps({'base': results['base']['assessments']['chromatic3_primary'], 'sensitivity': ranges}, indent=2))
    assert frozen.read_bytes() == raw and UPSTREAM.read_bytes() == raw_upstream


if __name__ == '__main__': main()
