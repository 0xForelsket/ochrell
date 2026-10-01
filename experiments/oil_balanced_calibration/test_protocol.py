import unittest
from unittest.mock import patch
import numpy as np
import run


class Protocol(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c, cls.r, cls.original = run.previous.inputs()
        cls.settings = cls.original['original_manifest']['settings']

    def test_fold_weights_and_exclusions(self):
        c, r, manifest, _ = run.inputs()
        assigned = []
        for name, fold in manifest['folds'].items():
            self.assertEqual(fold['test_rows'], self.original['folds'][name]['test_rows'])
            job = manifest['jobs'][fold['models']['balanced']]
            rows = job['train_rows']
            self.assertEqual(rows, self.original['jobs'][fold['models']['expanded']]['train_rows'])
            self.assertFalse(set(rows) & set(fold['test_rows']))
            assigned.extend(fold['test_rows'])
            x = c[np.array(rows)-1]
            labels = run.categories(x)
            weights, _ = run.weights(x)
            m = (labels >= 0).sum()
            self.assertAlmostEqual(weights.sum(), len(rows))
            np.testing.assert_array_equal(weights[labels == -1], np.ones(8))
            for g in range(4):
                self.assertAlmostEqual(weights[labels == g].sum(), m/4)
            self.assertTrue(set(np.flatnonzero((c > 0).sum(1) == 1)+1) <= set(rows))
        self.assertEqual(len(assigned), len(set(assigned)))
        self.assertEqual(set(assigned), set(manifest['primary_rows']+manifest['binary_assessment_rows']))

    def test_weighted_objective_normalization_priors_and_jacobians(self):
        c, target = self.c, self.r
        weights, _ = run.weights(c)
        labels = run.categories(c)
        rng = np.random.default_rng(20261002)
        q = run.method.pure_q(c, target)
        u = rng.uniform(-.2, .2, 217)
        _, x = run.method.features(c)
        base = run.method.forward(c, q, u)[0]
        active = np.max(abs(x), axis=(0, 1)) > 0
        objectives = [
            (run.method.base_objective(c, target, q, self.settings), u),
            (run.method.emp.objective(base, x, target, active), rng.uniform(-.2, .2, int(active.sum())))
        ]
        for original, z in objectives:
            fun, jac = run.weighted_objective(original, weights, 31)
            raw, actual = original[0](z), fun(z)
            count = target.size
            np.testing.assert_array_equal(actual[count:], raw[count:])
            np.testing.assert_array_equal(jac(z)[count:], original[1](z)[count:])
            # Independent category-mean form including unchanged pure-row term.
            per_row_mse = (raw[:count].reshape(len(c), 31)**2).sum(1)*len(c)
            expected = sum(per_row_mse[labels == g].mean() for g in range(4))/4*((labels >= 0).sum()/len(c))
            expected += per_row_mse[labels == -1].sum()/len(c)
            self.assertAlmostEqual(float(actual[:count]@actual[:count]), float(expected), places=14)
            direction = rng.normal(size=len(z))
            direction /= np.linalg.norm(direction)
            numerical = (fun(z+1e-6*direction)-fun(z-1e-6*direction))/(2e-6)
            np.testing.assert_allclose(numerical, jac(z)@direction, rtol=1e-5, atol=1e-9)
            uniform = run.weighted_objective(original, np.ones(len(c)), 31)
            np.testing.assert_array_equal(uniform[0](z), raw)
            np.testing.assert_array_equal(uniform[1](z), original[1](z))

    def test_only_selected_rows_reach_both_weighting_and_fitting(self):
        rows = next(job['train_rows'] for job in self.original['jobs'].values() if job['approach'] == 'expanded')
        idx = np.array(rows)-1
        weights, counts = run.weights(self.c[idx])
        job = {'train_rows': rows, 'row_weights': weights.tolist(), 'category_counts': counts}
        seen = []
        def capture(c, r, settings):
            seen.append((c.copy(), r.copy()))
            return {}
        with patch.object(run, 'fit', capture):
            for perturb in (False, True):
                _, result = run.worker('test', self.c, self.r, job, self.settings, perturb)
                self.assertEqual(result['status'], 'success')
        for c, r in seen:
            np.testing.assert_array_equal(c, self.c[idx])
            np.testing.assert_array_equal(r, self.r[idx])


if __name__ == '__main__':
    unittest.main()
