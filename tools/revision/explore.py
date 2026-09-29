"""Independent candidates: fit only colorimetric anchor spectra, never mixtures."""
import sys,json,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from model import *
from scipy.optimize import lsq_linear

m=Model(5);A=m.rgb.T;n=A.shape[1]
targets=np.array([[1,1,1],[0,1,1],[1,0,1],[1,1,0],[1,0,0],[0,1,0],[0,0,1],[0,0,0]])
def fit_basis(floor=.001,ceil=.999,smooth=.01):
 D=np.diff(np.eye(n),axis=0)
 mat=np.vstack([A,smooth*D])
 return np.array([lsq_linear(mat,np.r_[t,np.zeros(n-1)],bounds=(floor,ceil),tol=1e-12,max_iter=500).x for t in targets])
def encode(c,basis):
 w=prior(linear(c));r=w@basis
 return r,linear(c)-r@A.T
def opts(r,mode):
 q=(1-r)**2/(2*r)
 if mode=='constant_s':return q,np.ones_like(q)
 if mode=='scalar_budget':
  e=1/(1+np.mean(q));return q*e,np.full_like(q,e)
 if mode=='luminance_budget':
  y=np.clip(r@m.xyz[:,1],.00001,1);s=2*y/(1+y*y);return q*s,np.full_like(q,s)
 if mode=='band_budget':
  return (1-r)**2/(1+r*r),2*r/(1+r*r)
 raise ValueError(mode)
def mix(a,b,t,basis,mode):
 ra,ea=encode(a,basis);rb,eb=encode(b,basis)
 ka,sa=opts(ra,mode);kb,sb=opts(rb,mode)
 q=((1-t)*ka+t*kb)/((1-t)*sa+t*sb)
 r=1/(1+q+np.sqrt(q*(q+2)))
 return srgb(gamut(r@A.T+(1-t)*ea+t*eb))
def run():
 basis=fit_basis();np.save(ROOT/'results/revision/anchor_basis.npy',basis)
 out={'anchor_linear_errors':(basis@A.T-targets).tolist(),'pairs':[]}
 pairs=PAIRS+[('official_default',[0,33,133],[252,210,0])]
 for name,a,b in pairs:
  a=np.array(a)/255;b=np.array(b)/255
  row={'pair':name}
  for mode in ['constant_s','scalar_budget','luminance_budget','band_budget']:
   row[mode]=np.rint(255*mix(a,b,.5,basis,mode)).astype(int).tolist()
  out['pairs'].append(row)
 print(json.dumps(out,indent=2));(ROOT/'results/revision/first_candidates.json').write_text(json.dumps(out,indent=2)+'\n')
if __name__=='__main__':run()
