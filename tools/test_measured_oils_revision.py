"""Numerical checks for the single bounded pure-spectrum revision; no real data."""
import json
import unittest
import numpy as np
import measured_oils as v1
import measured_oils_revision as revision
from test_measured_oils import synthetic


class RevisionNumerics(unittest.TestCase):
    def test_zero_shift_reduces_to_original_model(self):
        c, measured, q, u = synthetic()
        pure = revision.pure_samples(c, measured)
        old = v1.predict(c, q, u)[0]
        new = revision.predict(c, pure, np.r_[u, np.zeros(20)])[0]
        np.testing.assert_allclose(new, old, atol=5e-16, rtol=0)

    def test_analytic_jacobian_including_pure_controls(self):
        c, measured, _, u = synthetic()
        pure = revision.pure_samples(c, measured)
        settings = json.loads(revision.CONFIG.read_text())
        residual, jacobian = revision.objective(c, measured, pure, settings)
        point = np.r_[u + .1 * np.cos(np.arange(93)), .001 * np.sin(np.arange(20))]
        numeric = []
        for j in range(113):
            h = 1e-5 if j < 93 else 1e-7
            shift = np.eye(113)[j] * h
            numeric.append((residual(point + shift) - residual(point - shift)) / (2 * h))
        np.testing.assert_allclose(jacobian(point), np.column_stack(numeric), rtol=2e-6, atol=2e-9)

    def test_basis_and_control_bounds_guarantee_finite_interior(self):
        c, measured, _, _ = synthetic()
        pure = revision.pure_samples(c, measured)
        pure[0, 0] = .00011; pure[1, -1] = .99989
        settings = json.loads(revision.CONFIG.read_text())
        b = revision.basis()
        self.assertTrue((b >= 0).all())
        np.testing.assert_allclose(b.sum(axis=1), 1., atol=1e-15)
        lower, upper = revision.bounds(pure, settings)
        for controls in [lower[93:], upper[93:], np.where(np.arange(20) % 2 == 0, lower[93:], upper[93:])]:
            _, _, _, _, _, corrected, _, delta = revision.predict(c, pure, np.r_[np.zeros(93), controls])
            self.assertTrue((corrected >= .0001 - 1e-15).all())
            self.assertTrue((corrected <= .9999 + 1e-15).all())
            self.assertLessEqual(float(np.abs(delta).max()), .02 + 1e-15)

    def test_noiseless_tints_recover_strength_without_pure_drift(self):
        c, measured, q, u = synthetic()
        settings = json.loads(revision.CONFIG.read_text())
        settings['amplitude_weight'] = 0.
        model = revision.fit_model(c, measured, settings)
        found = np.asarray(model['log_relative_s']).ravel()
        np.testing.assert_allclose(found, u, atol=3e-4)
        np.testing.assert_allclose(model['pure_shift'], 0., atol=2e-6)
        reconstructed = v1.predict(c, np.asarray(model['q']), found)[0]
        np.testing.assert_allclose(reconstructed, measured, atol=3e-6)
        self.assertTrue(all(run['success'] for run in model['runs']))


if __name__ == '__main__':
    unittest.main()
