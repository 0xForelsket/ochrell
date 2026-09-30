"""One frozen spectral/Lab hybrid; run check, prepare, fit, evaluate in order."""
import argparse
import json
import sys
import time
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import measured_oils as v1
import measured_oils_chromatic as v3

CFG = json.loads((HERE / 'config.json').read_text())
SETTINGS = json.loads(v1.CONFIG.read_text())
OUT = ROOT / 'target/measured-oils/parallel/objective'

def lab_jac(r):
    weights, white, _ = v1.colorimetry()
    t = (r @ weights) / white
    delta = 6 / 29
    f = np.where(t > delta**3, np.cbrt(t), t/(3*delta**2)+4/29)
    fp = np.where(t > delta**3, 1/(3*np.cbrt(t)**2), 1/(3*delta**2))
    a = np.array([[0,116,0],[500,-500,0],[0,200,-200]])
    lab = f @ a.T + np.array([-16,0,0])
    derivative = np.einsum('ak,nk,bk->nab', a, fp, weights/white)
    return lab, derivative

def objective(c, measured, q):
    oldres, oldjac = v1.objective(c, measured, q, SETTINGS)
    n = len(c); count = measured.size
    target = lab_jac(measured)[0]
    scale = np.sqrt(CFG['color_fraction']/n)*CFG['color_scale']
    spectral = np.sqrt(CFG['spectral_fraction'])
    def residual(u):
        old = oldres(u)
        lab = lab_jac(v1.predict(c,q,u)[0])[0]
        return np.concatenate([spectral*old[:count],scale*(lab-target).ravel(),old[count:]])
    def jacobian(u):
        old = oldjac(u)
        _, dl = lab_jac(v1.predict(c,q,u)[0])
        dr = old[:count].reshape(n,31,93)*np.sqrt(count)
        color = np.einsum('nab,nbp->nap',dl,dr).reshape(n*3,93)*scale
        return np.vstack([spectral*old[:count],color,old[count:]])
    return residual,jacobian

def fit(c,r):
    q=v1.pure_ratios(c,r); fun,jac=objective(c,r,q)
    runs=[]; solutions=[]
    for initial in SETTINGS['initial_log_scattering']:
        t=time.perf_counter()
        sol=least_squares(fun,np.full(93,initial),jac=jac,bounds=SETTINGS['log_scattering_bounds'],
            max_nfev=SETTINGS['max_nfev'],ftol=SETTINGS['ftol'],xtol=SETTINGS['xtol'],gtol=SETTINGS['gtol'])
        runs.append(dict(initial_log_s=initial,success=bool(sol.success),status=int(sol.status),message=sol.message,
            nfev=sol.nfev,njev=sol.njev,objective=float(sol.fun@sol.fun),optimality=float(sol.optimality),
            bound_variables=int(np.count_nonzero(sol.active_mask)),elapsed_seconds=time.perf_counter()-t))
        solutions.append(sol)
    good=[i for i,x in enumerate(runs) if x['success']]
    if not good: raise RuntimeError(runs)
    selected=min(good,key=lambda i:(runs[i]['objective'],i)); u=solutions[selected].x
    _,_,_,s,k=v1.predict(c,q,u)
    return dict(q=q.tolist(),log_relative_s=u.reshape(3,31).tolist(),S=s.tolist(),K=k.tolist(),runs=runs,selected_start=selected)

