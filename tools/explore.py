from model import *
import csv,json
(ROOT/CFG['paths']['results']/'exploration').mkdir(parents=True,exist_ok=True)
m=Model();rows=[]
for name,a,b in PAIRS:
 a=np.array(a)/255;b=np.array(b)/255
 out=[m.mix_spectral(a,b,.5),m.mix(a,b,.5,False),m.mix(a,b,.5)]
 rows.append([name]+[','.join(map(str,np.rint(srgb(x)*255).astype(int))) for x in out])
with open(ROOT/CFG['paths']['results']/'exploration/midpoints.csv','w') as f:
 w=csv.writer(f);w.writerow(['pair','A_spectral','B_palette','C_hybrid']);w.writerows(rows)
rng=np.random.default_rng(CFG['experiments']['seed']);samples=rng.random((128,3))
errs={}
for label,active in [('CMYW',[0,1,2,3]),('CMYWK',[0,1,2,3,7]),('eight',None)]:
 mod=Model(active=active);e=[]
 for c in samples:e.append(100*np.linalg.norm(lab(gamut(mod.forward(mod.invert(c))))-lab(linear(c))))
 errs[label]={'mean_deltaEOK100':float(np.mean(e)),'p95':float(np.percentile(e,95)),'max':float(np.max(e))}
(ROOT/CFG['paths']['results']/'exploration/reconstruction.json').write_text(json.dumps(errs,indent=2))
print(rows);print(errs)
