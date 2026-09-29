"""Scientific figures from recorded CSV/JSON and generated basis spectra."""
import sys,io,os,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from revision.analyze import read,cols,de
from model import ROOT,linear,lab,srgb,gamut
import numpy as np
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42})
OUT=ROOT/'results/revision';FIG=ROOT/'paper/figures';FIG.mkdir(exist_ok=True)
S=json.loads((OUT/'summary.json').read_text())
def save(fig,name):
 for ext in ['png','pdf']:
  buf=io.BytesIO();fig.savefig(buf,format=ext,dpi=180,bbox_inches='tight')
  with (FIG/f'{name}.{ext}').open('wb') as f:f.write(buf.getvalue());f.flush();os.fsync(f.fileno())
 plt.close(fig)
def gradients():
 d=read('canonical');names=list(dict.fromkeys(d['pair']));methods=['srgb','linear','oklab','old','new'];titles=['Encoded sRGB','Linear RGB','OKLab','Ours v0.1','Ours v0.2']
 fig,axs=plt.subplots(len(names),len(methods),figsize=(13,9),gridspec_kw={'hspace':.55,'wspace':.06})
 for i,name in enumerate(names):
  z=d[d['pair']==name]
  for j,m in enumerate(methods):
   ax=axs[i,j];ax.imshow(cols(z,m+'_')[None,:,:],aspect='auto',extent=[0,1,0,1]);ax.set_xticks([]);ax.set_yticks([]);ax.spines[:].set_visible(False)
   if i==0:ax.set_title(titles[j],fontsize=11,pad=12)
   if j==0:ax.set_ylabel(({'official_default':'Dark blue + yellow','extreme_yellow_blue':'Pure yellow + blue'}.get(name,name.replace('_',' + '))),rotation=0,ha='right',va='center',fontsize=9,labelpad=10)
 fig.suptitle('Canonical mixture trajectories · t = 0 → 1',y=.97,fontsize=14);save(fig,'comparisons')
 # Observational external output, with only three sampled Mixbox patches shown.
 readx=lambda f:np.genfromtxt(OUT/'external'/f,names=True,delimiter=',',dtype=None,encoding='utf8')
 sp=readx('spectral.csv');ours=readx('ours.csv');mb=readx('mixbox_samples.csv')
 fig,axs=plt.subplots(len(names),4,figsize=(12,9),gridspec_kw={'hspace':.55,'wspace':.08})
 for i,name in enumerate(names):
  z=ours[ours['pair']==name];ss=sp[sp['pair']==name];mm=mb[mb['pair']==name]
  arrays=[cols(z,'old_'),cols(z,'new_'),cols(ss)/255,cols(mm,'mixbox_')/255]
  for j,x in enumerate(arrays):
   ax=axs[i,j];ax.imshow(x[None,:,:],aspect='auto',interpolation='nearest');ax.axis('off')
   if i==0:ax.set_title(['Ours v0.1','Ours v0.2','Spectral.js 3.0','Mixbox JPEG samples\nt = ¼, ½, ¾'][j],fontsize=11)
   if j==0:ax.text(-.04,.5,({'official_default':'Dark blue + yellow','extreme_yellow_blue':'Pure yellow + blue'}.get(name,name.replace('_',' + '))),transform=ax.transAxes,ha='right',va='center',fontsize=9)
 fig.suptitle('Engine similarity is not real-paint accuracy',y=.98,fontsize=14);save(fig,'external_comparison')
def reconstruction():
 d=read('reconstruction');src=cols(d);old=de(src,srgb(gamut(cols(d,'old_raw_'))));new=de(src,srgb(gamut(cols(d,'new_raw_'))));l=lab(linear(src));C=np.linalg.norm(l[:,1:],axis=1)
 fig,axs=plt.subplots(1,3,figsize=(13,3.7),constrained_layout=True)
 for ax,e,name in zip(axs[:2],[old,new],['v0.1 raw palette','v0.2 raw spectrum']):
  ix=np.argsort(e);p=ax.scatter(l[ix,0],C[ix],c=e[ix],s=4,norm=LogNorm(.001,50),cmap='magma',rasterized=True);ax.set(xlabel='Source OKLab L',ylabel='Source OKLab chroma',title=name)
 fig.colorbar(p,ax=list(axs[:2]),label='ΔE2000',shrink=.8)
 bins=np.geomspace(.001,50,60);axs[2].hist(old,bins=bins,histtype='step',lw=1.5,label='v0.1');axs[2].hist(new,bins=bins,histtype='step',lw=1.5,label='v0.2');axs[2].set(xscale='log',xlabel='Uncorrected ΔE2000',ylabel='Count',title='Same 10,000 inputs');axs[2].legend();save(fig,'reconstruction')
 # Explicit worst examples, so dark-region errors are visible.
 ix=np.argsort(new)[-12:][::-1];fig,axs=plt.subplots(1,3,figsize=(8,5))
 for ax,x,title in zip(axs,[src[ix],srgb(gamut(cols(d,'old_raw_')))[ix],srgb(gamut(cols(d,'new_raw_')))[ix]],['Source','v0.1 raw','v0.2 raw']):
  ax.imshow(x[:,None,:],aspect='auto');ax.set_title(title);ax.set_xticks([]);ax.set_yticks(range(12),[f'{v:.3f}' for v in new[ix]] if ax==axs[0] else []);ax.spines[:].set_visible(False)
 axs[0].set_ylabel('v0.2 ΔE2000, worst first');save(fig,'worst_reconstruction')
 np.savetxt(OUT/'worst_reconstruction.csv',np.c_[d['id'][ix],src[ix],old[ix],new[ix]],delimiter=',',header='id,r,g,b,old_deltaE00,new_deltaE00',comments='')
