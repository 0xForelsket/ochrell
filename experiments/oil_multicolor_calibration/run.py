"""Compare binary-only and expanded calibration with whole recipe families excluded."""
import os
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import importlib.util
import json
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
spec=importlib.util.spec_from_file_location('unified_comparison_method',ROOT/'experiments/oil_unified_eight/run.py')
method=importlib.util.module_from_spec(spec);spec.loader.exec_module(method)
DEFAULT=ROOT/'target/measured-oils/multicolor-calibration'
OLD=ROOT/'target/measured-oils/unified-eight/frozen-model.json'
MODEL_NAMES=('binary_km','binary_empirical','expanded_km','expanded_empirical')


def ratio_key(recipe):
    chromatic=np.asarray(recipe,dtype=float)[:7]
    if not np.isfinite(chromatic).all() or (chromatic<0).any() or (chromatic>0).sum()<2:
        raise ValueError('Family requires at least two chromatic paints')
    return tuple(np.round(chromatic/chromatic.sum(),12))


def design(c):
    counts=(c>0).sum(1); anchors=(c[:,:7]>0).sum(1)<2; binary=counts<=2
    groups={}
    for i in np.flatnonzero(~anchors):groups.setdefault(ratio_key(c[i]),[]).append(int(i))
    folds={};jobs={};coverage=np.zeros(len(c),dtype=int)
    keys=list(groups)
    if len(keys)>1:
        distances=np.max(abs(np.array(keys)[:,None,:]-np.array(keys)[None,:,:]),axis=2)
        distances[np.diag_indices_from(distances)]=np.inf
        assert distances.min()>1e-9,'Ambiguous near-identical distinct ratio groups'
    for key,idx in groups.items():
        name=f'ratio-{idx[0]+1:03d}';test=np.zeros(len(c),dtype=bool);test[idx]=True
        coverage[test]+=1;fold={'ratio':list(key),'test_rows':(np.flatnonzero(test)+1).tolist(),'models':{}}
        ratios=c[idx,:7]/c[idx,:7].sum(1,keepdims=True)
        assert np.max(abs(ratios-np.array(key)))<1e-11
        for approach,train in [('binary',binary&~test),('expanded',~test)]:
            assert not (train&test).any() and train[anchors].all()
            assert all(ratio_key(x)!=key for x in c[train&~anchors])
            rows=(np.flatnonzero(train)+1).tolist()
            digest=method.old.sha(np.array(rows,dtype='<u2').tobytes())[:16]
            model_id=f'{approach}-{digest}'
            job={'approach':approach,'train_rows':rows}
            if model_id in jobs:assert jobs[model_id]==job
            jobs[model_id]=job;fold['models'][approach]=model_id
        folds[name]=fold
    np.testing.assert_array_equal(coverage,(~anchors).astype(int))
    assert len(folds)==107 and sum(x['approach']=='binary' for x in jobs.values())==51
    assert len(jobs)==158 and int(anchors.sum())==53 and int((counts>=3).sum())==183
    return folds,jobs,anchors


def inputs():
    c,r,binary,previous=method.inputs();folds,jobs,anchors=design(c)
    archived=json.loads(OLD.read_text(encoding='utf-8'))
    assert archived['manifest']==previous
    for name,digest in previous['hashes'].items():assert method.old.sha((ROOT/name).read_bytes())==digest,name
    files=[HERE/'PLAN.md',Path(__file__),HERE/'test_protocol.py',OLD,
        ROOT/'experiments/oil_unified_eight/summary.json',
        ROOT/'target/measured-oils/unified-eight/old-holland-eight-empirical.opp',
        ROOT/'target/measured-oils/unified-eight/old-holland-eight-km.opp']
    manifest={'experiment':'binary versus expanded calibration under whole chromatic-ratio exclusion',
        'original_manifest':previous,'hashes':{p.relative_to(ROOT).as_posix():method.old.sha(p.read_bytes()) for p in files},
        'anchors':(np.flatnonzero(anchors)+1).tolist(),'folds':folds,'jobs':jobs,
        'primary_rows':(np.flatnonzero((c>0).sum(1)>=3)+1).tolist(),
        'binary_assessment_rows':(np.flatnonzero(binary&~anchors)+1).tolist()}
    return c,r,manifest


