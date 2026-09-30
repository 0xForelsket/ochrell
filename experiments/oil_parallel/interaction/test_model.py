import unittest
import run as m
import numpy as np
from scipy.optimize import least_squares

class NumericalTests(unittest.TestCase):
    def test_derivative_and_scalar(self):
        rng=np.random.default_rng(1);c=rng.dirichlet(np.ones(4),13);c,x=m.features(c)
        base=rng.uniform(.05,.95,(13,31));z=rng.uniform(-.3,.3,24);active=np.ones(24,dtype=bool)
        fun,jac=m.objective(base,x,base,active);eps=1e-6
        numerical=np.column_stack([(fun(z+np.eye(24)[i]*eps)-fun(z-np.eye(24)[i]*eps))/(2*eps) for i in range(24)])
        np.testing.assert_allclose(jac(z),numerical,atol=1e-10)
        reference=np.empty_like(base)
        import math
        for i in range(13):
            for band in range(31):
                shift=sum(4*c[i,a]*c[i,b]*sum(m.B[band,k]*z[4*p+k] for k in range(4)) for p,(a,b) in enumerate(m.PAIRS))
                reference[i,band]=1/(1+math.exp(-math.log(base[i,band]/(1-base[i,band]))-shift))
        np.testing.assert_allclose(m.forward(base,x,z),reference,atol=3e-16)

    def test_synthetic_recovery(self):
        c=np.vstack([np.eye(4)[a]*f+np.eye(4)[b]*(1-f) for a,b in m.PAIRS for f in (.1,.3,.5,.7,.9)])
        _,x=m.features(c);base=np.full((len(c),31),.4);theta=np.linspace(-.2,.2,24);target=m.forward(base,x,theta)
        sol=least_squares(lambda z:(m.forward(base,x,z)-target).ravel(),np.zeros(24),gtol=1e-12,ftol=1e-12,xtol=1e-12)
        np.testing.assert_allclose(sol.x,theta,atol=1e-7)

    def test_endpoints_bounds_and_mass(self):
        rng=np.random.default_rng(4);c=np.vstack((np.eye(4),rng.dirichlet(np.ones(4),2000)))
        _,x=m.features(c);_,x2=m.features(c*7);np.testing.assert_allclose(x,x2,atol=1e-15)
        base=rng.uniform(.001,.999,(len(c),31))
        for z in (np.full(24,.8),np.full(24,-.8),rng.uniform(-.8,.8,24)):
            p=m.forward(base,x,z);self.assertTrue(np.isfinite(p).all());self.assertTrue(((p>0)&(p<1)).all());np.testing.assert_array_equal(p[:4],base[:4]);self.assertLessEqual(np.max(abs(x@z)),1.2+1e-14)
        np.testing.assert_array_equal(m.forward(base,x,np.zeros(24)),base)
        for bad in ([[0]*4],[[-1,2,0,0]],[[np.nan,1,0,0]],[[1,2,3]]):
            with self.assertRaises(ValueError):m.features(bad)

    def test_unseen_pair_zero(self):
        c=np.vstack((np.eye(4),[[.5,0,0,.5],[0,.5,0,.5],[0,0,.5,.5]]))
        _,x=m.features(c);active=np.max(abs(x),axis=(0,1))>0
        theta=np.zeros(24);theta[active]=.5
        for a,b in [(0,1),(0,2),(1,2)]:
            _,test=m.features([np.eye(4)[a]*.4+np.eye(4)[b]*.6]);np.testing.assert_array_equal(test@theta,np.zeros((1,31)))

if __name__=='__main__':unittest.main()
