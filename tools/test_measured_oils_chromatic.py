"""Data-free checks of the v3 split, sensitivity calculation and scalar decoder."""
import unittest
import numpy as np
import measured_oils as v1
import measured_oils_chromatic as v3
from test_measured_oils import synthetic


def recipes():
    calibration, _, q, u = synthetic()
    result = list(calibration)
    for (a, b), count in [((0, 1), 5), ((0, 2), 1), ((1, 2), 2)]:
        for fraction in np.linspace(.1, .9, count):
            c = np.zeros(4); c[a] = fraction; c[b] = 1 - fraction
            result.append(c)
    for active, count in [([0, 1, 2], 3), ([0, 1, 3], 6), ([0, 2, 3], 2), ([1, 2, 3], 2), ([0, 1, 2, 3], 3)]:
        for j in range(count):
            c = np.zeros(4); c[active] = np.arange(1, len(active) + 1) + j
            result.append(c / c.sum())
    c = np.array(result)
    original = np.arange(len(c)) < 21
    return c, original, q, u


class ChromaticCalibration(unittest.TestCase):
    def test_whole_family_split_and_no_multicolor_leakage(self):
        c, original, _, _ = recipes()
        primary, pairs, multi, folds = v3.design(c, original)
        self.assertEqual((primary.sum(), pairs.sum(), multi.sum()), (29, 8, 16))
        self.assertFalse((primary & multi).any())
        evaluated = np.zeros(45, dtype=int)
        for family, (train, test) in folds.items():
            self.assertFalse((train & test).any())
            self.assertFalse((train & multi).any())
            self.assertTrue((train[original]).all())
            self.assertTrue(all(v1.family(row) == family for row in c[test]))
            self.assertTrue(all(v1.family(row) != family for row in c[train]))
            evaluated += test
        np.testing.assert_array_equal(evaluated, pairs.astype(int))

    def test_multichromatic_reflectance_and_fitting_jacobians(self):
        c, original, q, u = recipes()
        primary, _, _, _ = v3.design(c, original)
        analytic = v3.reflectance_jacobian(c, q, u)
        for j in range(3):
            for band in [0, 7, 15, 23, 30]:
                delta = np.zeros(93); delta[j * 31 + band] = 1e-5
                numeric = (v1.predict(c, q, u + delta)[0] - v1.predict(c, q, u - delta)[0]) / 2e-5
                np.testing.assert_allclose(numeric[:, band], analytic[:, band, j], rtol=1e-6, atol=2e-10)
        # The actual v1 fitter must also differentiate chromatic-pair residuals.
        settings = {'curvature_weight': .0001, 'amplitude_weight': 1e-8}
        r = v1.predict(c[primary], q, u)[0]
        residual, jacobian = v1.objective(c[primary], r, q, settings)
        for j in [0, 15, 30, 31, 62, 92]:
            delta = np.eye(93)[j] * 1e-5
            np.testing.assert_allclose((residual(u + delta) - residual(u - delta)) / 2e-5,
                                       jacobian(u)[:, j], rtol=1e-6, atol=2e-10)

    def test_sensitivity_information_and_independent_decoder(self):
        c, original, q, u = recipes()
        primary, _, _, _ = v3.design(c, original)
        r, _, _, s, k = v1.predict(c, q, u)
        model = {'q': q.tolist(), 'log_relative_s': u.reshape(3, 31).tolist(), 'K': k.tolist(), 'S': s.tolist()}
        rows, _ = v3.sensitivity(c, original, primary, model)
        self.assertEqual(len(rows), 31)
        for row in rows:
            self.assertGreaterEqual(row['with_pairs29_smallest_singular_value'] + 1e-12, row['white_tints21_smallest_singular_value'])
        self.assertLess(v3.independent_check(c, model, r), 1e-12)


if __name__ == '__main__':
    unittest.main()
