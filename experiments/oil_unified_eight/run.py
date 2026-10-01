"""One shared eight-paint K-M base and 28 empirical pair interactions."""
import os
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
import argparse
import csv
import importlib.util
import io
import itertools
import json
import platform
import sys
import time
import zipfile
from pathlib import Path
import numpy as np
import scipy
from scipy.optimize import least_squares
from scipy.special import expit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import measured_oils as old
import measured_oils_chromatic as old_chromatic

spec = importlib.util.spec_from_file_location('original_interaction', ROOT/'experiments/oil_parallel/interaction/run.py')
emp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(emp)
SOURCE = ROOT/'target/measured-oils/source/spectralDatasets.zip'
DEFAULT = ROOT/'target/measured-oils/unified-eight'
NAMES = ['Scheveningen Yellow Lemon', 'Cadmium Yellow', 'Scarlet Lake extra',
         'Alizarine Lake', 'Cobalt Blue', 'Ultramarine Blue', 'Viridian Green', 'Mixed White']


def inputs():
    raw = SOURCE.read_bytes()
    assert old.sha(raw) == old.HASHES['archive']
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        members = {name:z.read(name) for name in old.HASHES if name != 'archive'}
    for name, data in members.items(): assert old.sha(data) == old.HASHES[name]
    c = np.loadtxt(io.BytesIO(members['oilmixtureportions.txt']))
    r = np.loadtxt(io.BytesIO(members['oilspectra.txt']))
    assert c.shape == (286,8) and r.shape == (286,31)
    assert np.isfinite(c).all() and (c >= 0).all() and (c.sum(1) > 0).all()
    assert np.isfinite(r).all() and (r > 0).all() and (r < 1).all()
    c /= c.sum(1, keepdims=True)
    counts = (c > 0).sum(1); train = counts <= 2
    assert train.sum() == 103 and (~train).sum() == 183 and (counts == 1).sum() == 8
    pairs = list(itertools.combinations(range(8), 2))
    assert all(((counts == 2)&(c[:,i]>0)&(c[:,j]>0)).any() for i,j in pairs)
    files = [Path(__file__), HERE/'PLAN.md', old.CONFIG, Path(old.__file__),
             Path(old_chromatic.__file__), Path(emp.__file__), ROOT/'data/cie_380_780_1nm.csv',
             ROOT/'experiments/oil_ternary_transfer/errors.csv',
             ROOT/'experiments/oil_ternary_sources/next-cohort.json']
    manifest = {'source_sha256':old.HASHES, 'hashes':{p.relative_to(ROOT).as_posix():old.sha(p.read_bytes()) for p in files},
        'fit_rows':(np.flatnonzero(train)+1).tolist(), 'assessment_rows':(np.flatnonzero(~train)+1).tolist(),
        'paint_names':NAMES, 'grid_nm':[400,700,10], 'amount_basis':'normalized recorded tube-paint mass portions',
        'settings':json.loads(old.CONFIG.read_text(encoding='utf-8')),
        'pair_counts':{f'{i+1}+{j+1}':int(((counts==2)&(c[:,i]>0)&(c[:,j]>0)).sum()) for i,j in pairs},
        'environment':{'python':platform.python_version(), 'numpy':np.__version__, 'scipy':scipy.__version__}}
    return c, r, train, manifest


def pure_q(c, target):
    pure=[]
    for i in range(c.shape[1]):
        indices=np.flatnonzero((c[:,i]==1)&((c>0).sum(1)==1))
        assert len(indices)==1
        pure.append(target[indices[0]])
    pure=np.array(pure)
    return (1-pure)**2/(2*pure)


def forward(c, q, u):
    n,b=q.shape
    s=np.vstack([np.exp(np.asarray(u).reshape(n-1,b)),np.ones(b)])
    k=q*s; denominator=c@s; ratio=(c@k)/denominator
    r=1/(1+ratio+np.sqrt(ratio*(ratio+2)))
    return r,ratio,denominator,s,k


