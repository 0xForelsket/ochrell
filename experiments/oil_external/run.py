"""One fixed-method transfer test; empirical implementation imported unchanged."""
import os
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'

import argparse
import csv
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import colour

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


audit = module('public_audit', ROOT/'experiments/oil_public_data/audit.py')
empirical = module('empirical_frozen', ROOT/'experiments/oil_parallel/interaction/run.py')
scalar = module('scalar_reference', ROOT/'experiments/oil_parallel/validate_comparison.py')
DEFAULT = ROOT/'target/measured-oils/grillini-fixed-method'
GRID = np.arange(440, 741, 10)


def load():
    labels, order, amounts, nominal, nm, reflectance, _ = audit.load()
    chosen = ['Y','C','B','W']
    keep = (amounts[:,[i for i,k in enumerate(order) if k not in chosen]] == 0).all(1)
    columns = [order.index(k) for k in chosen]
    c, intended = amounts[keep][:,columns], nominal[keep][:,columns]
    names = np.array(labels)[keep]
    support = nm[10:-10]
    assert support.min() <= GRID.min() and support.max() >= GRID.max()
    spectra = np.array([np.interp(GRID,support,r[10:-10]) for r in reflectance[keep]])
    assert spectra.shape == (34,31) and np.isfinite(spectra).all()
    return names,c,intended,spectra


def design(names,c,nominal):
    count = (c>0).sum(1)
    anchors = (count==1) | ((count==2)&(c[:,3]>0))
    pairs = (count==2)&(c[:,3]==0)
    multi = count==3
    pool = anchors|pairs
    assert anchors.sum()==13 and pairs.sum()==9 and multi.sum()==12
    keys = [tuple(np.round(r[:3]/r[:3].sum(),12)) if r[:3].sum() else None for r in nominal]
    folds = {}
    for i in np.flatnonzero(~anchors):
        key = keys[i]
        if key in [f['key'] for f in folds.values()]:continue
        test = np.array([k==key for k in keys])
        train = pool&~test
        assert not (test&anchors).any() and not (train&multi).any()
        assert train[anchors].all() and not (train&test).any()
        folds[str(names[i])] = {'train':train,'test':test,'key':key}
    assert len(folds)==12
    np.testing.assert_array_equal(np.sum([f['test'] for f in folds.values()],axis=0),(~anchors).astype(int))
    assert len({tuple(names[f['train']]) for f in folds.values()})==10
    # Rounded 2:1 parents must share their group with exact 2:1 chromatic ratios
    # from ternary recipes; all nine pair groups contain exactly one white tint.
    assert all(f['test'].sum()==2 for f in folds.values() if (f['test']&pairs).any())
    return anchors,pairs,multi,pool,folds


def colorimetry():
    with (ROOT/'data/cie_380_780_1nm.csv').open(newline='') as f:
        cie={int(r['nm']):r for r in csv.DictReader(f)}
    weights=np.array([[float(cie[n]['D65'])*float(cie[n][k]) for k in ['xbar','ybar','zbar']] for n in GRID])
    weights[[0,-1]]*=.5
    weights/=weights[:,1].sum()
    white=weights.sum(0);xy=white[:2]/white.sum()
    def lab(spectra):return colour.XYZ_to_Lab(spectra@weights,illuminant=xy)
    return lab,white


def provenance(names,folds):
    files=[HERE/'PLAN.md',Path(__file__),Path(audit.__file__),audit.SOURCE,Path(empirical.__file__),
           Path(v1.__file__),Path(v3.__file__),Path(scalar.__file__),v1.CONFIG,ROOT/'data/cie_380_780_1nm.csv']
    return {'experiment':'Grillini fixed-method transfer, grouped nominal recipe exclusions',
            'hashes':{p.relative_to(ROOT).as_posix():v1.sha(p.read_bytes()) for p in files},
            'grid_nm':GRID.tolist(),'fit_mass_basis':'published rounded dry-pigment mass fractions',
            'group_basis':'nominal ratios encoded by source sample labels',
            'settings':json.loads(v1.CONFIG.read_text()),
            'folds':{n:{'train':names[f['train']].tolist(),'test':names[f['test']].tolist(),
                        'nominal_chromatic_fraction':list(f['key'])} for n,f in folds.items()}}


