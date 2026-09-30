"""Coordinator-only scalar re-evaluation of frozen agent artifacts; never fits.

Opaque decoding uses scalar sums and the subtractive equation. Finite-layer
decoding independently composes a layer's reflectance/transmittance with its
white backing, rather than using the participant's coth expression/inversion.
"""
import json
import math
import sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import measured_oils as v1
import measured_oils_chromatic as v3


def opaque(recipe, model, band):
    k = math.fsum(float(w) * model['K'][j][band] for j, w in enumerate(recipe))
    s = math.fsum(float(w) * model['S'][j][band] for j, w in enumerate(recipe))
    ratio = k / s
    return 1 + ratio - math.sqrt(ratio * ratio + 2 * ratio)


def finite(recipe, model, band):
    k = math.fsum(float(w) * model['q'][j][band] * model['S'][j][band] for j, w in enumerate(recipe))
    s = math.fsum(float(w) * model['S'][j][band] for j, w in enumerate(recipe))
    ratio = k / s
    if ratio == 0:
        return 1.0
    a = 1 + ratio
    b = math.sqrt(ratio * (ratio + 2))
    optical = b * s * model['x']
    decay = math.exp(-2 * optical)
    denominator = a + b - (a - b) * decay
    layer_r = -math.expm1(-2 * optical) / denominator
    layer_t = 2 * b * math.exp(-optical) / denominator
    return layer_r + layer_t * layer_t / (1 - layer_r)


def interaction(recipe, model, band):
    base = opaque(recipe, model['base'], band)
    t = band / 30
    basis = [(1-t)**3, 3*t*(1-t)**2, 3*t*t*(1-t), t**3]
    pair = 0
    shift = 0.0
    for i in range(4):
        for j in range(i+1, 4):
            correction = math.fsum(basis[k] * model['theta'][pair*4+k] for k in range(4))
            shift += 4 * recipe[i] * recipe[j] * correction
            pair += 1
    if shift == 0:
        return base
    return 1 / (1 + math.exp(-(math.log(base) - math.log1p(-base) + shift)))


def main():
    rows, c, measured, original = v1.load_source(ROOT / 'target/measured-oils/source/spectralDatasets.zip')
    primary, pairs, multi, folds = v3.design(c, original)
    _, _, lab = v1.colorimetry()
    output = {'method': 'independent scalar decoding of all frozen participant fits; same validated colorimetry', 'agents': {}}
    for name, decoder, summary_key, candidate, cv_key, cv_candidate in [
        ('physical', finite, 'multicolor16', 'finite', 'pair_cv8', 'finite_cv'),
        ('objective', opaque, 'primary_multicolor16', 'hybrid', 'pair_family_cv8', 'hybrid'),
        ('interaction', interaction, 'primary16', 'interaction', 'pairs_cv8', 'interaction')]:
        path = ROOT / 'target/measured-oils/parallel' / name / 'frozen-models.json'
        artifact = json.loads(path.read_text()); models = artifact['models']
        participant = json.loads((HERE / name / 'summary.json').read_text())
        manifest = artifact['manifest']
        if name == 'physical':
            assert manifest['fit_rows'] == rows[primary].tolist()
            assert manifest['assessment_rows'] == rows[multi].tolist()
            assert manifest['script_sha'] == v1.sha((HERE / name / 'run.py').read_bytes())
            assert manifest['plan_sha'] == v1.sha((HERE / name / 'PLAN.md').read_bytes())
            for family, (train, test) in folds.items():
                assert manifest['folds'][family] == {'fit': rows[train].tolist(), 'test': rows[test].tolist()}
        elif name == 'objective':
            assert manifest['primary_fit_rows'] == rows[primary].tolist()
            assert manifest['primary_test_rows'] == rows[multi].tolist()
            for file, digest in manifest['hashes'].items():
                assert v1.sha((ROOT / file).read_bytes()) == digest
            for family, (train, test) in folds.items():
                assert manifest['folds'][family] == {'train': rows[train].tolist(), 'test': rows[test].tolist()}
        else:
            assert manifest['fit_rows']['primary29'] == rows[primary].tolist()
            assert manifest['test_rows']['primary29'] == rows[multi].tolist()
            assert manifest['implementation_sha256'] == v1.sha((HERE / name / 'run.py').read_bytes())
            assert manifest['plan_sha256'] == v1.sha((HERE / name / 'PLAN.md').read_bytes())
            for family, (train, test) in folds.items():
                assert manifest['fit_rows'][family] == rows[train].tolist()
                assert manifest['test_rows'][family] == rows[test].tolist()
        predicted = np.array([[decoder(recipe, models['primary29'], b) for b in range(31)] for recipe in c])
        cross = predicted.copy()
        for family, (_, test) in folds.items():
            cross[test] = [[decoder(recipe, models[family], b) for b in range(31)] for recipe in c[test]]
        pure = (c > 0).sum(axis=1) == 1
        for value in [predicted, cross]:
            assert np.isfinite(value).all() and (value >= 0).all() and (value <= 1).all()
        checks = {'primary16': v1.summarize(v1.errors(measured, predicted, lab), multi),
                  'pair_cv8': v1.summarize(v1.errors(measured, cross, lab), pairs)}
        maximum = 0.0
        for role, reference in [('primary16', participant[summary_key][candidate]), ('pair_cv8', participant[cv_key][cv_candidate])]:
            for metric in ['spectral_rmse', 'spectral_mae', 'spectral_max_abs', 'delta_e_2000']:
                for statistic in ['mean', 'median', 'p95', 'max']:
                    maximum = max(maximum, abs(checks[role][metric][statistic] - reference[metric][statistic]))
        assert maximum < 1e-8, (name, maximum)
        output['agents'][name] = {'model_bundle_sha256': v1.sha(path.read_bytes()), 'split_and_source_hash_checks': 'passed',
            'independent_aggregate_max_abs_difference': maximum, 'scalar_primary_pure_max_abs_error': float(np.max(abs(predicted[pure] - measured[pure]))),
            **checks}
    v1.write_json(HERE / 'coordinator-checks.json', output)
    print(json.dumps({name: {'max_metric_difference': value['independent_aggregate_max_abs_difference'],
        'primary_mean_de00': value['primary16']['delta_e_2000']['mean'], 'pair_cv_mean_de00': value['pair_cv8']['delta_e_2000']['mean']}
        for name, value in output['agents'].items()}, indent=2))


if __name__ == '__main__':
    main()