def coefficient_difference(a,b):
    result={}
    for key in ('q','log_relative_s','K','S'):
        result[key]=float(np.max(abs(np.asarray(a['base'][key])-np.asarray(b['base'][key]))))
    result['theta']=float(np.max(abs(np.asarray(a['theta'])-np.asarray(b['theta']))))
    np.testing.assert_array_equal(a['active'],b['active'])
    return result


def preflight(c,r,manifest):
    binary=(c>0).sum(1)<=2
    fitted=method.fit(c[binary].copy(),r[binary].copy(),manifest['original_manifest']['settings'])
    old=json.loads(OLD.read_text(encoding='utf-8'))['model']
    diff=coefficient_difference(fitted,old);assert max(diff.values())==0
    _,_,lab=method.old.colorimetry()
    archived=json.loads((ROOT/'experiments/oil_unified_eight/summary.json').read_text(encoding='utf-8'))
    score_error=0.
    for name,corrected in [('km',False),('empirical',True)]:
        stats=method.old.summarize(method.old.errors(r,method.predict(c,fitted,corrected),lab),~binary)
        expected=archived['scores']['assessment183'][name]
        for key in ('spectral_rmse','spectral_mae','spectral_max_abs','delta_e_2000'):
            for stat in ('mean','median','p95','max'):score_error=max(score_error,abs(stats[key][stat]-expected[key][stat]))
    assert score_error<1e-12
    return {'coefficients_max_abs':diff,'archived_score_max_abs':score_error,'scored_statistics':32}


def worker(key,c,r,job,settings,perturb):
    idx=np.array(job['train_rows'])-1
    try:
        if perturb:
            r=r.copy();excluded=np.ones(len(c),dtype=bool);excluded[idx]=False
            seed=int(method.old.sha(key.encode())[:8],16)
            r[excluded]=np.random.default_rng(seed).uniform(.01,.99,r[excluded].shape)
        model=method.fit(c[idx].copy(),r[idx].copy(),settings)
        return key,{'status':'success','model':model}
    except Exception as e:
        return key,{'status':'failed','error_type':type(e).__name__,'message':str(e)}


def fit_jobs(c,r,manifest,out,workers,perturb=False):
    checkpoint=out/('verification-refits' if perturb else 'fits');checkpoint.mkdir(exist_ok=True)
    identity=method.old.sha((out/'partition.json').read_bytes());results={};pending={}
    for key,job in manifest['jobs'].items():
        path=checkpoint/f'{key}.json'
        if path.exists():
            saved=json.loads(path.read_text(encoding='utf-8'));assert saved['manifest_sha256']==identity
            results[key]=saved['result']
        else:pending[key]=job
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures={pool.submit(worker,key,c,r,job,manifest['original_manifest']['settings'],perturb):key for key,job in pending.items()}
        for future in as_completed(futures):
            key,result=future.result();results[key]=result
            method.old.write_json(checkpoint/f'{key}.json',{'manifest_sha256':identity,'result':result})
            if len(results)%10==0 or len(results)==len(manifest['jobs']) or result['status']!='success':
                print(('verification refits' if perturb else 'fits'),len(results),'/',len(manifest['jobs']),key,result['status'],flush=True)
    return dict(sorted(results.items()))