def base_objective(c, target, q, settings):
    n,b=q.shape; count=target.size; params=(n-1)*b
    curve=np.kron(np.eye(n-1),np.diff(np.eye(b),n=2,axis=0))*np.sqrt(settings['curvature_weight']/((n-1)*(b-2)))
    prior=np.eye(params)*np.sqrt(settings['amplitude_weight']/params)
    def residual(u):
        return np.r_[(forward(c,q,u)[0]-target).ravel()/np.sqrt(count),curve@u,prior@u]
    def jacobian(u):
        r,ratio,denom,s,_=forward(c,q,u); derivative=-r/np.sqrt(ratio*(ratio+2))
        jac=np.zeros((count,params))
        for i in range(n-1):
            v=derivative*c[:,i,None]*s[i]*(q[i]-ratio)/denom
            jac[np.arange(count),np.tile(np.arange(b)+i*b,len(c))]=v.ravel()/np.sqrt(count)
        return np.vstack([jac,curve,prior])
    return residual,jacobian


def fit_base(c, target, settings):
    q=pure_q(c,target); n,b=q.shape
    residual,jac=base_objective(c,target,q,settings)
    runs=[]; solutions=[]
    for start in settings['initial_log_scattering']:
        now=time.perf_counter()
        sol=least_squares(residual,np.full((n-1)*b,start),jac=jac,method='trf',bounds=settings['log_scattering_bounds'],
            max_nfev=settings['max_nfev'],ftol=settings['ftol'],xtol=settings['xtol'],gtol=settings['gtol'])
        runs.append({'initial_log_s':start,'success':bool(sol.success),'nfev':sol.nfev,
            'objective':float(sol.fun@sol.fun),'optimality':float(sol.optimality),
            'bound_variables':int(np.count_nonzero(sol.active_mask)),'elapsed_seconds':time.perf_counter()-now})
        solutions.append(sol)
    good=[i for i,r in enumerate(runs) if r['success']]
    if not good: raise RuntimeError(str(runs))
    selected=min(good,key=lambda i:(runs[i]['objective'],i)); u=solutions[selected].x
    _,_,_,s,k=forward(c,q,u)
    return {'q':q.tolist(),'log_relative_s':u.reshape(n-1,b).tolist(),'K':k.tolist(),'S':s.tolist(),
        'runs':runs,'selected_start':selected}


def features(c):
    c=np.asarray(c,dtype=float)
    assert c.ndim==2 and np.isfinite(c).all() and (c>=0).all() and (c.sum(1)>0).all()
    c=c/c.sum(1,keepdims=True)
    pairs=list(itertools.combinations(range(c.shape[1]),2))
    w=np.stack([4*c[:,i]*c[:,j] for i,j in pairs],axis=1)
    return c,(w[:,None,:,None]*emp.B[None,:,None,:]).reshape(len(c),31,len(pairs)*4)


def predict(c, model, corrected=True):
    base=model['base']; c,x=features(c)
    r=forward(c,np.asarray(base['q']),np.asarray(base['log_relative_s']))[0]
    return emp.forward(r,x,np.asarray(model['theta'])) if corrected else r


def fit(c, target, settings):
    base=fit_base(c.copy(),target.copy(),settings); frozen=json.dumps(base,sort_keys=True)
    c,x=features(c); r=forward(c,np.asarray(base['q']),np.asarray(base['log_relative_s']))[0]
    active=np.max(abs(x),axis=(0,1))>0
    residual,jac=emp.objective(r,x,target,active); now=time.perf_counter()
    sol=least_squares(residual,np.zeros(active.sum()),jac=jac,bounds=(-.8,.8),max_nfev=2000,ftol=1e-10,xtol=1e-10,gtol=1e-10)
    meta={'success':bool(sol.success),'nfev':sol.nfev,'objective':float(sol.fun@sol.fun),
        'bound_variables':int(np.count_nonzero(sol.active_mask)),'elapsed_seconds':time.perf_counter()-now}
    if not sol.success: raise RuntimeError(str(meta))
    assert json.dumps(base,sort_keys=True)==frozen
    theta=np.zeros(x.shape[2]); theta[active]=sol.x
    return {'base':base,'theta':theta.tolist(),'active':active.tolist(),'optimizer':meta}


