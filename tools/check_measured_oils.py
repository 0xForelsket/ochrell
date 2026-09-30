"""Verify frozen research predictions independently; summarize wavelength bias.

No fitting, parameter selection or model writes. Run after measured_oils evaluate.
"""
import argparse
import csv
import json
import math
from pathlib import Path

import numpy as np
import measured_oils as study


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=study.ROOT / 'target/measured-oils/source/spectralDatasets.zip')
    parser.add_argument('--out', type=Path, default=study.ROOT / 'target/measured-oils/v1')
    args = parser.parse_args()
    out = study.research_directory(args.out)
    path = out / 'fitted-model.json'
    before = study.sha(path.read_bytes())
    model = json.loads(path.read_text())
    report = json.loads((out / 'summary.json').read_text())
    rows, c, measured, fit = study.load_source(args.source)
    if model['fit_rows'] != rows[fit].tolist() or before != report['model_sha256']:
        raise ValueError('Frozen fit or partition differs from the evaluated model')
    k, s, q = [np.asarray(model[key]) for key in ['K', 'S', 'q']]
    predictions = study.predict(c, q, np.asarray(model['log_relative_s']).ravel())[0]
    # Scalar accumulations and the subtractive K-M equation differ from the
    # vectorized fitter's matrix products and reciprocal reflectance expression.
    reference = np.empty_like(predictions)
    for i, recipe in enumerate(c):
        for band in range(31):
            a = sum(float(w) * float(k[j, band]) for j, w in enumerate(recipe))
            b = sum(float(w) * float(s[j, band]) for j, w in enumerate(recipe))
            ratio = a / b
            reference[i, band] = 1 + ratio - math.sqrt(ratio * ratio + 2 * ratio)
    maximum = float(np.max(np.abs(reference - predictions)))
    if maximum > 1e-12 or not np.isfinite(predictions).all() or (predictions < 0).any() or (predictions > 1).any():
        raise AssertionError(f'Independent reference mismatch: {maximum}')
    baseline = study.predict(c, q, np.zeros(93))[0]
    fields = ['wavelength_nm'] + [f'{name}_{role}_{metric}' for name in ['fitted', 'baseline']
                                 for role in ['fit', 'holdout'] for metric in ['signed_bias', 'rmse']]
    with (out / 'wavelength-errors.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator='\n'); writer.writeheader()
        for band, nm in enumerate(range(400, 701, 10)):
            row = {'wavelength_nm': nm}
            for name, predicted in [('fitted', predictions), ('baseline', baseline)]:
                for role, mask in [('fit', fit), ('holdout', ~fit)]:
                    diff = predicted[mask, band] - measured[mask, band]
                    row[f'{name}_{role}_signed_bias'] = float(np.mean(diff))
                    row[f'{name}_{role}_rmse'] = float(np.sqrt(np.mean(diff ** 2)))
            writer.writerow(row)
    if study.sha(path.read_bytes()) != before:
        raise AssertionError('Verification modified the frozen model')
    verification = {'independent_scalar_km_max_abs_error': maximum,
        'model_sha256_after_evaluation': before, 'fit_rows_verified': True, 'holdout_rows': int((~fit).sum()),
        'verification_implementation_sha256': study.sha(Path(__file__).read_bytes()),
        'holdout_signed_spectral_bias': float(np.mean(predictions[~fit] - measured[~fit]))}
    # Exploratory diagnosis after evaluation, not a fitted correction or a new
    # acceptance threshold. Positive K/S mixtures cannot leave the per-band
    # reflectance envelope of their active ingredients with fixed pure spectra.
    pure = np.array([measured[np.flatnonzero(c[:, j] == 1)[0]] for j in range(4)])
    envelope = {'diagnostic_threshold_reflectance': 0.001, 'roles': {}}
    for role, mask in [('fit_tints', fit & ((c > 0).sum(axis=1) > 1)), ('holdout', ~fit)]:
        violations = []
        for i in np.flatnonzero(mask):
            active = pure[c[i] > 0]
            gap = np.maximum(np.maximum(active.min(axis=0) - measured[i], measured[i] - active.max(axis=0)), 0)
            if gap.max() > 0.001:
                violations.append({'source_row': int(rows[i]), 'family': study.family(c[i]),
                    'max_outside_envelope': float(gap.max()), 'bands_over_threshold': int((gap > 0.001).sum()),
                    'worst_wavelength_nm': int(400 + 10 * np.argmax(gap))})
        envelope['roles'][role] = {'count': int(mask.sum()), 'violations': violations}
    verification['posthoc_fixed_pure_envelope_diagnostic'] = envelope
    study.write_json(out / 'verification.json', verification)
    print(json.dumps(verification, indent=2))


if __name__ == '__main__':
    main()
