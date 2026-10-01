import unittest
import numpy as np
import run


class Protocol(unittest.TestCase):
    def test_ratio_key_ignores_amount_and_white_but_not_chromatic_ratio(self):
        a=np.array([1.,2.,0.,0.,3.,0.,0.,0.])
        b=a*17;b[7]=123.
        self.assertEqual(run.ratio_key(a),run.ratio_key(b))
        b[0]+=1.
        self.assertNotEqual(run.ratio_key(a),run.ratio_key(b))
        with self.assertRaises(ValueError):run.ratio_key([0,0,0,0,0,0,0,1])
        with self.assertRaises(ValueError):run.ratio_key([1,0,0,0,0,0,0,1])

    def test_full_families_are_removed_from_both_stages_training_pools(self):
        c,_,_,_=run.method.inputs();folds,jobs,anchors=run.design(c)
        self.assertEqual(len(folds),107);self.assertEqual(len(jobs),158)
        assigned=[];pure=(c>0).sum(1)==1
        for fold in folds.values():
            idx=np.array(fold['test_rows'])-1;assigned.extend(idx.tolist())
            for label in ('binary','expanded'):
                train=np.zeros(len(c),dtype=bool);train[np.array(jobs[fold['models'][label]]['train_rows'])-1]=True
                self.assertFalse(train[idx].any());self.assertTrue(train[pure|anchors].all())
                allowed=np.ones(len(c),dtype=bool) if label=='expanded' else (c>0).sum(1)<=2
                allowed[idx]=False;np.testing.assert_array_equal(train,allowed)
                for x in c[train&~anchors]:self.assertNotEqual(run.ratio_key(x),tuple(fold['ratio']))
        self.assertEqual(len(assigned),len(set(assigned)))
        self.assertEqual(set(assigned),set(np.flatnonzero(~anchors)))
        self.assertEqual(sum((c[assigned]>0).sum(1)>=3),183)

    def test_fitter_receives_only_selected_rows(self):
        c=np.eye(8);r=np.arange(8*31,dtype=float).reshape(8,31)
        original=run.method.fit;seen=[]
        def capture(x,y,settings):seen.append((x.copy(),y.copy()));return {}
        try:
            run.method.fit=capture
            for perturb in (False,True):
                _,result=run.worker('test',c,r,{'train_rows':[1,3,8]}, {},perturb)
                self.assertEqual(result['status'],'success')
            for x,y in seen:
                np.testing.assert_array_equal(x,c[[0,2,7]])
                np.testing.assert_array_equal(y,r[[0,2,7]])
        finally:run.method.fit=original


if __name__=='__main__':unittest.main()
