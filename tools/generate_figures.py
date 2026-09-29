from model import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt,json,shutil,io,os
OUT=ROOT/CFG['paths']['results'];FIG=ROOT/'paper/legacy/figures';FIG.mkdir(exist_ok=True,parents=True)
S=json.loads((OUT/'summary.json').read_text())
plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False,'savefig.dpi':180,'font.family':'DejaVu Sans'})
def save(name):
 for ext in ['png','pdf']:
  buf=io.BytesIO();plt.savefig(buf,format=ext,bbox_inches='tight',facecolor='white')
  with open(FIG/(name+'.'+ext),'wb') as f:f.write(buf.getvalue());f.flush();os.fsync(f.fileno())
 plt.close()
def cols(d,p=''):return np.column_stack([d[p+c] for c in ['r','g','b']])
g=np.genfromtxt(OUT/'mixing/gradients.csv',delimiter=',',names=True,dtype=None,encoding='utf8')
names=[p[0] for p in PAIRS];labels=['sRGB','Linear RGB','OKLab','Pigment (fast)'];fig,axes=plt.subplots(len(names),4,figsize=(10,9.5),gridspec_kw={'hspace':.60,'wspace':.06})
for row,name in enumerate(names):
 for mode in range(4):
  z=g[(g['pair']==name)&(g['mode']==mode)];ax=axes[row,mode];ax.imshow(cols(z)[None,:,:],aspect='auto',extent=[0,1,0,1]);ax.set_xticks([]);ax.set_yticks([])
  if row==0:ax.set_title(labels[mode],fontsize=10)
  if mode==0:ax.text(-.06,.5,name.replace('_',' + '),ha='right',va='center',transform=ax.transAxes,fontsize=8)
fig.suptitle('Canonical mixtures • fixed RGB endpoints • t = 0 → 1',y=.94);save('comparisons');shutil.copyfile(FIG/'comparisons.png',ROOT/'examples/comparisons/comparisons.png')
d=np.genfromtxt(OUT/'reconstruction/samples.csv',delimiter=',',names=True);errs=np.genfromtxt(OUT/'reconstruction/reference_no_residual_errors.csv',delimiter=',',names=True)
fig,ax=plt.subplots(1,2,figsize=(7,2.8));ax[0].hist(errs['deltaE00'],bins=50,color='#365e7d');ax[0].set(xlabel='CIEDE2000 without residual',ylabel='Count');hy=np.genfromtxt(OUT/'reconstruction/fast_hybrid_errors.csv',delimiter=',',names=True)['deltaE00'];ax[1].hist(np.log10(np.maximum(hy,1e-10)),bins=50,color='#548e6d');ax[1].set(xlabel='log10 CIEDE2000 with residual',ylabel='Count');fig.tight_layout();save('error_histogram')
fig,axes=plt.subplots(1,3,figsize=(8,2.6));src=cols(d)
for i,ax in enumerate(axes):
 sel=(src[:,2]>=i/3)&(src[:,2]<(i+1)/3);im=ax.scatter(src[sel,0],src[sel,1],c=errs['deltaE00'][sel],s=3,cmap='magma',vmin=0,vmax=np.percentile(errs['deltaE00'],99));ax.set(xlabel='sRGB red',ylabel='sRGB green',title=f'Blue ∈ [{i/3:.2f}, {(i+1)/3:.2f})')
fig.colorbar(im,ax=axes,label='CIEDE2000, no residual',shrink=.8);save('reconstruction_heatmap')
fig,axes=plt.subplots(2,3,figsize=(8,4.5));
for row,name in enumerate(['yellow_blue','red_blue']):
 for mode in range(4):
  z=g[(g['pair']==name)&(g['mode']==mode)];l=lab(linear(cols(z)));h=np.degrees(np.unwrap(np.arctan2(l[:,2],l[:,1])));ch=np.hypot(l[:,1],l[:,2]);h[ch<.02]=np.nan
  for col,v in enumerate([h,ch,linear(cols(z))@np.array([.2126,.7152,.0722])]):axes[row,col].plot(z['t'],v,label=labels[mode],lw=1.4)
 for col,title in enumerate(['Hue (degrees; C < 0.02 hidden)','OKLab chroma','Relative luminance']):axes[row,col].set(xlabel='t',title=title if row==0 else None)
 axes[row,0].set_ylabel(name.replace('_',' + '))
