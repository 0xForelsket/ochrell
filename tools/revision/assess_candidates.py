from sweep_basis import *
import colorsys
# These probes use broad color families; no external engine is an objective.
rng=np.random.default_rng(20260930)
ys=np.array([colorsys.hsv_to_rgb(rng.uniform(45,75)/360,rng.uniform(.6,.95),rng.uniform(.5,1)) for _ in range(512)])
bs=np.array([colorsys.hsv_to_rgb(rng.uniform(220,255)/360,rng.uniform(.6,.95),rng.uniform(.2,1)) for _ in range(512)])
tints=rng.uniform(0,1,(1024,3))
def f(c,b):return prior(linear(c))@b
def bulk(a,b,t,basis,beta,white):
 ra=np.array([f(c,basis) for c in a]);rb=np.array([f(c,basis) for c in b])
 ea=linear(a)-ra@A.T;eb=linear(b)-rb@A.T
 def encode(r,c):
  q=(1-r)**2/(2*r);y=r@m.xyz[:,1];sn=2*y/(1+y*y)
  s=(1+q)**(-beta)*sn[:,None]**(1-beta)
  strength=1+(white-1)*linear(c).min(axis=1)
  return q*s*strength[:,None],s*strength[:,None]
 ka,sa=encode(ra,a);kb,sb=encode(rb,b)
 q=((1-t)*ka+t*kb)/((1-t)*sa+t*sb);r=1/(1+q+np.sqrt(q*(q+2)))
 raw=r@A.T+(1-t)*ea+t*eb
 return gamut(raw),raw
def hue(x):
 v=lab(x);return np.arctan2(v[:,2],v[:,1]),np.linalg.norm(v[:,1:],axis=1)
rows=[];b=logit_basis(.001)
np.save(ROOT/'results/revision/logit_basis_selected.npy',b)
for beta in [0,.125,.25,.5,.75,1]:
 for white in [1,2,4]:
  g,raw=bulk(ys,bs,.5,b,beta,white);h,c=hue(g)
  green=(g[:,1]>g[:,0])&(g[:,1]>g[:,2])&(c>=.03)
  a,_=bulk(tints,np.ones_like(tints),.5,b,beta,white)
  h0,c0=hue(linear(tints));h1,c1=hue(a)
  diff=np.abs(np.angle(np.exp(1j*(h1-h0))))*180/np.pi
  mask=(c0>.04)&(c1>.02)
  mono=np.ones(len(tints),dtype=bool);prev=linear(tints)@np.array([.2126,.7152,.0722])
  for t in np.linspace(0,1,33)[1:]:
   x,_=bulk(tints,np.ones_like(tints),t,b,beta,white);y=x@np.array([.2126,.7152,.0722]);mono&=y>=prev-1e-8;prev=y
  rows.append({'beta':beta,'white':white,'green_fraction':float(green.mean()),'tint_hue_median':float(np.median(diff[mask])),'tint_hue_p95':float(np.quantile(diff[mask],.95)),'tint_luminance_monotone_fraction':float(mono.mean())})
print(json.dumps(rows,indent=2))
(ROOT/'results/revision/candidate_validation.json').write_text(json.dumps(rows,indent=2)+'\n')
# Also retain the finite-palette alternative using newly fitted R and old S.
pal=Model(5);pal.r=b;pal.k=(1-b)**2/(2*b)*pal.s[:,None]
results=[]
for name,a,c in pairs:
 x=pal.mix(np.array(a)/255,np.array(c)/255,.5)
 results.append({'pair':name,'rgb8':np.rint(255*srgb(x)).astype(int).tolist()})
(ROOT/'results/revision/refitted_palette.json').write_text(json.dumps(results,indent=2)+'\n')
print('Refitted palette:',results)