def preflight(settings):
    rows,c,r,_=old.load_source(SOURCE); train=(c>0).sum(1)<=2
    original=emp.fit(c[train],r[train],settings); generalized=fit(c[train],r[train],settings)
    errors={}
    for field in ['K','S','q','log_relative_s']:
        errors[field]=float(np.max(abs(np.asarray(original['base'][field])-np.asarray(generalized['base'][field]))))
        np.testing.assert_allclose(original['base'][field],generalized['base'][field],rtol=1e-9,atol=1e-11)
    np.testing.assert_allclose(original['theta'],generalized['theta'],rtol=1e-9,atol=1e-11)
    errors['theta']=float(np.max(abs(np.array(original['theta'])-generalized['theta'])))
    rng=np.random.default_rng(81016)
    c=np.vstack([np.eye(8),rng.dirichlet(np.ones(8),19)])
    q=rng.uniform(.05,10,(8,31)); u=rng.uniform(-.2,.2,217)
    target=forward(c,q,u)[0]; fun,jac=base_objective(c,target,q,settings)
    direction=rng.normal(size=217); direction/=np.linalg.norm(direction)
    numerical=(fun(u+1e-6*direction)-fun(u-1e-6*direction))/(2e-6)
    errors['directional_jacobian_max_abs']=float(np.max(abs(numerical-jac(u)@direction)))
    assert errors['directional_jacobian_max_abs']<1e-8
    return errors