def verify(c,r,manifest,bundle,out,workers):
    results=bundle['results'];failed={k:x for k,x in results.items() if x['status']!='success'}
    assert not failed,failed
    repeated=fit_jobs(c,r,manifest,out,workers,True)
    dense=np.vstack([np.random.default_rng(20261001).dirichlet(np.ones(8),256),np.ones((1,8))/8])
    pure=np.flatnonzero((c>0).sum(1)==1)
    checks={'coefficient_max_abs':0.,'scalar_max_abs':0.,'pure_max_abs':0.,'dense_min':1.,'dense_max':0.}
    details={}
    for key,item in results.items():
        assert repeated[key]['status']=='success',repeated[key]
        model=item['model'];diff=coefficient_difference(model,repeated[key]['model']);assert max(diff.values())==0
        test_rows=sorted({row for fold in manifest['folds'].values() if key in fold['models'].values() for row in fold['test_rows']})
        probes=np.vstack([c[np.array(sorted(set(test_rows)|set((pure+1).tolist())))-1],dense[:2],dense[-1:]])
        for corrected in (False,True):
            actual=method.predict(probes,model,corrected)
            expected=np.array([method.scalar(x,model,corrected) for x in probes])
            delta=float(abs(actual-expected).max());assert delta<1e-12
            checks['scalar_max_abs']=max(checks['scalar_max_abs'],delta)
            pure_delta=float(abs(method.predict(c[pure],model,corrected)-r[pure]).max());assert pure_delta<1e-12
            checks['pure_max_abs']=max(checks['pure_max_abs'],pure_delta)
            spectrum=method.predict(np.vstack([c,dense]),model,corrected)
            assert np.isfinite(spectrum).all() and (spectrum>0).all() and (spectrum<1).all()
            checks['dense_min']=min(checks['dense_min'],float(spectrum.min()));checks['dense_max']=max(checks['dense_max'],float(spectrum.max()))
        details[key]={'training_count':len(manifest['jobs'][key]['train_rows']),
            'base_runs':model['base']['runs'],'correction':model['optimizer'],'active_controls':int(sum(model['active']))}
    return {'checks':checks,'refitted_models':len(repeated),'additional_dense_recipes_per_model':len(dense),'models':details}


def evaluate(c,r,manifest,results):
    assert all(x['status']=='success' for x in results.values()),'Incomplete paired assessment; do not drop failed families'
    predictions={name:np.full_like(r,np.nan) for name in MODEL_NAMES};families={};counts=(c>0).sum(1)
    _,_,lab=method.old.colorimetry();record_folds={}
    for key,fold in manifest['folds'].items():
        idx=np.array(fold['test_rows'])-1
        for i in idx:assert int(i) not in record_folds;record_folds[int(i)]=key
        for approach in ('binary','expanded'):
            model=results[fold['models'][approach]]['model']
            for suffix,corrected in [('km',False),('empirical',True)]:predictions[f'{approach}_{suffix}'][idx]=method.predict(c[idx],model,corrected)
    idx=np.array(sorted(record_folds));assert len(idx)==233
    metrics={name:method.old.errors(r[idx],p[idx],lab) for name,p in predictions.items()}
    masks={'multicolor183':counts[idx]>=3,'binary50':counts[idx]==2,'all233':np.ones(len(idx),dtype=bool),
        'multicolor_no_white':(counts[idx]>=3)&(c[idx,7]==0),'multicolor_with_white':(counts[idx]>=3)&(c[idx,7]>0)}
    masks.update({f'{i}_paints':counts[idx]==i for i in range(3,8)})
    groups={}
    for key,fold in manifest['folds'].items():
        group_mask=np.isin(idx+1,fold['test_rows']);primary=group_mask&masks['multicolor183']
        groups[key]={'test_rows':fold['test_rows'],'ratio':fold['ratio'],
            'all':{name:method.old.summarize(m,group_mask) for name,m in metrics.items()},
            'multicolor':{name:method.old.summarize(m,primary) for name,m in metrics.items()} if primary.any() else None}
    summary={'status':'paired whole-recipe-family exclusion; development evidence',
        'subsets':{role:{name:method.old.summarize(m,mask) for name,m in metrics.items()} for role,mask in masks.items()},
        'groups':groups,'comparisons':{},'equal_family_means':{},'method_settings_changed':False,
        'colorimetry':'31 measured bands, 400-700 nm; truncated D65/2 degree, matching white, unclipped XYZ/Lab'}
    for role,mask in masks.items():
        summary['comparisons'][role]={}
        for a,b,label in [('expanded_empirical','binary_empirical','expanded_vs_binary'),
            ('expanded_km','binary_km','base_only'),('expanded_empirical','expanded_km','expanded_correction_vs_base')]:
            summary['comparisons'][role][label]={}
            for metric in ('spectral_rmse','delta_e_2000'):
                x=metrics[a][metric][mask];y=metrics[b][metric][mask];delta=x-y
                summary['comparisons'][role][label][metric]={'mean_error_change_percent':float(100*(x.mean()/y.mean()-1)),
                    'improved':int((delta < -1e-12).sum()),'worsened':int((delta > 1e-12).sum()),'tied':int((abs(delta)<=1e-12).sum())}
    for role in ('multicolor','all'):
        selected=[g[role] for g in groups.values() if g[role] is not None]
        summary['equal_family_means'][role]={'families':len(selected), 'scores':{name:{metric:float(np.mean([g[name][metric]['mean'] for g in selected])) for metric in ('spectral_rmse','delta_e_2000')} for name in MODEL_NAMES}}
    records=[]
    for j,i in enumerate(idx):
        key=record_folds[int(i)];fold=manifest['folds'][key]
        records.append({'source_row':int(i+1),'family':key,'paint_count':int(counts[i]),'white_fraction':float(c[i,7]),
            'binary_training_count':len(manifest['jobs'][fold['models']['binary']]['train_rows']),
            'expanded_training_count':len(manifest['jobs'][fold['models']['expanded']]['train_rows']),
            **{f'{name}_{metric}':float(values[j]) for name,m in metrics.items() for metric,values in m.items()}})
    return summary,records