axes[0,0].legend(fontsize=7);fig.tight_layout();save('trajectories')
fig,ax=plt.subplots(figsize=(7,3));p=S['performance'];keys=[x for x in p if x!='LUT parsing'];v=[p[x]['median'] for x in keys];ax.barh(keys,v,color='#365e7d');ax.set_xscale('log');ax.set_xlabel('ns per operation (median of seven repetitions; log scale)');ax.invert_yaxis();save('performance')
fig,axes=plt.subplots(1,2,figsize=(7,2.8));keys=['n17_','n33_','n65_','tri33_'];axes[0].bar(['17³ tet','33³ tet','65³ tet','33³ tri'],[S['lut'][k]['deltaE00']['p95'] for k in keys],color='#548e6d');axes[0].set_ylabel('95th percentile ΔE00 vs reference mixes');axes[1].plot([17,33,65],[32*x**3/1024**2 for x in [17,33,65]],'o-');axes[1].set(xlabel='LUT side resolution',ylabel='Memory (MiB)');fig.tight_layout();save('lut_resolution')
fig,axes=plt.subplots(1,2,figsize=(7,3));a=S['basis_ablation'];axes[0].bar([x['label'] for x in a],[x['mean'] for x in a],color='#9d7550');axes[0].tick_params(axis='x',rotation=30);axes[0].set_ylabel('Mean ΔE00 without residual');sp=S['spectral_resolution'];axes[1].plot([x['step_nm'] for x in sp],[x['p95'] for x in sp],'o-');axes[1].set(xlabel='Wavelength step (nm)',ylabel='95th percentile ΔE00 vs 5 nm');fig.tight_layout();save('ablations')
m=Model();fig,axes=plt.subplots(1,2,figsize=(8,2.8));names2=['White','Cyan','Magenta','Yellow','Red','Green','Blue','Black'];colors=['#aaaaaa','teal','magenta','goldenrod','red','green','blue','black']
for i in range(8):axes[0].plot(m.nm,m.r[i],label=names2[i],color=colors[i]);axes[1].plot(m.nm,m.k[i],color=colors[i]);
axes[0].legend(ncol=4,fontsize=7);axes[0].set(xlabel='Wavelength (nm)',ylabel='Synthetic reflectance');axes[1].set(xlabel='Wavelength (nm)',ylabel='Relative absorption K',yscale='log');fig.tight_layout();save('spectra')
z=g[(g['pair']=='yellow_blue')&(g['mode']==3)];fig,ax=plt.subplots(figsize=(6,2.5));ax.stackplot(z['t'],*[z['w'+str(i)] for i in range(8)],labels=names2,colors=colors);ax.legend(ncol=4,loc='upper center',bbox_to_anchor=(.5,1.3),fontsize=8);ax.set(xlabel='t (yellow → blue)',ylabel='Concentration',xlim=(0,1),ylim=(0,1));save('concentrations')
fig,ax=plt.subplots(figsize=(9,2.2));ax.axis('off');boxes=[(.02,.55,'Encode sRGB\nConcentrations + residual'),(.37,.55,'Blend latent vectors\nNonnegative mixture weights'),(.74,.55,'Spectral K–M + residual\nGamut map → sRGB')]
for x,y,text in boxes:ax.text(x,y,text,transform=ax.transAxes,va='center',bbox={'boxstyle':'round,pad=.6','fc':'#e9eff3','ec':'#365e7d'},fontsize=9)
for x1,x2 in [(.30,.35),(.68,.72)]:ax.annotate('',xy=(x2,.55),xytext=(x1,.55),xycoords='axes fraction',arrowprops={'arrowstyle':'->'})
ax.text(.02,.12,'Encoder: LUT(sRGB) → concentrations; residual = linear(sRGB) − spectral(concentrations). Reference replaces LUT with direct inversion.',transform=ax.transAxes,fontsize=8);save('pipeline')
# All plotted data originate in recorded CSV/JSON or the exact analytic model.
np.savetxt(OUT/'ablations/spectra.csv',np.c_[m.nm,m.r.T,m.k.T],delimiter=',',header='nm,'+','.join('R_'+x for x in names2)+','+','.join('K_'+x for x in names2),comments='')
print('Generated',len(list(FIG.glob('*.png'))),'figures')
# Largest LUT discrepancies: include all five worst examples, not a curated subset.
import colour
p=np.genfromtxt(OUT/'mixing/random_pairs.csv',delimiter=',',names=True)
xyz=lambda x:linear(x)@np.linalg.inv(M).T
err=colour.delta_E(colour.XYZ_to_Lab(xyz(cols(p,'ref_'))),colour.XYZ_to_Lab(xyz(cols(p,'n33_'))))
ix=np.argsort(err)[-5:][::-1];fig,axes=plt.subplots(5,4,figsize=(7,3.2),gridspec_kw={'hspace':.5,'wspace':.06})
for row,i in enumerate(ix):
 for col,prefix in enumerate(['a','b','ref_','n33_']):
  ax=axes[row,col];ax.imshow(cols(p,prefix)[i][None,None,:],aspect='auto');ax.set_xticks([]);ax.set_yticks([])
  if row==0:ax.set_title(['Source A','Source B','Reference','Fast 33³'][col],fontsize=9)
  if col==0:ax.text(-.05,.5,f"ΔE {err[i]:.1f}\nt={p['t'][i]:.3f}",ha='right',va='center',transform=ax.transAxes,fontsize=8)
save('worst_cases')
np.savetxt(OUT/'mixing/worst_lut.csv',np.c_[p['id'][ix],err[ix],p['t'][ix],cols(p,'a')[ix],cols(p,'b')[ix],cols(p,'ref_')[ix],cols(p,'n33_')[ix]],delimiter=',',header='id,deltaE00,t,ar,ag,ab,br,bg,bb,ref_r,ref_g,ref_b,fast_r,fast_g,fast_b',comments='')
