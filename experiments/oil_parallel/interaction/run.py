"""One frozen bounded empirical spectral interaction experiment."""
import os
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
import argparse
import json
import sys
import time
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares
from scipy.special import expit
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
import measured_oils as v1
import measured_oils_chromatic as v3
PAIRS = [(i,j) for i in range(4) for j in range(i+1,4)]
t = np.linspace(0,1,31)
B = np.stack(((1-t)**3, 3*t*(1-t)**2, 3*t*t*(1-t), t**3), axis=1)

def features(c):
    c = np.asarray(c, dtype=float)
    if c.ndim != 2 or c.shape[1] != 4 or not np.isfinite(c).all() or (c<0).any() or (c.sum(1)<=0).any():
        raise ValueError('Expected finite nonnegative nonzero four-paint recipes')
    c = c / c.sum(1,keepdims=True)
    w = np.stack([4*c[:,i]*c[:,j] for i,j in PAIRS],axis=1)
    return c, (w[:,None,:,None]*B[None,:,None,:]).reshape(len(c),31,24)

def forward(base, x, theta):
    shift = x @ theta
    result = expit(np.log(base)-np.log1p(-base)+shift)
    return np.where(shift == 0, base, result)

def objective(base,x,target,active):
    xa=x[:,:,active]; count=target.size; n=int(active.sum())
    def residual(z):
        return np.r_[(forward(base,xa,z)-target).ravel()/np.sqrt(count), np.sqrt(1e-4/n)*z]
    def jac(z):
        r=forward(base,xa,z)
        return np.vstack((((r*(1-r))[:,:,None]*xa/np.sqrt(count)).reshape(count,n),np.sqrt(1e-4/n)*np.eye(n)))
    return residual,jac

def fit(c,target,settings):
    base_model=v1.fit_model(c.copy(),target.copy(),settings)
    c,x=features(c); base=v3.predicted(c,base_model)
    active=np.max(abs(x),axis=(0,1))>0
    residual,jac=objective(base,x,target,active)
    start=time.perf_counter()
    sol=least_squares(residual,np.zeros(active.sum()),jac=jac,bounds=(-.8,.8),max_nfev=2000,ftol=1e-10,xtol=1e-10,gtol=1e-10)
    theta=np.zeros(24);theta[active]=sol.x
    meta={'success':bool(sol.success),'message':sol.message,'nfev':sol.nfev,'objective':float(sol.fun@sol.fun),'bound_variables':int(np.count_nonzero(sol.active_mask)),'elapsed_seconds':time.perf_counter()-start,'active_parameters':int(active.sum())}
    if not sol.success: raise RuntimeError(str(meta))
    return {'base':base_model,'theta':theta.tolist(),'active':active.tolist(),'optimizer':meta}

