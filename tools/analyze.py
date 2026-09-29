"""Metrics and ablations from recorded Rust outputs; no invented measurements."""
from model import *
import colour,csv,json,platform,subprocess,sys
CFG=tomllib.loads((ROOT/'config.toml').read_text());OUT=ROOT/CFG['paths']['results'];OUT.mkdir(exist_ok=True)
def read(p):return np.genfromtxt(p,delimiter=',',names=True,dtype=None,encoding='utf8')
def cols(d,p):return np.column_stack([d[p+c] for c in ['r','g','b']])
def de(a,b):
 xyz=lambda c:linear(c)@np.linalg.inv(M).T
 return colour.delta_E(colour.XYZ_to_Lab(xyz(a)),colour.XYZ_to_Lab(xyz(b)),method='CIE 2000')
def stats(x):return dict(mean=float(np.mean(x)),median=float(np.median(x)),p95=float(np.percentile(x,95)),p99=float(np.percentile(x,99)),max=float(np.max(x)))
d=read(OUT/'reconstruction/samples.csv');src=cols(d,'');raw=srgb(gamut(cols(d,'raw_')));fastraw=srgb(gamut(cols(d,'fast_raw_')))
summary={'reconstruction':{}}
for label,values in [('reference_hybrid',cols(d,'ref_')),('fast_hybrid',cols(d,'fast_')),('reference_no_residual',raw),('fast_no_residual',fastraw)]:
 errors=de(src,values);summary['reconstruction'][label]={'deltaE00':stats(errors),'deltaEOK100':stats(100*np.linalg.norm(lab(linear(src))-lab(linear(values)),axis=1)),'max_channel_error':float(np.max(np.abs(src-values)))}
 np.savetxt(OUT/'reconstruction'/f'{label}_errors.csv',np.c_[errors,100*np.linalg.norm(lab(linear(src))-lab(linear(values)),axis=1)],delimiter=',',header='deltaE00,deltaEOK100',comments='')
# Cross-language reference, using the exact recorded Rust concentrations.
w=np.column_stack([d['w'+str(i)] for i in range(8)]);p=Model().forward(w)
summary['cross_language_max_linear_error']=float(np.max(np.abs(p-cols(d,'raw_'))))
# Spectral sampling, fixed weights: isolates decoder, not inversion changes.
ref=srgb(gamut(p));spect=[]
for step in [1,5,10,20,40]:
 pred=srgb(gamut(Model(step).forward(w)));spect.append({'step_nm':step,**stats(de(ref,pred))})
summary['spectral_resolution']=spect
precision=read(OUT/'reconstruction/precision.csv')
assert len(precision)==len(d), 'precision and reconstruction datasets differ in length'
f32=cols(precision,'');f64=Model(20).forward(w)
summary['precision_max_linear_error']=float(np.max(np.abs(f32-f64)))
summary['precision_deltaE00']=stats(de(srgb(gamut(f32)),srgb(gamut(f64))))
random_smooth=read(OUT/'mixing/random_smoothness.csv')
summary['random_smoothness_max_step']=float(np.max(random_smooth['max_step_deltaEOK100']))
assert np.isfinite(f32).all() and np.isfinite(cols(d,'ref_')).all()
# Independent optimizer diagnostic on the first 128 recorded input colors.
model=Model();rust_loss=[];oracle_loss=[]
for c,weights in zip(src[:128],w[:128]):
 prior_w=prior(c);target=lab(linear(c))
 loss=lambda weights:float(np.sum((lab(model.forward(weights))-target)**2)+CFG['model']['regularization']*np.sum((weights-prior_w)**2))
 rust_loss.append(loss(weights));oracle_loss.append(loss(model.invert(c)))
np.savetxt(OUT/'ablations/solver.csv',np.c_[rust_loss,oracle_loss],delimiter=',',header='rust_objective,slsqp_objective',comments='')
summary['solver_objective_excess_vs_slsqp']=stats(np.array(rust_loss)-oracle_loss)
pairs=read(OUT/'mixing/random_pairs.csv');summary['lut']={}
for label in ['n17_','n33_','n65_','tri33_']:
 e=de(cols(pairs,'ref_'),cols(pairs,label));summary['lut'][label]={'deltaE00':stats(e),'deltaEOK100':stats(100*np.linalg.norm(lab(linear(cols(pairs,'ref_')))-lab(linear(cols(pairs,label))),axis=1))}