def checks():
    rng=np.random.default_rng(20260930)
    pure=rng.uniform(.08,.85,(4,31)); c=np.vstack([np.eye(4),rng.dirichlet(np.ones(4),12)])
    q=(1-pure)**2/(2*pure); u=np.repeat(np.array([-.5,-1.,-1.5]),31); r=v1.predict(c,q,u)[0]
    fun,jac=objective(c,r,q); x=u+.1; analytic=jac(x); numerical=np.empty_like(analytic)
    for j in range(93):
        step=np.zeros(93);step[j]=1e-5
        numerical[:,j]=(fun(x+step)-fun(x-step))/2e-5
    error=float(np.max(np.abs(analytic-numerical)))
    assert error<1e-8,error
    _,_,lab=v1.colorimetry(); cases=np.vstack([r,np.full((1,31),.001)])
    parity=float(np.max(np.abs(lab(cases)-lab_jac(cases)[0])))
    assert parity<1e-10,parity
    # Recovery with the declared regularization retained; report its tiny bias.
    model=fit(c,r); recovery=float(np.max(np.abs(v3.predicted(c,model)-r)))
    assert recovery<.002,recovery
    scalar=v3.independent_check(c,model,v3.predicted(c,model))
    return dict(jacobian_max_abs=error,lab_parity_max_abs=parity,synthetic_recovery_max_abs=recovery,scalar_max_abs=scalar)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['check','prepare','fit','evaluate']);parser.add_argument('--out',type=Path,default=OUT)
    args=parser.parse_args();out=v1.research_directory(args.out)
    if args.phase=='check':
        v1.write_json(HERE/'checks.json',checks());print((HERE/'checks.json').read_text());return
    rows,c,r,original=v1.load_source(ROOT/'target/measured-oils/source/spectralDatasets.zip')
    primary,pairs,multi,folds=v3.design(c,original)
    baseline=json.loads((ROOT/'target/measured-oils/v1/fitted-model.json').read_text())
    oldmodels=json.loads((ROOT/'target/measured-oils/v3-chromatic/frozen-models.json').read_text())['models']
    manifest=dict(hashes={str(p.relative_to(ROOT)):v1.sha(p.read_bytes()) for p in [HERE/'PLAN.md',HERE/'config.json',Path(__file__),v1.CONFIG,Path(v1.__file__),Path(v3.__file__)]},source_sha256=v1.HASHES['archive'],baseline_sha256=v1.sha((ROOT/'target/measured-oils/v1/fitted-model.json').read_bytes()),
        primary_fit_rows=rows[primary].tolist(),primary_test_rows=rows[multi].tolist(),folds={f:dict(train=rows[a].tolist(),test=rows[b].tolist()) for f,(a,b) in folds.items()})
    path=out/'frozen-models.json'
    if args.phase=='prepare':
        assert not path.exists();v1.write_json(out/'partition.json',manifest);return
    assert json.loads((out/'partition.json').read_text())==manifest
    if args.phase=='fit':
        assert not path.exists();models={}
        for name,mask in [('primary29',primary)]+[(f,a) for f,(a,b) in folds.items()]:
            models[name]=fit(c[mask].copy(),r[mask].copy());models[name]['fit_rows']=rows[mask].tolist()
            print(name,json.dumps(models[name]['runs']),flush=True)
        v1.write_json(path,dict(manifest=manifest,models=models));return
    artifact=json.loads(path.read_text());assert artifact['manifest']==manifest
    summary,metrics=v3.compare(rows,c,r,original,baseline,artifact['models'])
    oldsummary,oldmetrics=v3.compare(rows,c,r,original,baseline,oldmodels)
    for role in ['primary_multicolor16','pair_family_cv8','cross_fitted24']:
        summary[role]['hybrid']=summary[role].pop('v3');summary[role]['v3']=oldsummary[role]['v3']
    recorded=json.loads((ROOT/'results/measured-oils-v3/summary.json').read_text())
    for role in ['primary_multicolor16','pair_family_cv8','cross_fitted24']:
        for name in ['v1','v3']:
            assert abs(summary[role][name]['delta_e_2000']['mean']-recorded[role][name]['delta_e_2000']['mean'])<1e-12
    summary['baseline_reproduction']='v1/v3 same-row mean DE00 matches archived summary within 1e-12'
    summary['manifest']=manifest;summary['frozen_model_sha256']=v1.sha(path.read_bytes())
    summary['optimizer']={n:dict(runs=m['runs'],selected_start=m['selected_start']) for n,m in artifact['models'].items()}
    summary['parameter_count']=93;summary['total_fit_seconds']=sum(run['elapsed_seconds'] for m in artifact['models'].values() for run in m['runs'])
    summary['note']='Within families/folds/changes, v3 key denotes hybrid candidate; primary aggregate tables explicitly distinguish true v3.'
    summary['changes_vs_v3']={}
    errorrows=[]
    for role,mask,key in [('primary_multicolor16',multi,'v3_primary'),('pair_family_cv8',pairs,'v3_cross_fitted')]:
        diff=metrics[key]['delta_e_2000']-oldmetrics[key]['delta_e_2000']
        summary['changes_vs_v3'][role]=dict(color_improved=int(np.sum(diff[mask]<0)),color_worsened=int(np.sum(diff[mask]>0)),spectral_improved=int(np.sum(metrics[key]['spectral_rmse'][mask]<oldmetrics[key]['spectral_rmse'][mask])))
    for i in range(len(c)):
        key='v3_cross_fitted' if pairs[i] else 'v3_primary'
        item=dict(source_row=int(rows[i]),family=v1.family(c[i]),role='pair_cv' if pairs[i] else 'multicolor' if multi[i] else 'calibration')
        for name,m in [('v1',metrics['v1']),('v3',oldmetrics[key]),('hybrid',metrics[key])]:
            item.update({name+'_'+k:float(v[i]) for k,v in m.items()})
        errorrows.append(item)
    v1.write_json(HERE/'summary.json',summary);v3.write_csv(HERE/'errors.csv',errorrows)
    print(json.dumps({k:summary[k] for k in ['primary_multicolor16','pair_family_cv8','total_fit_seconds','changes_vs_v3']},indent=2))

if __name__=='__main__':main()