def predict(c,model):
    c,x=features(c)
    return forward(v3.predicted(c,model['base']),x,np.asarray(model['theta']))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['fit','evaluate']);parser.add_argument('--out',type=Path,default=ROOT/'target/measured-oils/parallel/interaction');args=parser.parse_args()
    out=v1.research_directory(args.out); artifact_path=out/'frozen-models.json'
    rows,c,r,original=v1.load_source(ROOT/'target/measured-oils/source/spectralDatasets.zip')
    primary,pairs,multi,folds=v3.design(c,original)
    masks={'primary29':primary,**{name:train for name,(train,test) in folds.items()}}
    manifest={'plan_sha256':v1.sha(Path(__file__).with_name('PLAN.md').read_bytes()),'implementation_sha256':v1.sha(Path(__file__).read_bytes()),'source_sha256':v1.HASHES['archive'],'settings':json.loads(v1.CONFIG.read_text()),'fit_rows':{name:rows[m].tolist() for name,m in masks.items()},'test_rows':{'primary29':rows[multi].tolist(),**{name:rows[test].tolist() for name,(_,test) in folds.items()}}}
    if args.phase=='fit':
        if artifact_path.exists():raise ValueError('Refusing frozen-model overwrite; use fresh --out')
        v1.write_json(out/'partition.json',manifest)
        models={}
        for name,mask in masks.items():
            models[name]=fit(c[mask],r[mask],manifest['settings']);print(name,models[name]['optimizer'],flush=True)
        v1.write_json(artifact_path,{'manifest':manifest,'models':models});return
    artifact=json.loads(artifact_path.read_text())
    if artifact['manifest']!=manifest:raise ValueError('Frozen manifest differs')
    models=artifact['models'];base=json.loads((ROOT/'target/measured-oils/v1/fitted-model.json').read_text())
    frozen3=json.loads((ROOT/'target/measured-oils/v3-chromatic/frozen-models.json').read_text())['models']
    predictions={'v1':v3.predicted(c,base),'v3':v3.predicted(c,frozen3['primary29']),'interaction':predict(c,models['primary29'])}
    cross={name:p.copy() for name,p in predictions.items()}
    for name,(_,test) in folds.items():
        cross['v3'][test]=v3.predicted(c[test],frozen3[name]);cross['interaction'][test]=predict(c[test],models[name])
    _,_,lab=v1.colorimetry();metrics={name:v1.errors(r,p,lab) for name,p in predictions.items()};cm={name:v1.errors(r,p,lab) for name,p in cross.items()}
    summary={'status':'exploratory; all assessment rows previously exposed','manifest':manifest,'model_sha256':v1.sha(artifact_path.read_bytes()),'primary16':{name:v1.summarize(m,multi) for name,m in metrics.items()},'calibration29':{name:v1.summarize(m,primary) for name,m in metrics.items()},'pairs_cv8':{name:v1.summarize(m,pairs) for name,m in cm.items()},'families':{},'folds':{},'optimizer':{name:model['optimizer'] for name,model in models.items()},'base_optimizer':{name:model['base']['runs'] for name,model in models.items()}}
    for family in sorted(set(v1.family(x) for x in c[multi])):
        mask=np.array([v1.family(x)==family for x in c]);summary['families'][family]={name:v1.summarize(m,mask) for name,m in metrics.items()}
    for name,(_,test) in folds.items():summary['folds'][name]={key:v1.summarize(m,test) for key,m in cm.items()}
    pure=(c>0).sum(1)==1;summary['pure_max_abs']=max(float(np.max(abs(predict(c[pure],m)-r[pure]))) for m in models.values())
    old=json.loads((ROOT/'results/measured-oils-v1/summary.json').read_text())['models']['fitted']['holdout']['delta_e_2000']['mean']
    assert abs(v1.summarize(metrics['v1'],~original)['delta_e_2000']['mean']-old)<1e-12
    old3=json.loads((ROOT/'results/measured-oils-v3/summary.json').read_text())['primary_multicolor16']['v3']['delta_e_2000']['mean'];assert abs(summary['primary16']['v3']['delta_e_2000']['mean']-old3)<1e-12
    summary['base_v3_max_abs']=max(float(np.max(abs(v3.predicted(c,models[n]['base'])-v3.predicted(c,frozen3[n])))) for n in models)
    rng=np.random.default_rng(4821);recipes=np.vstack((rng.dirichlet(np.ones(4),10000),np.eye(4),[[1-1e-12,1e-12,0,0],[.25]*4]))
    pp=predict(recipes,models['primary29']);summary['validity']={'recipes':len(recipes),'min':float(pp.min()),'max':float(pp.max()),'finite':bool(np.isfinite(pp).all())}
    delta=pp-v3.predicted(recipes,models['primary29']['base'])
    summary['correction_reflectance']={'min':float(delta.min()),'max':float(delta.max()),'mean_abs':float(abs(delta).mean()),'positive_fraction':float((delta>0).mean()),'negative_fraction':float((delta<0).mean())}
    begin=time.perf_counter()
    for _ in range(10):predict(recipes,models['primary29'])
    summary['runtime_10006_recipes_seconds']=(time.perf_counter()-begin)/10
    records=[]
    for i in range(len(rows)):
        rec={'source_row':int(rows[i]),'family':v1.family(c[i]),'role':'fit' if original[i] else 'pair_cv' if pairs[i] else 'multicolor'}
        rec.update({f'{name}_{key}':float(value[i]) for name,m in cm.items() for key,value in m.items()});records.append(rec)
    v3.write_csv(out/'errors.csv',records);v1.write_json(out/'summary.json',summary)
    tracked=Path(__file__).parent
    v3.write_csv(tracked/'errors.csv',records);v1.write_json(tracked/'summary.json',summary)
    print(json.dumps({'primary16':summary['primary16'],'pairs_cv8':summary['pairs_cv8'],'pure_max_abs':summary['pure_max_abs'],'base_v3_max_abs':summary['base_v3_max_abs']},indent=2))
if __name__=='__main__':main()
