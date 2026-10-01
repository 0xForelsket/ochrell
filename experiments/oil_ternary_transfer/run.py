"""Execute the frozen 25-palette/35-ternary cohort without tuning methods."""
import os
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
import argparse
import importlib.util
import io
import itertools
import json
import platform
import sys
import zipfile
from pathlib import Path

import numpy as np
import scipy

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import measured_oils as v1
import measured_oils_chromatic as v3


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


empirical = module('transfer_empirical', ROOT/'experiments/oil_parallel/interaction/run.py')
reference = module('transfer_reference', ROOT/'experiments/oil_parallel/validate_comparison.py')
SOURCE = ROOT/'target/measured-oils/source/spectralDatasets.zip'
COHORT = ROOT/'experiments/oil_ternary_sources/next-cohort.json'
ATTENUATION = ROOT/'experiments/oil_ternary_attenuation/run.py'
DEFAULT = ROOT/'target/measured-oils/ternary-transfer'


def inputs():
    assert v1.sha(COHORT.read_bytes()) == '4e041683aef3205c8f0219d479c5889993486cfa4bb9e6e26450162db3b70247'
    assert v1.sha(ATTENUATION.read_bytes()) == '9150a5692d344b1ede794cc02c7884e2a775071acf052b7107c942174263afa2'
    cohort = json.loads(COHORT.read_text(encoding='utf-8'))
    raw = SOURCE.read_bytes(); assert v1.sha(raw) == cohort['source_sha256'] == v1.HASHES['archive']
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        amounts_raw = z.read('oilmixtureportions.txt'); spectra_raw = z.read('oilspectra.txt')
    assert v1.sha(amounts_raw) == v1.HASHES['oilmixtureportions.txt']
    assert v1.sha(spectra_raw) == v1.HASHES['oilspectra.txt']
    c = np.loadtxt(io.BytesIO(amounts_raw)); r = np.loadtxt(io.BytesIO(spectra_raw))
    assert c.shape == (286,8) and r.shape == (286,31)
    assert np.isfinite(c).all() and (c >= 0).all() and (c.sum(1)>0).all()
    assert np.isfinite(r).all() and (r>0).all() and (r<1).all()
    c /= c.sum(1, keepdims=True)
    jobs = {}; covered = []
    for palette in cohort['palettes']:
        cols = np.array(palette['columns_one_based'])-1
        assert cols[-1] == 7 and len(set(cols)) == 4
        keep = (c[:,[i for i in range(8) if i not in cols]] == 0).all(1)
        rows = np.flatnonzero(keep)+1; recipes = c[keep][:,cols]; measured = r[keep]
        count = (recipes>0).sum(1)
        train = np.isin(rows, palette['calibration_rows_one_based'])
        test = np.isin(rows, palette['assessment_rows_one_based'])
        np.testing.assert_array_equal(train, count<=2)
        np.testing.assert_array_equal(test, (count==3)&(recipes[:,3]==0))
        assert rows[train].tolist() == palette['calibration_rows_one_based']
        assert rows[test].tolist() == palette['assessment_rows_one_based']
        assert not (train & test).any() and (count[train]==1).sum() == 4
        for a,b in itertools.combinations(range(4),2):
            n = int((train & (recipes[:,a]>0) & (recipes[:,b]>0)).sum())
            assert n == palette['pair_calibration_counts'][f'{cols[a]+1}+{cols[b]+1}'] and n>0
        covered.extend(rows[test].tolist())
        jobs[palette['id']] = {'palette':palette,'rows':rows,'c':recipes,'measured':measured,'train':train,'test':test}
    assert len(jobs)==25 and len(covered)==len(set(covered))==35
    assert not set(covered)&set(cohort['previously_assessed_control_rows_one_based'])
    files = [Path(empirical.__file__),Path(v1.__file__),Path(v3.__file__),Path(reference.__file__),v1.CONFIG,ROOT/'data/cie_380_780_1nm.csv']
    previous = json.loads((ROOT/'experiments/oil_reconstructed/summary.json').read_text(encoding='utf-8'))['manifest']['original_method']['hashes']
    for path in files: assert v1.sha(path.read_bytes()) == previous[path.relative_to(ROOT).as_posix()]
    files += [Path(__file__),HERE/'PLAN.md',COHORT,SOURCE,ATTENUATION,ROOT/'experiments/oil_ternary_sources/NEXT-STUDY.md']
    manifest = {'experiment':'Additional Old Holland ternaries; fixed method and lambda=1 comparator',
        'hashes':{p.relative_to(ROOT).as_posix():v1.sha(p.read_bytes()) for p in files},
        'settings':json.loads(v1.CONFIG.read_text(encoding='utf-8')), 'cohort':cohort, 'attenuation_lambda':1.0,
        'environment':{'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__}}
    return jobs,manifest


def fit_one(key,c,target,settings):
    try:
        return key, {'status':'success','model':empirical.fit(c.copy(),target.copy(),settings)}
    except Exception as error:
        return key, {'status':'failed','error_type':type(error).__name__,'message':str(error)}


def fit_jobs(jobs,settings,workers,perturb=False):
    from concurrent.futures import ProcessPoolExecutor, as_completed
    results = {}
    with ProcessPoolExecutor(max_workers=workers) as pool:
        pending = []
        for key,j in jobs.items():
            measured=j['measured'].copy()
            if perturb:
                measured[~j['train']]=np.random.default_rng(4621).uniform(.02,.98,measured[~j['train']].shape)
            pending.append(pool.submit(fit_one,key,j['c'][j['train']],measured[j['train']],settings))
        for future in as_completed(pending):
            key,result=future.result();results[key]=result
            print('refit' if perturb else 'fit',len(results),'/',len(jobs),key,result['status'],flush=True)
    return {k:results[k] for k in jobs}


def compare_metrics(metrics):
    comparisons={}
    for candidate,baseline in [('empirical','km'),('attenuated','km'),('attenuated','empirical')]:
        comparisons[candidate+'_vs_'+baseline]={}
        for metric in ['spectral_rmse','delta_e_2000']:
            a,b=metrics[candidate][metric],metrics[baseline][metric];diff=a-b
            comparisons[candidate+'_vs_'+baseline][metric]={
                'mean_difference':float(diff.mean()), 'improvement_percent':float(100*(b.mean()-a.mean())/b.mean()),
                'improved':int((diff < -1e-12).sum()),'worsened':int((diff > 1e-12).sum()),'tied':int((abs(diff)<=1e-12).sum())}
    return comparisons


def main():
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['prepare','fit','verify','evaluate'])
    p.add_argument('--out',type=Path,default=DEFAULT);p.add_argument('--workers',type=int,default=3);args=p.parse_args()
    out=v1.research_directory(args.out);jobs,manifest=inputs()
    partition=out/'partition.json';frozen=out/'frozen-models.json'
    if args.phase=='prepare':
        assert not partition.exists() and not frozen.exists(),'Refusing preparation overwrite'
        v1.write_json(partition,manifest)
        print(json.dumps({'palettes':len(jobs),'targets':sum(int(j['test'].sum()) for j in jobs.values()),
                          'training_rows':{k:int(j['train'].sum()) for k,j in jobs.items()}},indent=2));return
    assert json.loads(partition.read_text(encoding='utf-8'))==manifest
    if args.phase=='fit':
        assert not frozen.exists(),'Refusing frozen model overwrite'
        results=fit_jobs(jobs,manifest['settings'],args.workers)
        v1.write_json(frozen,{'manifest':manifest,'results':results})
        print('Frozen SHA256',v1.sha(frozen.read_bytes()),'failures',sum(r['status']=='failed' for r in results.values()));return
    raw=frozen.read_bytes();bundle=json.loads(raw)
    assert bundle['manifest']==manifest and set(bundle['results'])==set(jobs)
    successful={k:j for k,j in jobs.items() if bundle['results'][k]['status']=='success'}
    failures={k:r for k,r in bundle['results'].items() if r['status']!='success'}
    if args.phase=='verify':
        # This happens before importing the archived attenuation module, whose
        # diagnostic guard disables the shared fitter in the current process.
        repeated=fit_jobs(successful,manifest['settings'],args.workers,perturb=True)
        for key,r in repeated.items():
            assert r['status']=='success',r
            a,b=r['model'],bundle['results'][key]['model']
            for field in ['theta','active']:np.testing.assert_array_equal(a[field],b[field])
            for field in ['q','log_relative_s','K','S']:np.testing.assert_array_equal(a['base'][field],b['base'][field])
        attenuation=module('fixed_attenuation',ATTENUATION)
        checks={'scalar_km_max_abs':0.0,'scalar_empirical_max_abs':0.0,'scalar_attenuated_max_abs':0.0,
            'pure_max_abs':0.0,'face_change_max_abs':0.0,'lambda_zero_change_max_abs':0.0,
            'excluded_target_coefficient_change':0.0,'dense_min':1.0,'dense_max':0.0}
        rng=np.random.default_rng(250035);dense=np.vstack([rng.dirichlet(np.ones(4),512),np.eye(4),[[1/3,1/3,1/3,0]]])
        face=[]
        for missing in range(3):
            f=np.zeros((100,4));f[:,[i for i in range(4) if i!=missing]]=rng.dirichlet(np.ones(3),100);face.append(f)
        face=np.vstack(face)
        for key,j in successful.items():
            model=bundle['results'][key]['model'];c=j['c'];pure=(c>0).sum(1)==1
            predictions={'km':v3.predicted(c,model['base']),'empirical':empirical.predict(c,model),'attenuated':attenuation.predict(c,model,1)}
            refs={'km':np.array([[reference.opaque(x,model['base'],b) for b in range(31)] for x in c]),
                'empirical':np.array([[reference.interaction(x,model,b) for b in range(31)] for x in c]),
                'attenuated':np.array([[attenuation.scalar(x,model,1,b) for b in range(31)] for x in c])}
            for method,pred in predictions.items():
                checks['scalar_'+method+'_max_abs']=max(checks['scalar_'+method+'_max_abs'],float(abs(pred-refs[method]).max()))
                checks['pure_max_abs']=max(checks['pure_max_abs'],float(abs(pred[pure]-j['measured'][pure]).max()))
                assert np.isfinite(pred).all() and (pred>0).all() and (pred<1).all()
            unaffected=(c[:,:3]>0).sum(1)<3
            np.testing.assert_array_equal(predictions['attenuated'][unaffected],predictions['empirical'][unaffected])
            np.testing.assert_array_equal(attenuation.predict(face,model,1),empirical.predict(face,model))
            np.testing.assert_array_equal(attenuation.predict(dense,model,0),empirical.predict(dense,model))
            for pred in [v3.predicted(dense,model['base']),empirical.predict(dense,model),attenuation.predict(dense,model,1)]:
                assert np.isfinite(pred).all() and (pred>0).all() and (pred<1).all()
                checks['dense_min']=min(checks['dense_min'],float(pred.min()));checks['dense_max']=max(checks['dense_max'],float(pred.max()))
        for k in ['scalar_km_max_abs','scalar_empirical_max_abs','scalar_attenuated_max_abs','pure_max_abs']:assert checks[k]<1e-12,k
        result={'manifest':manifest,'model_bundle_sha256':v1.sha(raw),'successful_palettes':len(successful),'failed_palettes':failures,
            'checks':checks,'perturbation_refits':len(successful),'random_dense_recipes_per_palette':len(dense),'face_recipes_per_palette':len(face)}
        for destination in [HERE,out]:v1.write_json(destination/'verification.json',result)
        print(json.dumps({k:v for k,v in result.items() if k!='manifest'},indent=2))
    else:
        verification=json.loads((out/'verification.json').read_text(encoding='utf-8'))
        assert verification['manifest']==manifest and verification['model_bundle_sha256']==v1.sha(raw)
        attenuation=module('fixed_attenuation',ATTENUATION)
        _,white,lab=v1.colorimetry();palette_results={};records=[];calibration=[];gathered={m:{} for m in ['km','empirical','attenuated']}
        for key,j in successful.items():
            model=bundle['results'][key]['model'];c=j['c'];test=j['test']
            predictions={'km':v3.predicted(c,model['base']),'empirical':empirical.predict(c,model),'attenuated':attenuation.predict(c,model,1)}
            metrics={m:v1.errors(j['measured'],pred,lab) for m,pred in predictions.items()}
            scores={m:v1.summarize(values,test) for m,values in metrics.items()}
            test_metrics={m:{metric:values[test] for metric,values in errors.items()} for m,errors in metrics.items()}
            palette_results[key]={'palette':j['palette'],'metrics':scores,'comparisons':compare_metrics(test_metrics),
                'optimizer':{'base':model['base']['runs'],'selected_start':model['base']['selected_start'],'empirical':model['optimizer']}}
            for method,errors in metrics.items():
                for metric,values in errors.items():gathered[method].setdefault(metric,[]).extend(values[test].tolist())
            for i in np.flatnonzero(test):
                rec={'palette':key,'source_row':int(j['rows'][i]),'paints':'; '.join(j['palette']['paint_names'][:3]),
                    'c1':float(c[i,0]),'c2':float(c[i,1]),'c3':float(c[i,2]),'white':float(c[i,3]),'gate':float(27*np.prod(c[i,:3])),
                    'calibration_count':int(j['train'].sum()),'minimum_pair_support':min(j['palette']['pair_calibration_counts'].values())}
                rec.update({m+'_'+metric:float(values[i]) for m,errors in metrics.items() for metric,values in errors.items()});records.append(rec)
            for i in np.flatnonzero(j['train']):
                rec={'palette':key,'source_row':int(j['rows'][i]),'role':'pure' if (c[i]>0).sum()==1 else 'binary'}
                rec.update({m+'_'+metric:float(values[i]) for m,errors in metrics.items() if m!='attenuated' for metric,values in errors.items()});calibration.append(rec)
        arrays={m:{metric:np.array(values) for metric,values in errors.items()} for m,errors in gathered.items()}
        complete=len(successful)==25 and len(records)==35
        aggregate={m:v1.summarize(errors,np.ones(len(records),bool)) for m,errors in arrays.items()} if records else None
        macro={m:{metric:np.array([r['metrics'][m][metric]['mean'] for r in palette_results.values()]) for metric in ['spectral_rmse','delta_e_2000']} for m in gathered}
        result={'status':'Complete 35-row same-source assessment' if complete else 'Incomplete cohort; failed palettes retained, full primary endpoint unavailable',
            'manifest':manifest,'model_bundle_sha256':v1.sha(raw),'complete_primary':complete,'scored_rows':len(records),'failed_palettes':failures,
            'primary35':aggregate if complete else None,'successful_subset_only':aggregate if not complete else None,
            'comparisons':compare_metrics(arrays) if records else None,
            'macro_palette_means':{m:{metric:float(values.mean()) for metric,values in errors.items()} for m,errors in macro.items()} if records else None,
            'macro_comparisons':compare_metrics(macro) if records else None,'palettes':palette_results,
            'colorimetry':{'window_nm':[400,700],'white_xyz':white.tolist(),'caveat':'Truncated D65/2-degree colorimetry, not numerically comparable to Grillini 440-740 nm scores.'}}
        for destination in [HERE,out]:
            v1.write_json(destination/'summary.json',result)
            if records:v3.write_csv(destination/'errors.csv',records);v3.write_csv(destination/'calibration.csv',calibration)
        print(json.dumps({k:result[k] for k in ['status','scored_rows','failed_palettes','primary35','comparisons','macro_palette_means','macro_comparisons']},indent=2))
    assert frozen.read_bytes()==raw


if __name__=='__main__':main()
