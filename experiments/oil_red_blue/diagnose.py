"""Inspect frozen red/blue predictions and support; deliberately contains no fitting."""
import os
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'

import csv
import importlib.util
import io
import itertools
import json
import sys
import zipfile
from pathlib import Path

import numpy as np
from scipy.special import expit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import measured_oils as v1
import measured_oils_chromatic as v3


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


empirical = load_module('empirical_frozen', ROOT / 'experiments/oil_parallel/interaction/run.py')
scalar = load_module('independent_scalar', ROOT / 'experiments/oil_parallel/validate_comparison.py')
OUT = ROOT / 'target/measured-oils/red-blue-diagnosis'
BUNDLE = ROOT / 'target/measured-oils/grouped-ratios/frozen-models.json'
SOURCE = ROOT / 'target/measured-oils/source/spectralDatasets.zip'


def compose(base, terms):
    return np.where(terms == 0, base, expit(np.log(base) - np.log1p(-base) + terms))


def components(c, model):
    c, x = empirical.features(c)
    theta = np.asarray(model['theta'])
    spectral_curves = empirical.B @ theta.reshape(6, 4).T
    weights = np.array([4*c[:, a]*c[:, b] for a, b in empirical.PAIRS]).T
    terms = weights[:, None, :] * spectral_curves[None, :, :]
    np.testing.assert_allclose(terms.sum(2), x @ theta, rtol=0, atol=5e-16)
    base = v3.predicted(c, model['base'])
    rb = terms[:, :, empirical.PAIRS.index((1, 2))]
    rw = terms[:, :, empirical.PAIRS.index((1, 3))]
    bw = terms[:, :, empirical.PAIRS.index((2, 3))]
    result = {'km': base, 'rb_only': compose(base, rb),
              'white_only': compose(base, rw + bw), 'full': compose(base, terms.sum(2))}
    np.testing.assert_allclose(result['full'], empirical.predict(c, model), rtol=0, atol=3e-16)
    return result, {'rb': rb, 'rw': rw, 'bw': bw}


def maximum_disagreement(predictions, lab):
    error_sets = [v1.errors(predictions[a], predictions[b], lab)
                  for a, b in itertools.combinations(predictions, 2)]
    return {key: np.max([e[key] for e in error_sets], axis=0)
            for key in ('delta_e_2000', 'spectral_rmse')}


