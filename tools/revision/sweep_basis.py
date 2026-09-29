from sweep_optics import *
from scipy.optimize import least_squares
from scipy.special import expit,logit
def logit_basis(weight):
 D=np.diff(np.eye(n),axis=0)
 fitted=[]
 for j in [4,5,6]:
  z=logit(np.clip((basis[j]-.001)/.998,.0001,.9999))
  def fun(z):
   r=.001+.998*expit(z)
   return np.r_[A@r-targets[j],weight*D@z]
  def jac(z):
   v=expit(z);return np.vstack([A*(.998*v*(1-v))[None,:],weight*D])
  sol=least_squares(fun,z,jac=jac,max_nfev=2000,gtol=1e-12,ftol=1e-12,xtol=1e-12)
  fitted.append(.001+.998*expit(sol.x))
 red,green,blue=fitted
 return np.array([np.full(n,.999),1-red,1-green,1-blue,red,green,blue,np.full(n,.001)])
def run():
 rows=[]
 for smooth in [.0001,.001,.01,.03]:
  b=logit_basis(smooth);np.save(ROOT/f'results/revision/logit_basis_{smooth}.npy',b)
  print('smooth',smooth,'anchor error',np.max(np.abs(b@A.T-targets)))
  for beta in [0,.25,.5]:
   for name,a,c in pairs:
    aa=np.array(a)/255;bb=np.array(c)/255
    ra,ea=encode(aa,b);rb,eb=encode(bb,b)
    ka,sa=optical(ra,beta);kb,sb=optical(rb,beta)
    ka*=1+min(linear(aa));sa*=1+min(linear(aa));kb*=1+min(linear(bb));sb*=1+min(linear(bb))
    q=(ka+kb)/(sa+sb);r=1/(1+q+np.sqrt(q*(q+2)))
    x=srgb(gamut(r@A.T+.5*(ea+eb)))
    rows.append({'smooth':smooth,'beta':beta,'pair':name,**dict(zip('rgb',x))})
   print('beta',beta,[(x['pair'],np.rint([x[c]*255 for c in 'rgb']).astype(int).tolist()) for x in rows if x['smooth']==smooth and x['beta']==beta and x['pair'] in ['yellow_blue','red_blue','cyan_magenta','red_white','extreme_yellow_blue','official_default']])
 with (ROOT/'results/revision/basis_sweep.csv').open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

if __name__=="__main__":run()
