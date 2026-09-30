"""Data-free numerical checks for the measured-oil research pipeline."""
import json
import math
import unittest

import numpy as np
import measured_oils as study


def synthetic():
    q = np.array([np.linspace(.02, 3., 31), np.linspace(4., .1, 31),
                  .4 + np.linspace(-1., 1., 31) ** 2, np.full(31, .003)])
    u = np.repeat(np.log([.2, 1.5, 4.]), 31)
    c = list(np.eye(4))
    for paint, steps in enumerate([5, 6, 6]):
        for part in np.linspace(.05, .95, steps):
            row = np.zeros(4); row[paint] = part; row[3] = 1 - part
            c.append(row)
    c = np.array(c)
    measured = study.predict(c, q, u)[0]
    return c, measured, q, u


class Numerics(unittest.TestCase):
    def test_km_scalar_reference_and_wavelength_gauge(self):
        c, _, q, u = synthetic()
        r, _, _, s, k = study.predict(c, q, u)
        for i, recipe in enumerate(c):
            for band in range(31):
                factor = .1 + band * .03
                ratio = sum(recipe[j] * k[j, band] * factor for j in range(4)) / sum(recipe[j] * s[j, band] * factor for j in range(4))
                direct = 1 + ratio - math.sqrt(ratio * ratio + 2 * ratio)
                self.assertAlmostEqual(r[i, band], direct, places=13)

    def test_pure_constraints_and_analytic_jacobian(self):
        c, measured, q, u = synthetic()
        np.testing.assert_allclose(study.pure_ratios(c, measured), q, atol=1e-14)
        settings = json.loads(study.CONFIG.read_text())
        residual, jac = study.objective(c, measured, q, settings)
        point = u + np.sin(np.arange(93)) * .1
        numeric = np.column_stack([(residual(point + np.eye(93)[j] * 1e-5) - residual(point - np.eye(93)[j] * 1e-5)) / 2e-5 for j in range(93)])
        np.testing.assert_allclose(jac(point), numeric, rtol=2e-6, atol=2e-10)

    def test_recover_known_scattering_from_noiseless_tints(self):
        c, measured, q, u = synthetic()
        settings = json.loads(study.CONFIG.read_text())
        settings['amplitude_weight'] = 0.0
        result = study.fit_model(c, measured, settings)
        found = np.asarray(result['log_relative_s']).ravel()
        np.testing.assert_allclose(found, u, atol=2e-4)
        np.testing.assert_allclose(study.predict(c, q, found)[0], measured, atol=2e-6)
        self.assertTrue(all(r['success'] for r in result['runs']))

    def test_color_difference_reference_and_truncated_white(self):
        import colour
        # Sharma et al. CIEDE2000 supplementary test pair 1.
        self.assertAlmostEqual(float(colour.delta_E([50., 2.6772, -79.7751], [50., 0., -82.7485], method='CIE 2000')), 2.0425, places=4)
        weights, white, lab = study.colorimetry()
        self.assertEqual(weights.shape, (31, 3))
        self.assertAlmostEqual(white[1], 1.)
        np.testing.assert_allclose(lab(np.ones((1, 31))), [[100., 0., 0.]], atol=1e-12)
        for v in study.errors(np.full((3,31),.5), np.full((3,31),.5), lab).values():
            np.testing.assert_array_equal(v, 0.)

    def test_source_validation_rejects_invalid_portions(self):
        for values in [np.zeros((286,8)), np.ones((285,8)), np.full((286,8),np.nan), np.full((286,8),-1.)]:
            with self.assertRaises(ValueError): study.partition(values)
        with self.assertRaises(ValueError): study.research_directory(study.ROOT / 'data/forbidden-measured-output')


if __name__ == '__main__':
    unittest.main()