rawmix=cols(pairs,'raw_');summary['random_mix_gamut_fraction']=float(np.mean(np.any((rawmix<0)|(rawmix>1),axis=1)))
summary['random_mix_raw_range']=[float(rawmix.min()),float(rawmix.max())]
raw_palette=raw.copy()
g=read(OUT/'mixing/gradients.csv');smooth=[];midpoints=[]
for name in np.unique(g['pair']):
 for mode in np.unique(g['mode']):
  z=g[(g['pair']==name)&(g['mode']==mode)];x=cols(z,'');l=lab(linear(x));diff=100*np.linalg.norm(np.diff(l,axis=0),axis=1)
  raw=cols(z,'raw_');smooth.append({'pair':name,'mode':int(mode),'max_step_deltaEOK100':float(diff.max()),'max_second_difference':float((100*np.linalg.norm(np.diff(l,n=2,axis=0),axis=1)).max()),'gamut_fraction':float(np.mean(np.any((raw<0)|(raw>1),axis=1))),'min_luminance':float(np.min(linear(x)@np.array([.2126,.7152,.0722]))),'finite':bool(np.isfinite(x).all())})
  if mode==3:midpoints.append({'pair':name,'srgb8':np.rint(x[len(x)//2]*255).astype(int).tolist()})
summary['smoothness']=smooth;summary['midpoints']=midpoints
perf=read(OUT/'performance/raw.csv');names=['sRGB','linear RGB','OKLab','reference RGB','fast RGB','fast cached latent','tetrahedral lookup','reference cached latent','trilinear lookup','LUT parsing']
summary['performance']={}
for mode in range(10):
 z=perf[perf['mode']==mode]['ns_per_operation'];v=stats(z);v['million_per_second']=1000/v['median'];summary['performance'][names[mode]]=v
worst=np.argsort(de(src,raw_palette))[-20:][::-1]
with open(OUT/'reconstruction/worst.csv','w') as f:
 writer=csv.writer(f);writer.writerow(['id','r','g','b','raw_r','raw_g','raw_b','deltaE00']);writer.writerows([[int(d['id'][i]),*src[i],*raw_palette[i],float(de(src[i],raw_palette[i]))] for i in worst])
# Small, fully specified ablation set. SLSQP is a separate oracle, not runtime inversion.
rng=np.random.default_rng(CFG['experiments']['seed']);samples=rng.random((128,3));abl=[]
for label,active,ws in [('CMYW',[0,1,2,3],None),('CMYWK',[0,1,2,3,7],None),('eight',None,None),('no_white',list(range(1,8)),None),('equal_scattering',None,1.)]:
 mod=Model(active=active,white_s=ws);pred=np.array([srgb(gamut(mod.forward(mod.invert(c)))) for c in samples]);abl.append({'label':label,**stats(de(samples,pred))})
 np.savetxt(OUT/'ablations'/f'{label}.csv',np.c_[samples,pred,de(samples,pred)],delimiter=',',header='r,g,b,out_r,out_g,out_b,deltaE00',comments='')
summary['basis_ablation']=abl
# Verify explicit white-scattering influence on canonical RGB mixtures.
tints=[]
for ws in [1.,8.]:
 mod=Model(white_s=ws)
 for name,a,b in PAIRS:
  if 'white' in name:
   pred=srgb(mod.mix(np.array(a)/255,np.array(b)/255,.5));tints.append({'white_S':ws,'pair':name,'srgb8':np.rint(pred*255).astype(int).tolist()})
summary['white_tints']=tints
(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
(ROOT/'paper/legacy/tables/summary.json').write_text(json.dumps(summary,indent=2)+'\n')
with open(ROOT/'paper/legacy/tables/reconstruction.csv','w') as f:
 writer=csv.writer(f);writer.writerow(['model','mean','median','p95','p99','max']);writer.writerows([[k,*v['deltaE00'].values()] for k,v in summary['reconstruction'].items()])
with open(ROOT/'paper/legacy/tables/lut.csv','w') as f:
 writer=csv.writer(f);writer.writerow(['mode','mean','median','p95','p99','max']);writer.writerows([[k,*v['deltaE00'].values()] for k,v in summary['lut'].items()])
print(json.dumps({k:summary[k] for k in ['reconstruction','cross_language_max_linear_error','lut','performance','midpoints','random_mix_gamut_fraction']},indent=2))
