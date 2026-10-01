"""Change only K-M calibration rows; preserve the empirical second stage."""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='1'
import argparse
import csv
import importlib.util
import json
import time
from pathlib import Path

import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
spec=importlib.util.spec_from_file_location('transfer',ROOT/'experiments/oil_ternary_transfer/run.py')
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
v1,v3,emp=old.v1,old.v3,old.empirical
ORIGINAL=old.DEFAULT/'frozen-models.json'
DEFAULT=ROOT/'target/measured-oils/anchor-base'
METHODS=['original_km','original_empirical','anchor_km','anchor_empirical']


def correction_stage(c,target,base_model):
    """The frozen empirical.fit second stage, accepting an already-frozen base."""
    before=json.dumps(base_model,sort_keys=True)
    c,x=emp.features(c);base=v3.predicted(c,base_model)
    active=np.max(abs(x),axis=(0,1))>0
    residual,jac=emp.objective(base,x,target,active)
    start=time.perf_counter()
    sol=emp.least_squares(residual,np.zeros(active.sum()),jac=jac,bounds=(-.8,.8),
        max_nfev=2000,ftol=1e-10,xtol=1e-10,gtol=1e-10)
    theta=np.zeros(24);theta[active]=sol.x
    meta={'success':bool(sol.success),'message':sol.message,'nfev':sol.nfev,'objective':float(sol.fun@sol.fun),
        'bound_variables':int(np.count_nonzero(sol.active_mask)),'elapsed_seconds':time.perf_counter()-start,
        'active_parameters':int(active.sum())}
    if not sol.success:raise RuntimeError(str(meta))
    assert json.dumps(base_model,sort_keys=True)==before
    return {'base':base_model,'theta':theta.tolist(),'active':active.tolist(),'optimizer':meta}


def inputs():
    jobs,previous_manifest=old.inputs()
    raw=ORIGINAL.read_bytes();assert v1.sha(raw)=='ddc0e552df366ed4c0e00bdfeb581ca03f48f3ab1f71501808bc2ec778b94fbb'
    original=json.loads(raw);assert original['manifest']==previous_manifest
    for key,j in jobs.items():
        count=(j['c']>0).sum(1)
        anchor=j['train']&((count==1)|(j['c'][:,3]>0))
        assert (count[anchor]==1).sum()==4 and not (anchor & j['test']).any()
        assert not (anchor & (count==2) & (j['c'][:,3]==0)).any()
        for paint in range(3):assert (anchor & (j['c'][:,paint]>0)&(j['c'][:,3]>0)).any()
        j['anchor']=anchor
    files=[Path(__file__),HERE/'PLAN.md',ORIGINAL,ROOT/'experiments/oil_ternary_transfer/errors.csv',
        ROOT/'experiments/oil_failure_cases/summary.json']
    manifest={'experiment':'Pure/white base; unchanged full-binary empirical stage', 'original_manifest':previous_manifest,
        'hashes':{p.relative_to(ROOT).as_posix():v1.sha(p.read_bytes()) for p in files},
        'settings':previous_manifest['settings'],
        'partitions':{key:{'base_rows':j['rows'][j['anchor']].tolist(),'pair_stage_rows':j['rows'][j['train']].tolist(),
                           'assessment_rows':j['rows'][j['test']].tolist()} for key,j in jobs.items()}}
    return jobs,original,manifest,raw


def fit_one(key,c_anchor,r_anchor,c_full,r_full,settings):
    stage='base'
    try:
        base=v1.fit_model(c_anchor.copy(),r_anchor.copy(),settings)
        stage='pair_controls';model=correction_stage(c_full.copy(),r_full.copy(),base)
        return key,{'status':'success','model':model}
    except Exception as error:
        return key,{'status':'failed','stage':stage,'error_type':type(error).__name__,'message':str(error)}


def fit_jobs(jobs,settings,workers,perturb=False):
    from concurrent.futures import ProcessPoolExecutor,as_completed
    results={}
    with ProcessPoolExecutor(max_workers=workers) as pool:
        pending=[]
        for key,j in jobs.items():
            measured=j['measured'].copy()
            if perturb:measured[~j['train']]=np.random.default_rng(351).uniform(.02,.98,measured[~j['train']].shape)
            pending.append(pool.submit(fit_one,key,j['c'][j['anchor']],measured[j['anchor']],j['c'][j['train']],measured[j['train']],settings))
        for future in as_completed(pending):
            key,r=future.result();results[key]=r;print('refit' if perturb else 'fit',len(results),'/',len(jobs),key,r['status'],flush=True)
    return {key:results[key] for key in jobs}