def evaluate(names,c,measured,multi,pairs,pool,folds,bundle):
    p={k:measured.copy() for k in ('km','empirical')}
    for name,f in folds.items():
        model=bundle['models'][bundle['fold_models'][name]]
        p['km'][f['test']]=v3.predicted(c[f['test']],model['base'])
        p['empirical'][f['test']]=empirical.predict(c[f['test']],model)
    lab,white=colorimetry()
    metrics={name:v1.errors(measured,value,lab) for name,value in p.items()}
    roles={'ternary12':multi,'pairs9':pairs,'pooled21':multi|pairs}
    full=bundle['models'][bundle['primary_model']]
    old={'km':v1.errors(measured,v3.predicted(c,full['base']),lab),
         'empirical':v1.errors(measured,empirical.predict(c,full),lab)}
    result={'manifest':bundle['manifest'],'metric_caveat':'DE00 is restricted to 440-740 nm, not full-visible color error',
            'truncated_white_xyz':white.tolist(),
            'grouped':{role:{name:v1.summarize(m,mask) for name,m in metrics.items()} for role,mask in roles.items()},
            'parent_available_ternary12':{name:v1.summarize(m,multi) for name,m in old.items()},
            'groups':{name:{'test':names[f['test']].tolist(),'metrics':{n:v1.summarize(m,f['test']) for n,m in metrics.items()}}
                      for name,f in folds.items()},'changes':{},
            'optimizer':{name:{'base':m['base']['runs'],'empirical':m['optimizer']} for name,m in bundle['models'].items()}}
    for role,mask in roles.items():
        result['changes'][role]={}
        for metric in ['spectral_rmse','delta_e_2000']:
            d=metrics['empirical'][metric]-metrics['km'][metric]
            result['changes'][role][metric]={'improved':int((d[mask]<-1e-12).sum()),
                                            'worsened':int((d[mask]>1e-12).sum()),'tied':int((abs(d[mask])<=1e-12).sum())}
    records=[]
    for group,f in folds.items():
        for i in np.flatnonzero(f['test']):
            rec={'sample':str(names[i]),'group':group,'role':'pair' if pairs[i] else 'ternary'}
            rec.update({n+'_'+k:float(v[i]) for n,m in metrics.items() for k,v in m.items()})
            records.append(rec)
    return result,records


def verify(names,c,measured,folds,bundle):
    checked=set();scalar_error=pure_error=0.0
    pure=(c>0).sum(1)==1
    for name,f in folds.items():
        key=bundle['fold_models'][name]
        if key in checked:continue
        checked.add(key);model=bundle['models'][key]
        p=empirical.predict(c,model)
        q=np.array([[scalar.interaction(recipe,model,b) for b in range(31)] for recipe in c])
        scalar_error=max(scalar_error,float(abs(p-q).max()))
        pure_error=max(pure_error,float(abs(p[pure]-measured[pure]).max()))
        assert np.isfinite(p).all() and (p>0).all() and (p<1).all()
        altered=measured.copy();altered[~f['train']]=np.random.default_rng(309).uniform(.02,.98,altered[~f['train']].shape)
        again=empirical.fit(c[f['train']].copy(),altered[f['train']].copy(),bundle['manifest']['settings'])
        np.testing.assert_array_equal(again['theta'],model['theta'])
        np.testing.assert_array_equal(again['base']['log_relative_s'],model['base']['log_relative_s'])
    assert scalar_error<1e-12 and pure_error<1e-12
    return {'unique_fits':len(checked),'scalar_max_abs':scalar_error,'pure_max_abs':pure_error,
            'excluded_target_perturbation_coefficient_change':0.0,'finite_bounded_all34_all_models':True}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['prepare','fit','verify','evaluate'])
    parser.add_argument('--out',type=Path,default=DEFAULT);args=parser.parse_args()
    out=v1.research_directory(args.out)
    names,c,nominal,measured=load();anchors,pairs,multi,pool,folds=design(names,c,nominal)
    manifest=provenance(names,folds);partition=out/'partition.json';frozen=out/'frozen-models.json'
    if args.phase=='prepare':
        if frozen.exists():raise ValueError('Models already frozen')
        v1.write_json(partition,manifest)
        print(json.dumps({'anchors':int(anchors.sum()),'groups':manifest['folds'],'grid':manifest['grid_nm']},indent=2));return
    assert json.loads(partition.read_text())==manifest
    if args.phase=='fit':
        if frozen.exists():raise ValueError('Refusing frozen-model overwrite')
        models={};fold_models={};known={};primary=None
        for name,f in folds.items():
            key=tuple(names[f['train']])
            if key not in known:
                known[key]=name;models[name]=empirical.fit(c[f['train']].copy(),measured[f['train']].copy(),manifest['settings'])
                print(name,int(f['train'].sum()),models[name]['optimizer'],flush=True)
            fold_models[name]=known[key]
            if np.array_equal(f['train'],pool):primary=known[key]
        assert len(models)==10 and primary is not None
        v1.write_json(frozen,{'manifest':manifest,'models':models,'fold_models':fold_models,'primary_model':primary})
        print('Frozen SHA256',v1.sha(frozen.read_bytes()));return
    raw=frozen.read_bytes();bundle=json.loads(raw);assert bundle['manifest']==manifest
    if args.phase=='verify':
        result=verify(names,c,measured,folds,bundle)
        v1.write_json(HERE/'verification.json',result);print(json.dumps(result,indent=2))
    else:
        result,records=evaluate(names,c,measured,multi,pairs,pool,folds,bundle)
        result['model_bundle_sha256']=v1.sha(raw)
        for dest in [out,HERE]:v1.write_json(dest/'summary.json',result);v3.write_csv(dest/'errors.csv',records)
        print(json.dumps({'grouped':result['grouped'],'changes':result['changes']},indent=2))
    assert frozen.read_bytes()==raw


if __name__=='__main__':main()
