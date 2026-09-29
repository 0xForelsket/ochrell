"""Analyze observed demo pixels; these are approximate display comparisons."""
from pathlib import Path
import csv,json,tomllib,io,os
import numpy as np
from PIL import Image
import colour
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
CFG=tomllib.loads((ROOT/'config.toml').read_text());s=CFG['sampling']
manifest=json.loads((ROOT/'captures/manifest.json').read_text())
ours=np.genfromtxt(ROOT/'results/ours.csv',delimiter=',',names=True,dtype=None,encoding='utf8')
spectral=np.genfromtxt(ROOT/'results/spectral.csv',delimiter=',',names=True,dtype=None,encoding='utf8')
def rgb(h):return np.array([int(h[j:j+2],16) for j in [1,3,5]],dtype=float)
def lab(v):return colour.XYZ_to_Lab(colour.sRGB_to_XYZ(np.asarray(v)/255.))
def delta(a,b):return float(colour.delta_E(lab(a),lab(b),method='CIE 2000'))
def sample(im,x,y):return np.median(im[y,x-s['half_width']:x+s['half_width'],:3],axis=0)
def own_at(rows,t,prefix='fast'):
 return np.array([np.interp(t,rows['t'],rows[f'{prefix}_{c}']) for c in 'rgb'])*255
measurements=[];controls=[];midpoints=[];strips=[];spectral_measurements=[]
for case in manifest['cases']:
 im=np.array(Image.open(ROOT/'captures'/case['file']).convert('RGB'))
 assert im.shape==(936,1363,3),im.shape
 rows=ours[ours['pair']==case['pair']];sr=spectral[spectral['pair']==case['pair']];a=rgb(case['a']);b=rgb(case['b'])
 def spectral_at(t):return np.array([np.interp(t,sr['t'],sr[c]) for c in 'rgb'])
 for t in s['comparison_ratios']:
  y=round(s['y_start']+s['y_span']*t)
  mb=sample(im,s['mixbox_x'],y);our=own_at(rows,t);ref=own_at(rows,t,'ref')
  base=a*(1-t)+b*t;observed=sample(im,s['rgb_x'],y)
  de=delta(our,mb);control=delta(base,observed)
  measurements.append({'pair':case['pair'],'t':t,**dict(zip(['ours_r','ours_g','ours_b'],our)),**dict(zip(['mixbox_r','mixbox_g','mixbox_b'],mb)),'deltaE00_approx':de,'reference_deltaE00_approx':delta(ref,mb)})
  controls.append({'pair':case['pair'],'t':t,'max_channel_error':float(np.max(np.abs(base-observed))),'deltaE00':control})
  sp=spectral_at(t)
  spectral_measurements.append({'pair':case['pair'],'t':t,'r':sp[0],'g':sp[1],'b':sp[2],'vs_mixbox_deltaE00_approx':delta(sp,mb),'vs_ours_deltaE00':delta(sp,our)})
  if t==.5:midpoints.append({'pair':case['pair'],'a':case['a'],'b':case['b'],'ours':np.rint(our).astype(int).tolist(),'mixbox_approx':mb.astype(int).tolist(),'deltaE00_approx':de,'spectral':sp.astype(int).tolist(),'spectral_vs_mixbox_deltaE00_approx':delta(sp,mb),'spectral_vs_ours_deltaE00':delta(sp,our)})
 ys=np.arange(s['first_row'],s['last_row']+1);ts=(ys-s['y_start'])/s['y_span']
 mb=np.array([sample(im,s['mixbox_x'],int(y)) for y in ys])/255.
 fast=np.array([own_at(rows,t) for t in ts])/255.
 baseline=np.array([(1-t)*a+t*b for t in ts])/255.
 spbar=np.array([spectral_at(t) for t in ts])/255.
 strips.append((case,fast,mb,spbar,baseline))
for name,data in [('samples',measurements),('controls',controls),('spectral_samples',spectral_measurements)]:
 with (ROOT/f'results/{name}.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
vals=np.array([x['deltaE00_approx'] for x in measurements]);ct=np.array([x['deltaE00'] for x in controls])
summary={'scope':'13 fixed pairs, t=0.25,0.50,0.75; screenshot-based, not SDK numerical parity or paint accuracy','samples':len(vals),'mean_deltaE00_approx':float(vals.mean()),'median_deltaE00_approx':float(np.median(vals)),'max_deltaE00_approx':float(vals.max()),'control_mean_deltaE00':float(ct.mean()),'control_max_deltaE00':float(ct.max()),'control_max_channel_error':max(x['max_channel_error'] for x in controls),'midpoints':midpoints}
for key in ['vs_mixbox_deltaE00_approx','vs_ours_deltaE00']:
 v=np.array([x[key] for x in spectral_measurements]);summary['spectral_'+key]={'mean':float(v.mean()),'median':float(np.median(v)),'max':float(v.max())}
(ROOT/'results/summary.json').write_text(json.dumps(summary,indent=2)+'\n')

plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10})
fig=plt.figure(figsize=(CFG['figure']['width_inches'],CFG['figure']['height_inches']),facecolor='white')
grid=fig.add_gridspec(len(strips),4,left=.20,right=.98,top=.90,bottom=.09,wspace=.085,hspace=.51)
titles=['Our Rust mixer (fast 33³)','Mixbox (demo capture)','Spectral.js 3.0.0','sRGB interpolation']
for i,(case,*bars) in enumerate(strips):
 for j,bar in enumerate(bars):
  ax=fig.add_subplot(grid[i,j]);ax.imshow(np.clip(bar[None,:,:],0,1),aspect='auto',interpolation='nearest',extent=[.01,.99,0,1]);ax.set_xticks([]);ax.set_yticks([])
  for sp in ax.spines.values():sp.set_visible(False)
  if i==0:ax.set_title(titles[j],fontsize=10.5,pad=10,fontweight='bold')
  if j==0:
   label=case['pair'].replace('_',' + ') if case['pair']!='official_default' else 'Official demo default'
   if case['pair']=='extreme_yellow_blue':label='Pure yellow + pure blue'
   ax.text(-.065,.74,label,ha='right',va='center',transform=ax.transAxes,fontsize=9.5)
   ax.text(-.065,.15,f"{case['a'].upper()} → {case['b'].upper()}",ha='right',va='center',transform=ax.transAxes,fontsize=8,color='#555555')
fig.text(.035,.971,'Our pigment mixer vs Mixbox vs Spectral.js',fontsize=22,fontweight='bold',va='top')
fig.text(.035,.934,'Identical sRGB inputs and mixing factors • Spectral.js defaults • fixed Rust release, no retuning',fontsize=11,color='#555555')
fig.text(.035,.053,'Gradients: t = 0.01–0.99. Mixbox: approximate JPEG capture. Spectral.js: direct API RGB8, tinting strength 1, gamut method map.',fontsize=9,color='#444444')
fig.text(.035,.031,'Sources: official Mixbox demo and spectral.js@3.0.0 • 29 Sep 2026 • similarity between models is not validation against real paint.',fontsize=8.5,color='#444444')
for ext in ['png','pdf']:
 buf=io.BytesIO();fig.savefig(buf,format=ext,dpi=CFG['figure']['dpi'])
 with (ROOT/f'mixbox-comparison.{ext}').open('wb') as f:f.write(buf.getvalue());f.flush();os.fsync(f.fileno())
plt.close(fig)
print(json.dumps(summary,indent=2))