def comparisons(metrics):
    result={}
    for new,baseline in [('anchor_empirical','original_empirical'),('anchor_km','original_km'),
                         ('anchor_empirical','anchor_km'),('anchor_empirical','original_km')]:
        result[new+'_vs_'+baseline]={}
        for metric in ['spectral_rmse','delta_e_2000']:
            a,b=metrics[new][metric],metrics[baseline][metric];d=a-b
            result[new+'_vs_'+baseline][metric]={'mean_difference':float(d.mean()),
                'improvement_percent':float(100*(b.mean()-a.mean())/b.mean()),'improved':int((d < -1e-12).sum()),
                'worsened':int((d > 1e-12).sum()),'tied':int((abs(d)<=1e-12).sum())}
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['prepare','fit','verify','evaluate'])
    p.add_argument('--out',type=Path,default=DEFAULT);p.add_argument('--workers',type=int,default=3);args=p.parse_args()
    out=v1.research_directory(args.out);jobs,original,manifest,raw_old=inputs()
    partition=out/'partition.json';frozen=out/'frozen-models.json'
    if args.phase=='prepare':
        assert not partition.exists() and not frozen.exists(),'Refusing preparation overwrite'
        v1.write_json(partition,manifest)
        print(json.dumps({k:{'base':int(j['anchor'].sum()),'pair_stage':int(j['train'].sum()),'targets':int(j['test'].sum())} for k,j in jobs.items()},indent=2));return
    assert json.loads(partition.read_text(encoding='utf-8'))==manifest
    if args.phase=='fit':
        assert not frozen.exists(),'Refusing frozen-model overwrite'
        results=fit_jobs(jobs,manifest['settings'],args.workers)
        v1.write_json(frozen,{'manifest':manifest,'results':results})
        print('Frozen SHA256',v1.sha(frozen.read_bytes()),'failures',sum(r['status']!='success' for r in results.values()))
        assert ORIGINAL.read_bytes()==raw_old;return
    raw=frozen.read_bytes();bundle=json.loads(raw);assert bundle['manifest']==manifest
    successful={k:j for k,j in jobs.items() if bundle['results'][k]['status']=='success'}
    failures={k:r for k,r in bundle['results'].items() if r['status']!='success'}
    if args.phase=='verify':
        repeats=fit_jobs(successful,manifest['settings'],args.workers,perturb=True)
        checks={'original_pair_stage_theta_max_abs':0.0,'scalar_km_max_abs':0.0,'scalar_empirical_max_abs':0.0,
            'pure_max_abs':0.0,'excluded_target_coefficient_change':0.0,'chromatic_calibration_base_change':0.0,
            'dense_min':1.0,'dense_max':0.0,'base_unchanged_during_pair_stage':True}
        rng=np.random.default_rng(2035197);dense=np.vstack([rng.dirichlet(np.ones(4),512),np.eye(4),[[1/3,1/3,1/3,0]]])
        for key,j in successful.items():
            a=repeats[key];assert a['status']=='success',a
            a=a['model'];model=bundle['results'][key]['model']
            for field in ['theta','active']:np.testing.assert_array_equal(a[field],model[field])
            for field in ['q','log_relative_s','K','S']:np.testing.assert_array_equal(a['base'][field],model['base'][field])
            # A stronger isolation check: change chromatic binary targets that
            # are allowed in stage two, then verify stage one's base is unchanged.
            changed=j['measured'].copy();mask=j['train']&~j['anchor']
            changed[mask]=rng.uniform(.02,.98,changed[mask].shape)
            base_again=v1.fit_model(j['c'][j['anchor']].copy(),changed[j['anchor']].copy(),manifest['settings'])
            for field in ['q','log_relative_s','K','S']:np.testing.assert_array_equal(base_again[field],model['base'][field])
            old_model=original['results'][key]['model']
            parity=correction_stage(j['c'][j['train']].copy(),j['measured'][j['train']].copy(),old_model['base'])
            theta_error=float(abs(np.array(parity['theta'])-np.array(old_model['theta'])).max())
            checks['original_pair_stage_theta_max_abs']=max(checks['original_pair_stage_theta_max_abs'],theta_error)
            assert theta_error<1e-12
            np.testing.assert_array_equal(parity['active'],old_model['active'])
            c=j['c'];pure=(c>0).sum(1)==1
            predictions={'km':v3.predicted(c,model['base']),'empirical':emp.predict(c,model)}
            refs={'km':np.array([[old.reference.opaque(x,model['base'],b) for b in range(31)] for x in c]),
                  'empirical':np.array([[old.reference.interaction(x,model,b) for b in range(31)] for x in c])}
            for method,pred in predictions.items():
                checks['scalar_'+method+'_max_abs']=max(checks['scalar_'+method+'_max_abs'],float(abs(pred-refs[method]).max()))
                checks['pure_max_abs']=max(checks['pure_max_abs'],float(abs(pred[pure]-j['measured'][pure]).max()))
                assert np.isfinite(pred).all() and (pred>0).all() and (pred<1).all()
            for pred in [v3.predicted(dense,model['base']),emp.predict(dense,model)]:
                assert np.isfinite(pred).all() and (pred>0).all() and (pred<1).all()
                checks['dense_min']=min(checks['dense_min'],float(pred.min()));checks['dense_max']=max(checks['dense_max'],float(pred.max()))
        for key in ['scalar_km_max_abs','scalar_empirical_max_abs','pure_max_abs']:assert checks[key]<1e-12,key
        result={'manifest':manifest,'new_bundle_sha256':v1.sha(raw),'old_bundle_sha256':v1.sha(raw_old),
            'successful_palettes':len(successful),'failed_palettes':failures,'checks':checks,
            'excluded_target_refits':len(successful),'chromatic_binary_perturbation_base_refits':len(successful),
            'archived_second_stage_parity_checks':len(successful),'dense_recipes_per_palette':len(dense)}
        for dest in [HERE,out]:v1.write_json(dest/'verification.json',result)
        print(json.dumps({k:v for k,v in result.items() if k!='manifest'},indent=2))
    else:
        verification=json.loads((out/'verification.json').read_text(encoding='utf-8'))
        assert verification['manifest']==manifest and verification['new_bundle_sha256']==v1.sha(raw)
        previous={int(r['source_row']):r for r in csv.DictReader((ROOT/'experiments/oil_ternary_transfer/errors.csv').open(newline=''))}
        _,white,lab=v1.colorimetry();palette_results={};records=[];calibration=[];gathered={m:{} for m in METHODS};replay_error=0.0
        for key,j in successful.items():
            model=bundle['results'][key]['model'];baseline=original['results'][key]['model'];c=j['c'];test=j['test']
            predictions={'original_km':v3.predicted(c,baseline['base']),'original_empirical':emp.predict(c,baseline),
                         'anchor_km':v3.predicted(c,model['base']),'anchor_empirical':emp.predict(c,model)}
            metrics={m:v1.errors(j['measured'],pred,lab) for m,pred in predictions.items()}
            subset={m:{metric:value[test] for metric,value in errors.items()} for m,errors in metrics.items()}
            palette_results[key]={'palette':j['palette'],'base_rows':j['rows'][j['anchor']].tolist(),
                'metrics':{m:v1.summarize(errors,test) for m,errors in metrics.items()},'comparisons':comparisons(subset),
                'optimizer':{'base':model['base']['runs'],'selected_start':model['base']['selected_start'],'empirical':model['optimizer']}}
            for method,errors in metrics.items():
                for metric,value in errors.items():gathered[method].setdefault(metric,[]).extend(value[test].tolist())
            for i in np.flatnonzero(test):
                row=int(j['rows'][i]);rec={'palette':key,'source_row':row,'paints':'; '.join(j['palette']['paint_names'][:3]),
                    'base_calibration_count':int(j['anchor'].sum()),'pair_calibration_count':int(j['train'].sum()),
                    'c1':float(c[i,0]),'c2':float(c[i,1]),'c3':float(c[i,2])}
                rec.update({m+'_'+metric:float(value[i]) for m,errors in metrics.items() for metric,value in errors.items()});records.append(rec)
                for method,old_method in [('original_km','km'),('original_empirical','empirical')]:
                    for metric in metrics[method]:replay_error=max(replay_error,abs(rec[method+'_'+metric]-float(previous[row][old_method+'_'+metric])))
            for i in np.flatnonzero(j['train']):
                rec={'palette':key,'source_row':int(j['rows'][i]),'role':'pure' if (c[i]>0).sum()==1 else 'white_tint' if c[i,3]>0 else 'chromatic_binary',
                     'used_for_new_base':bool(j['anchor'][i])}
                rec.update({m+'_'+metric:float(value[i]) for m,errors in metrics.items() for metric,value in errors.items()});calibration.append(rec)
        assert replay_error<1e-11
        arrays={m:{metric:np.array(values) for metric,values in errors.items()} for m,errors in gathered.items()}
        macro={m:{metric:np.array([r['metrics'][m][metric]['mean'] for r in palette_results.values()]) for metric in ['spectral_rmse','delta_e_2000']} for m in METHODS}
        complete=len(successful)==25 and len(records)==35
        aggregate={m:v1.summarize(errors,np.ones(len(records),bool)) for m,errors in arrays.items()} if records else None
        result={'status':'Complete exploratory calibration ablation on exposed targets' if complete else 'Incomplete cohort; failed palettes retained',
            'complete_primary':complete,'manifest':manifest,'new_bundle_sha256':v1.sha(raw),'old_bundle_sha256':v1.sha(raw_old),
            'scored_rows':len(records),'failed_palettes':failures,'primary35':aggregate if complete else None,
            'successful_subset_only':aggregate if not complete else None,'comparisons':comparisons(arrays) if records else None,
            'macro_palette_means':{m:{metric:float(values.mean()) for metric,values in errors.items()} for m,errors in macro.items()} if records else None,
            'macro_comparisons':comparisons(macro) if records else None,'palettes':palette_results,'original_score_replay_max_abs':replay_error,
            'colorimetry':{'window_nm':[400,700],'white_xyz':white.tolist(),'caveat':'Truncated D65/2-degree window, not independent full-visible validation.'}}
        for dest in [HERE,out]:
            v1.write_json(dest/'summary.json',result)
            if records:v3.write_csv(dest/'errors.csv',records);v3.write_csv(dest/'calibration.csv',calibration)
        print(json.dumps({k:result[k] for k in ['status','scored_rows','failed_palettes','primary35','comparisons','macro_palette_means','macro_comparisons']},indent=2))
    assert frozen.read_bytes()==raw and ORIGINAL.read_bytes()==raw_old


if __name__=='__main__':main()
