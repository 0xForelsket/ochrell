"""One predeclared finite-layer experiment; see PLAN.md."""
import os
for key in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:
    os.environ[key]='1'
import sys, json, time, argparse, csv
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools'))
import numpy as np
from scipy.optimize import least_squares
from scipy.sparse import lil_matrix
from scipy.linalg import expm
import measured_oils as v1
import measured_oils_chromatic as v3

def layer(q,tau):
    b=np.sqrt(q*(q+2))
    z=b*tau
    h=np.divide(b,np.tanh(z),out=np.asarray(np.ones_like(b)/tau).copy(),where=z>1e-12)
    # Rg=1; algebra avoids subtracting two quantities near 1.
    return (h-q)/(h+q)

def inverse(pure,tau):
    lo=np.zeros_like(pure); hi=np.maximum(1,(1-pure)**2/pure)
    for _ in range(60):
        need=layer(hi,tau)>pure
        if not need.any(): break
        hi=np.where(need,hi*2,hi)
    else: raise ValueError('Could not bracket finite-layer inverse')
    for _ in range(55):
        mid=(lo+hi)/2
        above=layer(mid,tau)>pure
        lo=np.where(above,mid,lo); hi=np.where(above,hi,mid)
    return (lo+hi)/2

def predict(c,pure,u):
    s=np.vstack([np.exp(u[:93].reshape(3,31)),np.ones(31)])
    x=np.exp(u[93]); q=inverse(pure,s*x)
    sm=c@s; qm=(c@(q*s))/sm
    return layer(qm,sm*x),q,s

def fit(c,r):
    pure=np.array([r[np.flatnonzero(c[:,j]==1)[0]] for j in range(4)])
    def residual(u):
        p=predict(c,pure,u)[0]
        return np.r_[(p-r).ravel()/np.sqrt(r.size),
            np.diff(u[:93].reshape(3,31),n=2).ravel()*np.sqrt(1e-4/87),
            u[:93]*np.sqrt(1e-8/93)]
    sparsity=lil_matrix((r.size+87+93,94),dtype=int)
    for i in range(len(c)):
        for b in range(31):
            sparsity[i*31+b,[b,31+b,62+b,93]]=1
    for j in range(3):
        for b in range(29): sparsity[r.size+j*29+b,j*31+b:j*31+b+3]=1
    for b in range(93): sparsity[r.size+87+b,b]=1
    sols=[]; runs=[]
    for log_s,x in [(0,.3),(np.log(.1),3),(np.log(10),30)]:
        begin=time.perf_counter()
        sol=least_squares(residual,np.r_[np.full(93,log_s),np.log(x)],
            bounds=(np.r_[np.full(93,-9.210340371976184),np.log(.1)],
                    np.r_[np.full(93,9.210340371976184),np.log(100)]),
            jac_sparsity=sparsity.tocsr(),max_nfev=200,ftol=1e-8,xtol=1e-8,gtol=1e-8)
        sols.append(sol)
        runs.append(dict(initial_log_s=float(log_s),initial_x=x,success=bool(sol.success),
            status=int(sol.status),message=sol.message,nfev=sol.nfev,njev=sol.njev,
            objective=float(sol.fun@sol.fun),optimality=float(sol.optimality),
            active_bounds=int(np.count_nonzero(sol.active_mask)),elapsed_seconds=time.perf_counter()-begin))
        print(runs[-1],flush=True)
    eligible=[i for i,s in enumerate(sols) if s.success] or list(range(3))
    selected=min(eligible,key=lambda i:runs[i]['objective']); sol=sols[selected]
    p,q,s=predict(c,pure,sol.x)
    # Dense numerical training Jacobian spectrum is useful only locally.
    singular=np.linalg.svd(sol.jac.toarray(),compute_uv=False)
    return dict(u=sol.x.tolist(),pure=pure.tolist(),q=q.tolist(),S=s.tolist(),
        x=float(np.exp(sol.x[93])),runs=runs,selected_start=selected,
        local_regularized_jacobian_singular_min=float(singular[-1]),
        local_regularized_jacobian_condition=float(singular[0]/singular[-1]))