def main():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    OUT.mkdir(parents=True, exist_ok=True)
    raw = BUNDLE.read_bytes()
    bundle = json.loads(raw)
    grouped = json.loads((ROOT / 'experiments/oil_grouped/summary.json').read_text())
    assert v1.sha(raw) == grouped['model_bundle_sha256']
    for name, expected in bundle['manifest']['hashes'].items():
        assert v1.sha((ROOT / name).read_bytes()) == expected, name
    paths = [HERE / 'PLAN.md', Path(__file__), BUNDLE, SOURCE, Path(v1.__file__),
             Path(v3.__file__), Path(empirical.__file__), Path(scalar.__file__),
             ROOT / 'experiments/oil_grouped/summary.json', ROOT / 'data/cie_380_780_1nm.csv']
    hashes = {p.relative_to(ROOT).as_posix(): v1.sha(p.read_bytes()) for p in paths}
    rows, c, measured, original = v1.load_source(SOURCE)
    models = {'both_parents': bundle['models']['ratio-172'],
              'only_9_to_1': bundle['models']['ratio-112'],
              'only_1_to_1': bundle['models']['ratio-113']}
    model_folds = {'both_parents': 'ratio-172', 'only_9_to_1': 'ratio-112', 'only_1_to_1': 'ratio-113'}
    selected = np.flatnonzero(np.isin(rows, [112, 113, 114, 115]))
    assert rows[selected].tolist() == [112, 113, 114, 115]
    _, _, lab = v1.colorimetry()

    with zipfile.ZipFile(SOURCE) as z:
        amounts = np.loadtxt(io.BytesIO(z.read('oilmixtureportions.txt')))
    allowed = np.array([2, 4, 7])
    unused = np.array([0, 1, 3, 5, 6])
    rb = (amounts[:, 2] > 0) & (amounts[:, 4] > 0) & (amounts[:, unused] == 0).all(1)
    source_support = (np.flatnonzero(rb) + 1).tolist()
    assert source_support == [112, 113, 114, 115]
    normalized = amounts[:, allowed] / amounts.sum(1, keepdims=True)
    distinct = len(np.unique(normalized[rb].round(12), axis=0))

    records = []
    for name, model in models.items():
        predictions, terms = components(c[selected], model)
        metrics = {variant: v1.errors(measured[selected], p, lab) for variant, p in predictions.items()}
        training = bundle['manifest']['folds'][model_folds[name]]['train_rows']
        for j, i in enumerate(selected):
            r = c[i, 1] / (c[i, 1] + c[i, 2])
            rec = {'model': name, 'source_row': int(rows[i]), 'red_fraction_of_chromatic': float(r),
                   'white_fraction': float(c[i, 3]), 'row_in_training': int(rows[i]) in training}
            for key, values in terms.items():
                rec[key + '_logit_rms'] = float(np.sqrt(np.mean(values[j] ** 2)))
            for variant, errors in metrics.items():
                rec.update({variant + '_' + key: float(value[j]) for key, value in errors.items()})
            records.append(rec)
    # Reproduce the previously recorded assessment errors, using the correct fold.
    with (ROOT / 'experiments/oil_grouped/errors.csv').open(newline='') as f:
        previous = {int(r['source_row']): r for r in csv.DictReader(f)}
    reproduced = []
    for rec in records:
        if (rec['model'] == 'only_9_to_1' and rec['source_row'] != 113) or (rec['model'] == 'only_1_to_1' and rec['source_row'] == 113):
            for old, new in [('km', 'km'), ('interaction', 'full')]:
                for key in ('spectral_rmse', 'spectral_mae', 'spectral_max_abs', 'delta_e_2000'):
                    reproduced.append(abs(rec[new + '_' + key] - float(previous[rec['source_row']][old + '_' + key])))
    assert max(reproduced) < 1e-11
    v3.write_csv(HERE / 'observed-components.csv', records)

    t = np.linspace(0, 1, 1001)
    trajectories = []
    peaks = []
    all_spectra = {}
    checks = {'grid_count_per_model': 3003, 'independent_scalar_max_abs': 0.0,
              'pure_endpoint_max_abs': 0.0, 'all_predictions_finite_bounded': True,
              'archived_metric_max_abs_difference': max(reproduced)}
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), layout='constrained')
    for white, color in [(0, '#344f79'), (.5, '#248781'), (.95, '#b46c33')]:
        recipes = np.stack((np.zeros_like(t), (1-white)*t, (1-white)*(1-t), np.full_like(t, white)), axis=1)
        weights = np.stack([4*recipes[:, a]*recipes[:, b] for a, b in empirical.PAIRS], axis=1)
        np.testing.assert_allclose(weights[:, empirical.PAIRS.index((1, 2))], 4*(1-white)**2*t*(1-t), atol=3e-16)
        np.testing.assert_allclose(weights[:, empirical.PAIRS.index((1, 3))], 4*(1-white)*t*white, atol=3e-16)
        np.testing.assert_allclose(weights[:, empirical.PAIRS.index((2, 3))], 4*(1-white)*(1-t)*white, atol=3e-16)
        full, base = {}, {}
        for name, model in models.items():
            full[name] = empirical.predict(recipes, model)
            base[name] = v3.predicted(recipes, model['base'])
            reference = np.array([[scalar.interaction(recipe, model, band) for band in range(31)] for recipe in recipes])
            error = float(abs(reference - full[name]).max())
            checks['independent_scalar_max_abs'] = max(checks['independent_scalar_max_abs'], error)
            assert error < 1e-12 and np.isfinite(full[name]).all() and (full[name] > 0).all() and (full[name] < 1).all()
            if white == 0:
                endpoint = float(abs(full[name][[0, -1]] - base[name][[0, -1]]).max())
                checks['pure_endpoint_max_abs'] = max(checks['pure_endpoint_max_abs'], endpoint)
                assert endpoint == 0
            all_spectra[f'{name}_w{white}'] = full[name]
        spread = maximum_disagreement(full, lab)
        base_spread = maximum_disagreement(base, lab)
        for i, red in enumerate(t):
            trajectories.append({'white_fraction': white, 'red_fraction_of_chromatic': float(red),
                                 **{'full_max_pairwise_' + k: float(v[i]) for k, v in spread.items()},
                                 **{'km_max_pairwise_' + k: float(v[i]) for k, v in base_spread.items()}})
        for kind, values in [('full', spread), ('km', base_spread)]:
            for metric, values_array in values.items():
                i = int(np.argmax(values_array))
                peaks.append({'white_fraction': white, 'model_stage': kind, 'metric': metric,
                              'peak': float(values_array[i]), 'red_fraction_at_peak': float(t[i])})
        for ax, metric in zip(axes, ['delta_e_2000', 'spectral_rmse']):
            ax.plot(t, spread[metric], color=color, label=f'{white:.0%} white, full model')
            ax.plot(t, base_spread[metric], '--', color=color, alpha=.6)
    for ax, ylabel in zip(axes, ['Largest pairwise CIEDE2000', 'Largest pairwise spectral RMSE']):
        ax.set_xlabel('Red fraction within red + blue'); ax.set_ylabel(ylabel)
        ax.grid(alpha=.2); ax.set_xlim(0, 1)
    axes[0].legend(fontsize=8)
    fig.suptitle('Sensitivity to available red/blue calibration ratios\nModel disagreement, not measured error; dashed = K-M bases')
    fig.savefig(HERE / 'ratio-disagreement.png', dpi=170); plt.close(fig)
    v3.write_csv(OUT / 'trajectories.csv', trajectories)
    np.savez_compressed(OUT / 'predicted-spectra.npz', **all_spectra)

    fig, axes = plt.subplots(2, 2, figsize=(11, 7.5), layout='constrained')
    nm = np.arange(400, 701, 10)
    for ax, i in zip(axes.flat, selected):
        ax.plot(nm, measured[i], color='black', linewidth=2, label='Measured')
        for name, color, label in [('both_parents', '#248781', 'Both parent ratios'),
                                   ('only_9_to_1', '#b46c33', 'Only 9:1 parent'),
                                   ('only_1_to_1', '#344f79', 'Only 1:1 parent')]:
            ax.plot(nm, empirical.predict(c[i:i+1], models[name])[0], color=color, label=label)
        ratio = '9:1' if rows[i] == 113 else '1:1'
        ax.set_title(f'Row {rows[i]}: R:B {ratio}, white {c[i,3]:.0%}')
        ax.set_xlabel('Wavelength (nm)'); ax.set_ylabel('Reflectance'); ax.grid(alpha=.2)
    axes[0,0].legend(fontsize=8)
    fig.suptitle('Existing observations and frozen model predictions\nParent rows are training data for some curves; see report')
    fig.savefig(HERE / 'observed-spectra.png', dpi=170); plt.close(fig)

    proposed = []
    for red, blue in [(1,9), (1,3), (1,1), (3,1), (9,1)]:
        for multiplier in (0,1,19):
            white = multiplier * (red+blue)
            recipe = np.array([red,blue,white], dtype=float)
            matches = (np.max(abs(normalized - recipe/recipe.sum()), axis=1) < 1e-12) & rb
            found = (np.flatnonzero(matches)+1).tolist()
            proposed.append({'red_parts': red, 'blue_parts': blue, 'white_parts': white,
                             'white_fraction': float(white/recipe.sum()), 'independent_preparations': 3,
                             'existing_source_rows': ','.join(map(str,found)),
                             'purpose': 'repeat existing condition' if found else 'new ratio/white condition'})
    assert sum(bool(r['existing_source_rows']) for r in proposed) == 4
    v3.write_csv(HERE / 'proposed-measurements.csv', proposed)
    summary = {'status': 'post-hoc frozen-model diagnosis; no fitting or new measurements',
               'provenance_hashes': hashes, 'source_support': {'rows': source_support,
               'distinct_normalized_recipes': distinct, 'independent_replicates_identified': False},
               'model_disagreement_peaks': peaks, 'checks': checks,
               'proposal': {'conditions': 15, 'currently_missing_conditions': 11,
                            'independent_mixture_swatches': 45, 'pure_anchor_swatches': 9,
                            'total_proposed_swatches': 54}}
    for p, expected in hashes.items():
        assert v1.sha((ROOT / p).read_bytes()) == expected, p
    v1.write_json(HERE / 'summary.json', summary)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