def trajectories():
 d=read('canonical');fig,axs=plt.subplots(2,3,figsize=(11,6),constrained_layout=True)
 for row,name in enumerate(['red_white','official_default']):
  z=d[d['pair']==name]
  for p,label in [('old_','v0.1'),('new_','v0.2')]:
   x=linear(cols(z,p));l=lab(x);C=np.linalg.norm(l[:,1:],axis=1);h=np.rad2deg(np.unwrap(np.arctan2(l[:,2],l[:,1])));h[C<.02]=np.nan
   for ax,y,title in zip(axs[row],[h,C,x@np.array([.2126,.7152,.0722])],['OKLab hue (degrees)','OKLab chroma','Relative luminance']):
    ax.plot(z['t'],y,label=label);ax.set(xlabel='White fraction' if row==0 else 'Yellow fraction',ylabel=title);ax.grid(alpha=.2)
  axs[row,0].set_title(({'official_default':'Dark blue + yellow','extreme_yellow_blue':'Pure yellow + blue'}.get(name,name.replace('_',' + '))));axs[row,2].legend()
 save(fig,'trajectories')
def ablations():
 rows=json.loads((OUT/'candidate_validation.json').read_text());fig,axs=plt.subplots(1,3,figsize=(12,3.7),constrained_layout=True)
 for white in [1,2,4]:
  z=[r for r in rows if r['white']==white];x=[r['beta'] for r in z]
  axs[0].plot(x,[100*r['green_fraction'] for r in z],'o-',label=f'white strength {white}');axs[1].plot(x,[r['tint_hue_p95'] for r in z],'o-')
 for ax in axs[:2]:ax.set_xlabel('Optical normalization β');ax.axvline(.5,c='black',ls=':',alpha=.5);ax.grid(alpha=.2)
 axs[0].set_ylabel('Green-dominant mixtures (%)');axs[1].set_ylabel('Tint hue shift P95 (degrees)');axs[0].legend(fontsize=8)
 z=S['resolution'];z=[r for r in z if r['step_nm']!=5]
 for k in ['mean','p95','max']:axs[2].plot([r['step_nm'] for r in z],[r[k] for r in z],'o-',label=k)
 axs[2].set(xlabel='Sample interval (nm)',ylabel='ΔE2000 relative to 5 nm',yscale='log');axs[2].legend();axs[2].grid(alpha=.2);save(fig,'ablations')
def spectra():
 d=np.loadtxt(ROOT/'data/optical_basis.csv',delimiter=',',skiprows=1);fig,axs=plt.subplots(1,2,figsize=(10,3.5),constrained_layout=True)
 for i,c in zip([2,3,4,5,6,7],['c','m','#d6ad00','r','g','b']):axs[0].plot(d[:,0],d[:,i],c=c,label=['nm','W','C','M','Y','R','G','B','K'][i])
 axs[0].set(xlabel='Wavelength (nm)',ylabel='Reflectance',ylim=(-.03,1.03),title='Independently fitted anchors');axs[0].legend(ncol=3)
 # Optical coefficients are a recorded deterministic model evaluation.
 from optical_model import OpticalModel
 model=OpticalModel(d[:,1:].T,5);k,s,e=model.encode(np.array([20,70,255])/255)
 np.savetxt(OUT/'blue_optics.csv',np.c_[d[:,0],k[0],s[0]],delimiter=',',header='nm,K,S',comments='')
 axs[1].plot(d[:,0],k[0],label='K');axs[1].plot(d[:,0],s[0],label='S');axs[1].set(xlabel='Wavelength (nm)',ylabel='Relative coefficient',yscale='log',title='Synthetic blue optical state');axs[1].legend();save(fig,'spectra')
def performance():
 p=S['performance'];names=list(p);fig,ax=plt.subplots(figsize=(10,3.7),constrained_layout=True);v=[p[n]['median'] for n in names]
 bars=ax.barh(names,v,color=['#8296a7']*3+['#aaa','#327d69','#327d69','#327d69','#aaa']);ax.set(xscale='log',xlabel='Nanoseconds per operation, median of seven repetitions');ax.invert_yaxis();ax.grid(axis='x',alpha=.2)
 for bar,x in zip(bars,v):ax.text(x*1.05,bar.get_y()+bar.get_height()/2,f'{x:.0f} ns',va='center',fontsize=9)
 ax.set_xlim(10,4000);save(fig,'performance')
def pipeline():
 from matplotlib.patches import FancyBboxPatch
 fig,ax=plt.subplots(figsize=(12,2.6));ax.axis('off');xs=[.02,.225,.43,.635,.84]
 labels=['sRGB inputs\nDecode gamma','Continuous recipe\nSmooth spectrum','Optical prior\nK, S, residual','Weighted state\nKM reflectance','Color projection\nGamut + sRGB']
 for i,(x,label) in enumerate(zip(xs,labels)):
  ax.add_patch(FancyBboxPatch((x,.28),.14,.48,boxstyle='round,pad=.015',facecolor='#e8f1ed',edgecolor='#327d69',transform=ax.transAxes));ax.text(x+.07,.52,label,ha='center',va='center',transform=ax.transAxes,fontsize=10)
  if i<4:ax.annotate('',xy=(xs[i+1]-.02,.52),xytext=(x+.16,.52),xycoords='axes fraction',arrowprops={'arrowstyle':'->','color':'#444'})
 ax.text(.5,.07,'Anchor fitting happens offline. The runtime encoder has no optimizer or LUT.',ha='center',transform=ax.transAxes);save(fig,'pipeline')
if __name__=='__main__':
 gradients();reconstruction();trajectories();ablations();spectra();performance();pipeline()