def checks():
    worst=0.
    for q in [0,1e-6,.1,2,10]:
        for tau in [.0001,.1,1]:
            # Downward D, upward U: D'=-(K+S)D+S U, U'=-S D+(K+S)U.
            m=expm(np.array([[-1-q,1],[-1,1+q]])*tau)
            reference=(m[0,0]-m[1,0])/(m[1,1]-m[0,1])
            worst=max(worst,abs(reference-float(layer(np.array(q),tau))))
    assert worst<1e-9,worst
    pure=np.array([[.0001,.01,.2,.8,.999999]])
    tau=np.array([[.00001,.3,1,10,100]])
    inv=inverse(pure,tau)
    inv_error=float(np.max(abs(layer(inv,tau)-pure)))
    assert inv_error<1e-11,inv_error
    q=np.array([.01,.1,1,10]); opaque=1/(1+q+np.sqrt(q*(q+2)))
    thick=float(np.max(abs(layer(q,1e5)-opaque)))
    thin=float(np.max(abs(layer(q,1e-10)-1)))
    assert thick<1e-12 and thin<3e-9
    rng=np.random.default_rng(100); p=rng.uniform(.02,.95,(4,31))
    u=np.r_[rng.normal(0,.3,93),np.log(2)]
    endpoints=float(np.max(abs(predict(np.eye(4),p,u)[0]-p)))
    assert endpoints<1e-12
    return dict(matrix_exponential_max_abs=worst,inversion_max_abs=inv_error,
        opaque_limit_max_abs=thick,thin_limit_max_abs=thin,synthetic_endpoints_max_abs=endpoints)

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('phase',choices=['check','fit','evaluate'])
    parser.add_argument('--out',type=Path,default=ROOT/'target/measured-oils/parallel/physical')
    args=parser.parse_args(); out=v1.research_directory(args.out)
    if args.phase=='check':
        result=checks(); v1.write_json(out/'checks.json',result); print(result); return
    rows,c,r,original=v1.load_source(ROOT/'target/measured-oils/source/spectralDatasets.zip')
    primary,pairs,multi,folds=v3.design(c,original)
    baseline=json.loads((ROOT/'target/measured-oils/v1/fitted-model.json').read_text())
    frozen_v3=json.loads((ROOT/'target/measured-oils/v3-chromatic/frozen-models.json').read_text())['models']
    manifest=dict(source_sha=v1.HASHES['archive'],script_sha=v1.sha(Path(__file__).read_bytes()),
        plan_sha=v1.sha(Path(__file__).with_name('PLAN.md').read_bytes()),
        baseline_sha=v1.sha((ROOT/'target/measured-oils/v1/fitted-model.json').read_bytes()),
        fit_rows=rows[primary].tolist(),assessment_rows=rows[multi].tolist(),
        folds={f:dict(fit=rows[a].tolist(),test=rows[b].tolist()) for f,(a,b) in folds.items()})
    path=out/'frozen-models.json'
    if args.phase=='fit':
        if path.exists(): raise ValueError('Use fresh --out; frozen fits cannot be overwritten')
        checks(); models={}
        for name,train in [('primary29',primary)]+[(f,a) for f,(a,b) in folds.items()]:
            print('Fitting',name,flush=True); models[name]=fit(c[train].copy(),r[train].copy())
        v1.write_json(path,dict(manifest=manifest,models=models)); return
    artifact=json.loads(path.read_text()); assert artifact['manifest']==manifest
    _,_,lab=v1.colorimetry()
    p1=v3.predicted(c,baseline); p3=v3.predicted(c,frozen_v3['primary29'])
    pc=predict(c,np.array(artifact['models']['primary29']['pure']),np.array(artifact['models']['primary29']['u']))[0]
    cross3=p3.copy(); crossc=pc.copy()
    for f,(train,test) in folds.items():
        m=artifact['models'][f]
        crossc[test]=predict(c[test],np.array(m['pure']),np.array(m['u']))[0]
        cross3[test]=v3.predicted(c[test],frozen_v3[f])
    metrics={name:v1.errors(r,p,lab) for name,p in [('v1',p1),('v3',p3),('finite',pc),('v3_cv',cross3),('finite_cv',crossc)]}
    pure=(c>0).sum(axis=1)==1
    summary=dict(status='Exploratory; assessment data were previously exposed',manifest=manifest,
        checks=checks(),model_hash=v1.sha(path.read_bytes()),parameters=94,
        colorimetry='31 bands 400-700nm truncated D65/2deg, unclipped Lab')
    for role,mask,names in [('multicolor16',multi,['v1','v3','finite']),('calibration29',primary,['v1','v3','finite']),
            ('pure4',pure,['v1','v3','finite']),('pair_cv8',pairs,['v1','v3_cv','finite_cv'])]:
        summary[role]={n:v1.summarize(metrics[n],mask) for n in names}
    summary['families']={}
    for f in sorted(set(v1.family(x) for x in c[~original])):
        mask=np.array([v1.family(x)==f for x in c]); pair=bool((mask&pairs).any())
        names=['v1','v3_cv','finite_cv'] if pair else ['v1','v3','finite']
        summary['families'][f]={n:v1.summarize(metrics[n],mask) for n in names}
    summary['optimization']={n:{k:m[k] for k in ['x','runs','selected_start','local_regularized_jacobian_singular_min','local_regularized_jacobian_condition']} for n,m in artifact['models'].items()}
    recorded=json.loads((ROOT/'results/measured-oils-v3/summary.json').read_text())
    agreement=abs(summary['multicolor16']['v1']['delta_e_2000']['mean']-recorded['primary_multicolor16']['v1']['delta_e_2000']['mean'])
    agreement3=abs(summary['pair_cv8']['v3_cv']['delta_e_2000']['mean']-recorded['pair_family_cv8']['v3']['delta_e_2000']['mean'])
    assert max(agreement,agreement3)<1e-12
    summary['baseline_agreement_max_abs']=max(agreement,agreement3)
    v1.write_json(out/'summary.json',summary)
    published=Path(__file__).parent
    v1.write_json(published/'summary.json',summary)
    table=[]
    for i,row in enumerate(rows):
        item=dict(source_row=int(row),family=v1.family(c[i]),role='fit' if original[i] else 'pair_cv' if pairs[i] else 'multicolor')
        item.update({f'{n}_{k}':float(val[i]) for n,m in metrics.items() for k,val in m.items()}); table.append(item)
    v3.write_csv(published/'errors.csv',table)
    print(json.dumps(summary['multicolor16'],indent=2))

if __name__=='__main__': main()
