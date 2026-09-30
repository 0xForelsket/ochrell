"""Training-only diagnosis of the frozen 21-sample Old Holland calibration.

No held-out spectra enter the diagnostic interface or scoring. The unsmoothed
fit is a diagnostic, not another model selected on the 24 exposed mixtures.
"""
import argparse
import csv
import json
from pathlib import Path

import numpy as np
from scipy.optimize import minimize_scalar
import measured_oils as v1


def diagnose(rows, c, measured, baseline):
    q = v1.pure_ratios(c, measured)
    pure = np.array([measured[np.flatnonzero(c[:, j] == 1)[0]] for j in range(4)])
    fixed = np.asarray(baseline['log_relative_s']).ravel()
    unsmoothed = fixed.copy().reshape(3, 31)
    lo, hi = baseline['settings']['log_scattering_bounds']
    grid = np.linspace(lo, hi, 513)
    runs = []
    for j in range(3):
        tint = (c[:, j] > 0) & (c[:, 3] > 0)
        amount = c[tint, j]
        for band in range(31):
            def loss(u):
                s = np.exp(u)
                ratio = (amount * q[j, band] * s + (1 - amount) * q[3, band]) / (amount * s + 1 - amount)
                r = 1 / (1 + ratio + np.sqrt(ratio * (ratio + 2)))
                return float(np.sum((r - measured[tint, band]) ** 2))
            scores = np.array([loss(u) for u in grid])
            candidates = [(loss(unsmoothed[j, band]), unsmoothed[j, band]), (scores[0], lo), (scores[-1], hi)]
            refinements = 0
            for i in range(1, len(grid) - 1):
                if scores[i] <= scores[i - 1] and scores[i] <= scores[i + 1]:
                    sol = minimize_scalar(loss, bounds=(grid[i - 1], grid[i + 1]), method='bounded',
                                          options={'xatol': 1e-12, 'maxiter': 1000})
                    if not sol.success:
                        raise RuntimeError('Unsmoothed scalar refinement did not converge')
                    candidates.append((float(sol.fun), float(sol.x))); refinements += 1
            best_loss, best_u = min(candidates)
            unsmoothed[j, band] = best_u
            runs.append({'paint': v1.LABELS[j], 'wavelength_nm': 400 + 10 * band,
                         'local_minima_refined': refinements, 'tint_sum_squared_error': best_loss})
    _, _, lab = v1.colorimetry()
    predictions = {name: v1.predict(c, q, u)[0] for name, u in [('v1', fixed), ('unsmoothed_diagnostic', unsmoothed.ravel())]}
    metrics = {name: v1.errors(measured, p, lab) for name, p in predictions.items()}
    masks = {'all_calibration': np.ones(len(c), dtype=bool), 'tints_only': (c > 0).sum(axis=1) == 2}
    masks.update({f'{v1.LABELS[j]}+W': (c[:, j] > 0) & (c[:, 3] > 0) for j in range(3)})
    summary = {'fit_rows': rows.tolist(), 'samples': len(c), 'holdout_used': False,
        'models': {name: {role: v1.summarize(m, mask) for role, mask in masks.items()} for name, m in metrics.items()},
        'spectral_mse': {name: float(np.mean((p - measured) ** 2)) for name, p in predictions.items()},
        'grid_points_per_scalar_fit': 513, 'refinements': runs, 'monotonicity': {}, 'pure_envelope': []}
    for j in range(3):
        selected = np.flatnonzero((c[:, j] + c[:, 3] == 1) & ((c > 0).sum(axis=1) <= 2))
        selected = selected[np.argsort(c[selected, j])]
        direction = np.sign(pure[j] - pure[3])
        violations = []
        for a, b in zip(selected[:-1], selected[1:]):
            reversal = np.maximum(-direction * (measured[b] - measured[a]), 0)
            if reversal.max() > .001:
                violations.append({'from_source_row': int(rows[a]), 'to_source_row': int(rows[b]),
                    'max_reversal_reflectance': float(reversal.max()), 'bands_over_0_001': int((reversal > .001).sum()),
                    'worst_wavelength_nm': int(400 + 10 * np.argmax(reversal))})
        summary['monotonicity'][v1.LABELS[j]] = {'comparisons': len(selected) - 1, 'violations': violations}
    for i, recipe in enumerate(c):
        active = pure[recipe > 0]
        gap = np.maximum(np.maximum(active.min(axis=0) - measured[i], measured[i] - active.max(axis=0)), 0)
        if gap.max() > .001:
            summary['pure_envelope'].append({'source_row': int(rows[i]), 'family': v1.family(recipe),
                'max_gap': float(gap.max()), 'rmse_lower_bound_from_envelope': float(np.sqrt(np.mean(gap ** 2)))})
    before = summary['spectral_mse']['v1']
    after = summary['spectral_mse']['unsmoothed_diagnostic']
    if after > before + 1e-12:
        raise AssertionError('Unsmoothed search lost the included v1 solution')
    summary['fraction_calibration_squared_error_removed'] = 1 - after / before
    return summary, metrics, unsmoothed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=v1.ROOT / 'target/measured-oils/source/spectralDatasets.zip')
    parser.add_argument('--baseline', type=Path, default=v1.ROOT / 'target/measured-oils/v1/fitted-model.json')
    parser.add_argument('--out', type=Path, default=v1.ROOT / 'target/measured-oils/calibration-diagnosis')
    args = parser.parse_args()
    out = v1.research_directory(args.out)
    rows, c, r, fit = v1.load_source(args.source)
    baseline = json.loads(args.baseline.read_text())
    if baseline['fit_rows'] != rows[fit].tolist():
        raise ValueError('Wrong baseline partition')
    summary, metrics, u = diagnose(rows[fit], c[fit], r[fit], baseline)
    summary.update({'baseline_model_sha256': v1.sha(args.baseline.read_bytes()),
                    'implementation_sha256': v1.sha(Path(__file__).read_bytes())})
    v1.write_json(out / 'summary.json', summary)
    v1.write_json(out / 'unsmoothed-training-only.json', {'log_relative_s': u.tolist(), 'holdout_evaluation': 'not performed'})
    fields = ['source_row', 'family'] + [f'{name}_{key}' for name, m in metrics.items() for key in m]
    with (out / 'errors.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator='\n'); writer.writeheader()
        for i, row in enumerate(rows[fit]):
            writer.writerow({'source_row': int(row), 'family': v1.family(c[fit][i]),
                **{f'{name}_{key}': float(value[i]) for name, m in metrics.items() for key, value in m.items()}})
    print(json.dumps({k: summary[k] for k in ['samples', 'holdout_used', 'spectral_mse',
        'fraction_calibration_squared_error_removed', 'monotonicity', 'pure_envelope']}, indent=2))


if __name__ == '__main__':
    main()