def scalar(recipe, model, corrected):
    import math
    c=[float(x)/sum(recipe) for x in recipe]; result=[]; base=model['base']
    pairs=list(itertools.combinations(range(len(c)),2))
    for band in range(31):
        k=sum(c[i]*base['K'][i][band] for i in range(len(c)))
        s=sum(c[i]*base['S'][i][band] for i in range(len(c)))
        q=k/s; r=1/(1+q+math.sqrt(q)*math.sqrt(q+2))
        if corrected:
            t=band/30; basis=[(1-t)**3,3*t*(1-t)**2,3*t*t*(1-t),t**3]
            shift=sum(4*c[i]*c[j]*basis[h]*model['theta'][p*4+h] for p,(i,j) in enumerate(pairs) for h in range(4))
            if shift: r=1/(1+math.exp(-(math.log(r)-math.log1p(-r)+shift)))
        result.append(r)
    return result


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('phase',choices=['prepare','fit','verify','evaluate'])
    parser.add_argument('--out',type=Path,default=DEFAULT); args=parser.parse_args()
    out=old.research_directory(args.out); c,r,train,manifest=inputs()
    frozen=out/'frozen-model.json'; partition=out/'partition.json'
    if args.phase=='prepare':
        assert not partition.exists() and not frozen.exists(),'Use a fresh output directory'
        checks=preflight(manifest['settings']); old.write_json(out/'preflight.json',checks)
        old.write_json(partition,manifest); print(json.dumps(checks)); return
    assert json.loads(partition.read_text(encoding='utf-8'))==manifest
    if args.phase=='fit':
        assert not frozen.exists(),'Refusing frozen-model overwrite'
        model=fit(c[train].copy(),r[train].copy(),manifest['settings'])
        old.write_json(frozen,{'manifest':manifest,'model':model})
        print(json.dumps({'base_runs':model['base']['runs'],'correction':model['optimizer'],'sha256':old.sha(frozen.read_bytes())},indent=2)); return
    raw=frozen.read_bytes(); artifact=json.loads(raw); assert artifact['manifest']==manifest; model=artifact['model']
    if args.phase=='verify':
        altered=r.copy(); altered[~train]=np.random.default_rng(81017).uniform(.01,.99,altered[~train].shape)
        again=fit(c[train].copy(),altered[train].copy(),manifest['settings'])
        for field in ['K','S','q','log_relative_s']: np.testing.assert_array_equal(again['base'][field],model['base'][field])
        np.testing.assert_array_equal(again['theta'],model['theta'])
        dense=np.vstack([c,np.random.default_rng(81018).dirichlet(np.ones(8),1024)])
        checks={'heldout_coefficient_change':0.,'scalar_max_abs':{},'range':{},'pure_max_abs':{}}
        pure=(c>0).sum(1)==1
        for corrected in [False,True]:
            name='empirical' if corrected else 'km'; prediction=predict(dense,model,corrected)
            reference=np.array([scalar(x,model,corrected) for x in dense])
            checks['scalar_max_abs'][name]=float(abs(prediction-reference).max())
            assert checks['scalar_max_abs'][name]<1e-12
            assert np.isfinite(prediction).all() and (prediction>0).all() and (prediction<1).all()
            checks['range'][name]=[float(prediction.min()),float(prediction.max())]
            checks['pure_max_abs'][name]=float(abs(prediction[:286][pure]-r[pure]).max())
            assert checks['pure_max_abs'][name]<1e-12
        result={'manifest':manifest,'bundle_sha256':old.sha(raw),'checks':checks,'dense_recipes':len(dense)}
        for dest in [out,HERE]: old.write_json(dest/'verification.json',result)
        print(json.dumps(checks,indent=2))
    if args.phase=='evaluate':
        verified=json.loads((out/'verification.json').read_text(encoding='utf-8'))
        assert verified['manifest']==manifest and verified['bundle_sha256']==old.sha(raw)
        _,white,lab=old.colorimetry(); counts=(c>0).sum(1)
        masks={'assessment183':~train,'calibration103':train,'no_white':(~train)&(c[:,7]==0),'with_white':(~train)&(c[:,7]>0)}
        masks.update({f'{i}_paints':counts==i for i in range(3,8)})
        metrics={name:old.errors(r,predict(c,model,corrected),lab) for name,corrected in [('km',False),('empirical',True)]}
        result={'manifest':manifest,'bundle_sha256':old.sha(raw),'status':'same-source exploratory assessment; no measured eight-ingredient sample',
            'scores':{role:{name:old.summarize(m,mask) for name,m in metrics.items()} for role,mask in masks.items()},
            'colorimetry':{'window':[400,700],'observer':'CIE 1931 2 degree','illuminant':'D65','white_xyz':white.tolist()},
            'base_runs':model['base']['runs'],'correction_optimizer':model['optimizer']}
        with (ROOT/'experiments/oil_ternary_transfer/errors.csv').open(encoding='utf-8',newline='') as stream: original=list(csv.DictReader(stream))
        idx=np.array([int(row['source_row'])-1 for row in original]); mask=np.isin(np.arange(286),idx); assert mask.sum()==35
        result['shared35']={name:old.summarize(m,mask) for name,m in metrics.items()}
        result['original35']={name:{key:float(np.mean([float(row[f'{name}_{key}']) for row in original])) for key in ['spectral_rmse','delta_e_2000']} for name in metrics}
        result['improved_counts183']={key:int((metrics['empirical'][key][~train]<metrics['km'][key][~train]).sum()) for key in metrics['km']}
        records=[{'source_row':i+1,'role':'calibration' if train[i] else 'assessment','paint_count':int(counts[i]),'white_fraction':float(c[i,7]),
            **{f'{name}_{key}':float(value[i]) for name,m in metrics.items() for key,value in m.items()}} for i in range(286)]
        for dest in [out,HERE]:
            old.write_json(dest/'summary.json',result); old_chromatic.write_csv(dest/'errors.csv',records)
        print(json.dumps({'assessment183':result['scores']['assessment183'],'shared35':result['shared35'],'improved_counts':result['improved_counts183']},indent=2))
    assert frozen.read_bytes()==raw


if __name__=='__main__': main()
