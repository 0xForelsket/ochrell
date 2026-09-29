"""Observational comparison after model selection; no external fitting targets.
Uses frozen numerical Spectral.js v3.0.0 output and 39 Mixbox JPEG samples.
"""
import sys,subprocess,io,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from model import ROOT,PAIRS
from revision.analyze import de,stats
import numpy as np
out=ROOT/'results/revision/external'
read=lambda f:np.genfromtxt(out/f,names=True,delimiter=',',dtype=None,encoding='utf8')
spectral=read('spectral.csv');mb=read('mixbox_samples.csv');pairs=dict((name,(np.array(a)/255,np.array(b)/255)) for name,a,b in PAIRS+[('official_default',[0,33,133],[252,210,0])])
x=np.array([[*pairs[d['pair']][0],*pairs[d['pair']][1],d['t']] for d in spectral]);buf=io.StringIO();np.savetxt(buf,x,delimiter=',',fmt='%.12e')
r=subprocess.run([str(ROOT/'target/release/examples/sample_pairs')],input=buf.getvalue(),text=True,capture_output=True,check=True)
v=np.genfromtxt(io.StringIO(r.stdout),names=True,delimiter=',');
with (out/'ours.csv').open('w') as f:
 f.write('pair,t,new_r,new_g,new_b,old_r,old_g,old_b\n')
 for d,row in zip(spectral,v):f.write(f'{d["pair"]},{d["t"]},'+','.join(str(row[n]) for n in v.dtype.names)+'\n')
col=lambda d,p='':np.column_stack([d[p+c] for c in 'rgb'])
new=col(v,'new_');old=col(v,'old_');sp=col(spectral)/255
idx=np.array([np.flatnonzero((spectral['pair']==d['pair'])&np.isclose(spectral['t'],d['t'],atol=1e-6))[0] for d in mb]);mbcol=col(mb,'mixbox_')/255
s={'scope':'13 fixed pairs; Mixbox 39 JPEG observations with screenshot uncertainty; Spectral.js 5213 8-bit API samples; neither is a paint-accuracy target','new_vs_mixbox':stats(de(new[idx],mbcol)),'old_vs_mixbox':stats(de(old[idx],mbcol)),'spectral_vs_mixbox':stats(de(sp[idx],mbcol)),'new_vs_spectral_all':stats(de(new,sp)),'old_vs_spectral_all':stats(de(old,sp))}
(out/'summary.json').write_text(json.dumps(s,indent=2)+'\n');print(json.dumps(s,indent=2))