def main():
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['prepare','fit','verify','evaluate'])
    parser.add_argument('--out',type=Path,default=DEFAULT);parser.add_argument('--workers',type=int,default=4);args=parser.parse_args()
    if not 1<=args.workers<=8:raise ValueError('Use 1-8 worker processes')
    out=method.old.research_directory(args.out);c,r,manifest=inputs();partition=out/'partition.json';frozen=out/'frozen-models.json'
    if args.phase=='prepare':
        assert not partition.exists() and not frozen.exists(),'Use a fresh output directory'
        check=preflight(c,r,manifest)
        for dest in (out,HERE):method.old.write_json(dest/'baseline-check.json',check);method.old.write_json(dest/'partition.json',manifest)
        print(json.dumps({'families':len(manifest['folds']),'fits':len(manifest['jobs']),'baseline_check':check},indent=2));return
    assert json.loads(partition.read_text(encoding='utf-8'))==manifest
    identity=method.old.sha(partition.read_bytes())
    if args.phase=='fit':
        assert not frozen.exists(),'Refusing frozen-model overwrite'
        results=fit_jobs(c,r,manifest,out,args.workers)
        method.old.write_json(frozen,{'manifest_sha256':identity,'results':results})
        print('Frozen',method.old.sha(frozen.read_bytes()),'failures',sum(x['status']!='success' for x in results.values()));return
    raw=frozen.read_bytes();bundle=json.loads(raw);assert bundle['manifest_sha256']==identity
    if args.phase=='verify':
        result=verify(c,r,manifest,bundle,out,args.workers)
        result.update({'manifest_sha256':identity,'bundle_sha256':method.old.sha(raw)})
        for dest in (out,HERE):method.old.write_json(dest/'verification.json',result)
        print(json.dumps(result['checks'],indent=2))
    if args.phase=='evaluate':
        v=json.loads((out/'verification.json').read_text(encoding='utf-8'))
        assert v['manifest_sha256']==identity and v['bundle_sha256']==method.old.sha(raw)
        summary,records=evaluate(c,r,manifest,bundle['results'])
        summary.update({'manifest_sha256':identity,'bundle_sha256':method.old.sha(raw),'unique_fits':len(bundle['results'])})
        for dest in (out,HERE):method.old.write_json(dest/'summary.json',summary);method.old_chromatic.write_csv(dest/'errors.csv',records)
        print(json.dumps({'primary':summary['subsets']['multicolor183'],'comparison':summary['comparisons']['multicolor183'],'macro':summary['equal_family_means']['multicolor']},indent=2))
    assert frozen.read_bytes()==raw
    for name,digest in manifest['hashes'].items():assert method.old.sha((ROOT/name).read_bytes())==digest,name


if __name__=='__main__':main()
