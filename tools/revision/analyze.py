"""Recorded v0.1/v0.2 comparisons and independent Python precision checks."""
import sys,json,csv
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from optical_model import *
from model import M,lab
import colour
OUT=ROOT/'results/revision'
def read(name):return np.genfromtxt(OUT/(name+'.csv'),delimiter=',',names=True,dtype=None,encoding='utf8')
def cols(d,p=''):return np.column_stack([d[p+c] for c in 'rgb'])
def de(a,b):
 xyz=lambda c:linear(c)@np.linalg.inv(M).T
 return colour.delta_E(colour.XYZ_to_Lab(xyz(a)),colour.XYZ_to_Lab(xyz(b)),method='CIE 2000')
def stats(x):return dict(zip(['mean','median','p95','p99','max'],map(float,[np.mean(x),*np.percentile(x,[50,95,99]),np.max(x)])))
def hue_difference(a,b):
 a=lab(linear(a));b=lab(linear(b));mask=(np.linalg.norm(a[:,1:],axis=1)>.04)&(np.linalg.norm(b[:,1:],axis=1)>.02)
 d=np.abs(np.angle(np.exp(1j*(np.arctan2(a[:,2],a[:,1])-np.arctan2(b[:,2],b[:,1])))))*180/np.pi
 return stats(d[mask]),int(mask.sum())
def run():
 s={};rec=read('reconstruction');src=cols(rec);s['reconstruction']={}
 for name,pred in [('v0.2 corrected',cols(rec,'new_')),('v0.2 raw',srgb(gamut(cols(rec,'new_raw_')))),('v0.1 raw',srgb(gamut(cols(rec,'old_raw_'))))]:
  e=de(src,pred);s['reconstruction'][name]={'deltaE00':stats(e),'max_srgb_channel_error':float(np.abs(src-pred).max())};np.savetxt(OUT/(name.replace(' ','_')+'_errors.csv'),e,header='deltaE00',comments='')
 grid=read('reconstruction_grid');s['grid_reconstruction']={'deltaE00':stats(de(cols(grid),cols(grid,'new_'))),'max_srgb_channel_error':float(np.abs(cols(grid)-cols(grid,'new_')).max())}
 mix=read('mixtures');s['fast_vs_reference']=stats(de(cols(mix,'new_'),cols(mix,'ref_')));raw=cols(mix,'raw_');s['gamut_fraction']=float(np.any((raw<0)|(raw>1),axis=1).mean());s['raw_range']=[float(raw.min()),float(raw.max())];s['decoder_precision_max']=float(mix['precision_error'].max())
 b=np.loadtxt(ROOT/'data/optical_basis.csv',delimiter=',',skiprows=1)[:,1:].T;a=cols(mix,'a');c=cols(mix,'b');t=mix['t'];ref=OpticalModel(b,5).mix(a,c,t);s['rust_python_ref_max_linear']=float(np.abs(linear(cols(mix,'ref_'))-ref).max())
 s['resolution']=[]
 for step in [1,5,10,20,40]:
  pred=OpticalModel(b,step).mix(a,c,t);errors=de(srgb(ref),srgb(pred));s['resolution'].append({'step_nm':step,**stats(errors)});np.savetxt(OUT/f'resolution_{step}.csv',errors,header='deltaE00_vs_5nm',comments='')
 pyfast=OpticalModel(b,CFG['optical']['fast_step_nm']).mix(a,c,t);s['fast_vs_python_same_step']=stats(de(cols(mix,'new_'),srgb(pyfast)));s['fast_python_max_linear']=float(np.abs(linear(cols(mix,'new_'))-pyfast).max())
 sm=read('smoothness');s['random_smoothness']={name:stats(sm[p]) for name,p in [('v0.1','old_max_step'),('v0.2','new_max_step')]};pert=read('perturbations');s['input_perturbations']={name:stats(pert[p]) for name,p in [('v0.1','old_delta'),('v0.2','new_delta')]}
 tint=read('tints');s['tints']={}
 for name,p in [('v0.1','old'),('v0.2','new')]:
  hue,count=hue_difference(cols(tint),cols(tint,p+'_'));s['tints'][name]={'hue_shift_degrees':hue,'eligible':count,'monotone_fraction':float((tint[p+'_min_dy']>=-2e-6).mean()),'minimum_luminance_step':float(tint[p+'_min_dy'].min())}
 s['tints']['black_endpoint_max_step']=float(tint['new_max_step'][0]);s['tints']['nonblack_max_step']=float(tint['new_max_step'][1:].max())
 can=read('canonical');s['midpoints']=[];s['canonical_smoothness']=[]
 for name in dict.fromkeys(can['pair']):
  d=can[can['pair']==name];i=np.argmin(abs(d['t']-.5));s['midpoints'].append({'pair':name,'v0.1':np.rint(cols(d,'old_')[i]*255).astype(int).tolist(),'v0.2':np.rint(cols(d,'new_')[i]*255).astype(int).tolist()})
  for method in ['srgb','linear','oklab','old','new']:
   v=lab(linear(cols(d,method+'_')));s['canonical_smoothness'].append({'pair':name,'method':method,'max_step':float(100*np.linalg.norm(np.diff(v,axis=0),axis=1).max())})
 hold=read('holdout_outputs');s['holdout_green_fraction']={}
 for name,p in [('v0.1','old_'),('v0.2','new_')]:
  x=linear(cols(hold,p));chroma=np.linalg.norm(lab(x)[:,1:],axis=1);s['holdout_green_fraction'][name]=float(((x[:,1]>x[:,0])&(x[:,1]>x[:,2])&(chroma>=.03)).mean())
 a=lab(linear(cols(tint)));old=lab(linear(cols(tint,'old_')));new=lab(linear(cols(tint,'new_')))
 mask=(np.linalg.norm(a[:,1:],axis=1)>.04)&(np.linalg.norm(old[:,1:],axis=1)>.02)&(np.linalg.norm(new[:,1:],axis=1)>.02)
 s['tints_common']={'eligible':int(mask.sum())}
 for name,x in [('v0.1',old),('v0.2',new)]:
  diff=np.abs(np.angle(np.exp(1j*(np.arctan2(a[:,2],a[:,1])-np.arctan2(x[:,2],x[:,1])))))*180/np.pi;s['tints_common'][name]=stats(diff[mask])
 perf=read('performance');s['performance']={}
 for name in dict.fromkeys(perf['method']):
  v=stats(perf['ns_per_mix'][perf['method']==name]);v['million_per_second']=1000/v['median'];s['performance'][name]=v
 assert all(np.isfinite(cols(mix,p)).all() for p in ['new_','ref_','old_','raw_'])
 (OUT/'summary.json').write_text(json.dumps(s,indent=2)+'\n');print(json.dumps(s,indent=2))
if __name__=='__main__':run()
