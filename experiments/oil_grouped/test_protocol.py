"""Checks for the new grouping boundary; the frozen model has its own tests."""
import unittest
from unittest.mock import patch

import numpy as np
import run as m


class GroupProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows, cls.c, cls.measured, cls.original = m.v1.load_source(m.SOURCE)

    def test_membership_coverage_and_anchor_preservation(self):
        primary, pairs, multi, folds = m.design(self.rows, self.c, self.original)
        self.assertEqual(len(folds), 11)
        self.assertEqual(len({tuple(self.rows[f['train']]) for f in folds.values()}), 9)
        for f in folds.values():
            self.assertFalse((f['train'] & f['test']).any())
            self.assertTrue(f['train'][self.original].all())
            self.assertFalse((f['train'] & multi).any())
        grouped = np.sum([f['test'] for f in folds.values()], axis=0)
        np.testing.assert_array_equal(grouped, (~self.original).astype(int))
        self.assertEqual(int(grouped[pairs].sum()), 8)
        self.assertEqual(int(grouped[multi].sum()), 16)

    def test_white_and_absolute_amount_do_not_change_group(self):
        for white in (0, .25, 2, 38, 999):
            self.assertEqual(m.ratio_key([1, 1, 0, white]), m.ratio_key([7, 7, 0, 7 * white]))
            self.assertEqual(m.ratio_label(m.ratio_key([1, 1, 0, white])), '1:1:0')
        self.assertNotEqual(m.ratio_key([1, 3, 0, 4]), m.ratio_key([3, 1, 0, 4]))
        scaled = self.c * np.arange(1, 46)[:, None]
        np.testing.assert_array_equal([m.ratio_key(x) for x in scaled[~self.original]],
                                      [m.ratio_key(x) for x in self.c[~self.original]])

    def test_fit_boundary_only_receives_calibration_arrays(self):
        _, _, _, folds = m.design(self.rows, self.c, self.original)
        for f in folds.values():
            changed = self.measured.copy()
            changed[~f['train']] = np.nan
            with patch.object(m.empirical, 'fit', return_value='checked') as fit:
                m.fit_training(self.c, changed, f['train'], {})
                passed_c, passed_r, _ = fit.call_args.args
                np.testing.assert_array_equal(passed_c, self.c[f['train']])
                np.testing.assert_array_equal(passed_r, self.measured[f['train']])
                self.assertTrue(np.isfinite(passed_r).all())

    def test_yellow_blue_interaction_is_unidentified_when_only_parent_excluded(self):
        _, _, _, folds = m.design(self.rows, self.c, self.original)
        f = folds['ratio-60']
        _, x = m.empirical.features(self.c[f['train']])
        active = abs(x).max(axis=(0, 1)) > 0
        pair = m.empirical.PAIRS.index((0, 2))
        self.assertFalse(active[pair * 4:pair * 4 + 4].any())
        self.assertEqual(int(active.sum()), 20)


if __name__ == '__main__':
    unittest.main()
