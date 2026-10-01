"""Explain three frozen failure cases without fitting or changing source labels."""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='1'
import csv
import importlib.util
import itertools
import json
import math
import zipfile
from pathlib import Path

import numpy as np
from scipy.special import expit

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
spec=importlib.util.spec_from_file_location('transfer',ROOT/'experiments/oil_ternary_transfer/run.py')
study=importlib.util.module_from_spec(spec);spec.loader.exec_module(study)
v1,v3,emp=study.v1,study.v3,study.empirical
BUNDLE=study.DEFAULT/'frozen-models.json'
OUT=ROOT/'target/measured-oils/failure-cases'
NM=np.arange(400,701,10)
CASES={'old-holland-2-3-4':[205,206],'old-holland-1-3-7':[197,198,199,200]}
TARGETS={205,197,199}


def prohibited(*args,**kwargs):raise RuntimeError('No fitting permitted in frozen failure diagnosis')


v1.fit_model=prohibited;emp.fit=prohibited


def q(r):return (1-r)**2/(2*r)


def compose(base,shift):
    return np.where(shift==0,base,expit(np.log(base)-np.log1p(-base)+shift))


def decompose(c,model):
    c,x=emp.features(c)
    weights=np.array([4*c[:,a]*c[:,b] for a,b in emp.PAIRS]).T
    curves=emp.B@np.array(model['theta']).reshape(6,4).T
    terms=weights[:,None,:]*curves[None]
    np.testing.assert_allclose(terms.sum(2),x@model['theta'],rtol=0,atol=5e-16)
    return v3.predicted(c,model['base']),weights,terms


def write_csv(name,rows):
    with (HERE/name).open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    raw=BUNDLE.read_bytes();assert v1.sha(raw)=='ddc0e552df366ed4c0e00bdfeb581ca03f48f3ab1f71501808bc2ec778b94fbb'
    bundle=json.loads(raw);jobs,manifest=study.inputs();assert bundle['manifest']==manifest
    previous={int(r['source_row']):r for r in csv.DictReader((ROOT/'experiments/oil_ternary_transfer/errors.csv').open(newline=''))}
    _,_,lab=v1.colorimetry()
    checks={'source_second_reader_max_abs':0.0,'scalar_max_abs':0.0,'saved_error_max_abs':0.0,'recombination_max_abs':0.0,
        'shapley_sum_max_abs':0.0,'mse_identity_max_abs':0.0,'positive_scattering_envelope_passed':True}
    with zipfile.ZipFile(study.SOURCE) as z:
        portions=np.array([[float(x) for x in line.split()] for line in z.read('oilmixtureportions.txt').decode().splitlines() if line.strip()])
        spectra=np.array([[float(x) for x in line.split()] for line in z.read('oilspectra.txt').decode().splitlines() if line.strip()])
    assert portions.shape==(286,8) and spectra.shape==(286,31)
    observations=[];component_rows=[];coverage=[];regions=[];binary=[];envelopes=[];raw_recipes=[];jacobians={};curves={}
    for key,selected in CASES.items():
        j=jobs[key];m=bundle['results'][key]['model'];c=j['c'];r=j['measured'];ids={int(row):i for i,row in enumerate(j['rows'])}
        names=j['palette']['paint_names'];cols=np.array(j['palette']['columns_one_based'])-1
        np.testing.assert_array_equal(spectra[j['rows']-1],r)
        cp=portions[j['rows']-1][:,cols];cp/=cp.sum(1,keepdims=True);np.testing.assert_array_equal(cp,c)
        pure=np.array([r[np.flatnonzero((c[:,a]==1)&((c>0).sum(1)==1))[0]] for a in range(4)])
        km,weights,terms=decompose(c,m);full=compose(km,terms.sum(2))
        checks['recombination_max_abs']=max(checks['recombination_max_abs'],float(abs(full-emp.predict(c,m)).max()))
        S=np.array(m['base']['S']);assert (S>0).all()
        for i in range(len(c)):
            active=np.flatnonzero(c[i]>0);low=pure[active].min(0);high=pure[active].max(0)
            assert (km[i]>=low-1e-12).all() and (km[i]<=high+1e-12).all()
            outside=r[i]-np.clip(r[i],low,high)
            if j['train'][i] or int(j['rows'][i]) in selected:
                envelopes.append({'palette':key,'source_row':int(j['rows'][i]),'role':'calibration' if j['train'][i] else 'selected_target' if int(j['rows'][i]) in TARGETS else 'white_addition_diagnostic',
                    'below_pure_min_bands':int((outside < -1e-12).sum()),'above_pure_max_bands':int((outside > 1e-12).sum()),
                    'opaque_RMSE_floor':float(np.sqrt(np.mean(outside**2))), 'largest_violation':float(abs(outside).max()),
                    'red_600_700_violation_bands':','.join(str(x) for x in NM[(abs(outside)>1e-12)&(NM>=600)])})
        residual,jac=v1.objective(c[j['train']],r[j['train']],np.array(m['base']['q']),m['base']['settings'])
        J=jac(np.array(m['base']['log_relative_s']).ravel());N=int(j['train'].sum())*31
        sv=np.linalg.svd(J[:N],compute_uv=False);svp=np.linalg.svd(J,compute_uv=False)
        jacobians[key]={'data_rank':int(np.linalg.matrix_rank(J[:N])),'parameters':93,'data_singular_min':float(sv[-1]),
            'data_singular_max':float(sv[0]),'data_condition_number':float(sv[0]/sv[-1]),'regularized_condition_number':float(svp[0]/svp[-1]),
            'optimizer_objectives':[x['objective'] for x in m['base']['runs']], 'optimizer_successes':[x['success'] for x in m['base']['runs']]}
        for i in np.flatnonzero(j['train'] & ((c>0).sum(1)==2)):
            a,b=np.flatnonzero(c[i]);qa,qb,qm=q(pure[a]),q(pure[b]),q(r[i])
            with np.errstate(divide='ignore',invalid='ignore'):
                implied=c[i,b]*(qb-qm)/(c[i,a]*(qm-qa))
            feasible=np.isfinite(implied)&(implied>0)
            relative=implied[feasible]/(S[a]/S[b])[feasible]
            binary.append({'palette':key,'source_row':int(j['rows'][i]),'pair':names[a]+' / '+names[b],
                'first_fraction':float(c[i,a]),'positive_implied_ratio_bands':int(feasible.sum()),
                'median_implied_over_fitted_ratio':float(np.median(relative)) if len(relative) else None,
                'km_rmse':float(np.sqrt(np.mean((km[i]-r[i])**2))), 'empirical_rmse':float(np.sqrt(np.mean((full[i]-r[i])**2)))})
            curves[f'{key}_row{j["rows"][i]}_implied_scattering_ratio']=implied
        for row in selected:
            i=ids[row];raw_recipes.append({'source_row':row,'portions_in_original_eight_column_order':portions[row-1].tolist(),
                                          'normalized_fractions':c[i].tolist(),'paint_names':names})
            active=np.flatnonzero(weights[i]).tolist();predictions={'km':km[i],'empirical':full[i]}
            for p in active:
                predictions['only_'+str(p)]=compose(km[i],terms[i,:,p])
                predictions['without_'+str(p)]=compose(km[i],terms[i].sum(1)-terms[i,:,p])
            for value in predictions.values():assert np.isfinite(value).all() and (value>0).all() and (value<1).all()
            metrics={k:v1.errors(r[i:i+1],value[None],lab) for k,value in predictions.items()}
            scalar=np.array([study.reference.interaction(c[i],m,b) for b in range(31)])
            checks['scalar_max_abs']=max(checks['scalar_max_abs'],float(abs(full[i]-scalar).max()))
            if row in TARGETS:
                for method in ['km','empirical']:
                    for metric,value in metrics[method].items():
                        checks['saved_error_max_abs']=max(checks['saved_error_max_abs'],abs(float(value[0])-float(previous[row][method+'_'+metric])))
            d=full[i]-km[i];needed=r[i]-km[i];energy=float(np.mean(d*d));alignment=float(np.mean(d*needed))
            change=float(np.mean((full[i]-r[i])**2)-np.mean((km[i]-r[i])**2))
            checks['mse_identity_max_abs']=max(checks['mse_identity_max_abs'],abs(change-(energy-2*alignment)))
            observations.append({'palette':key,'source_row':row,'role':'selected_target' if row in TARGETS else 'white_addition_diagnostic',
                'white_fraction':float(c[i,3]),'gate':float(27*np.prod(c[i,:3])),'correction_rms':float(np.sqrt(energy)),
                'projection_alpha':alignment/energy,'spectral_MSE_change':change,
                **{method+'_'+metric:float(value[0]) for method in ['km','empirical'] for metric,value in metrics[method].items()}})
            all_mse={}
            for bits in itertools.product([0,1],repeat=len(active)):
                include=frozenset(p for p,bit in zip(active,bits) if bit)
                shift=terms[i][:,sorted(include)].sum(1) if include else np.zeros(31)
                all_mse[include]=float(np.mean((compose(km[i],shift)-r[i])**2))
            contributions=[]
            for p in active:
                shapley=0.0;n=len(active)
                for subset,error in all_mse.items():
                    if p in subset:continue
                    k=len(subset);shapley+=math.factorial(k)*math.factorial(n-k-1)/math.factorial(n)*(error-all_mse[subset|{p}])
                a,b=emp.PAIRS[p];contributions.append(shapley)
                component_rows.append({'source_row':row,'pair':names[a]+' / '+names[b],'pair_index':p,'weight':float(weights[i,p]),
                    'logit_shift_red_mean':float(terms[i,NM>=600,p].mean()),'MSE_reduction_shapley':shapley,
                    'only_pair_RMSE':float(metrics['only_'+str(p)]['spectral_rmse'][0]),
                    'without_pair_RMSE':float(metrics['without_'+str(p)]['spectral_rmse'][0])})
                cal=j['train']&(c[:,a]>0)&(c[:,b]>0)
                ratio=float(c[i,a]/c[i,b]);cal_ratios=c[cal,a]/c[cal,b]
                coverage.append({'source_row':row,'pair':names[a]+' / '+names[b],'target_first_over_second':ratio,
                    'calibration_rows':','.join(str(x) for x in j['rows'][cal]),
                    'calibration_ratios':','.join(f'{x:.12g}' for x in cal_ratios),
                    'inside_calibration_ratio_range':bool(cal_ratios.min()-1e-12<=ratio<=cal_ratios.max()+1e-12),
                    'exact_calibration_ratio':bool(np.isclose(cal_ratios,ratio,atol=1e-12,rtol=0).any())})
            checks['shapley_sum_max_abs']=max(checks['shapley_sum_max_abs'],abs(sum(contributions)+change))
            for lo,hi in [(400,490),(500,590),(600,700)]:
                band=(NM>=lo)&(NM<=hi)
                regions.append({'source_row':row,'lo_nm':lo,'hi_nm':hi,
                    'km_MSE_contribution':float(np.sum((km[i,band]-r[i,band])**2)/31),
                    'correction_MSE_change_contribution':float(np.sum((d*d-2*d*needed)[band])/31),
                    'mean_needed_reflectance_change':float(needed[band].mean()),'mean_actual_reflectance_change':float(d[band].mean())})
            curves[f'row{row}_measured']=r[i];curves[f'row{row}_terms']=terms[i]
            for method,value in predictions.items():curves[f'row{row}_{method}']=value
        # Preserve calibration context spectra for the figures without copying
        # raw source spectra into versioned result tables.
        for row in ([7,13,20,108,109] if key.endswith('2-3-4') else [26,46,63,138]):
            i=ids[row]
            for method,value in [('measured',r[i]),('km',km[i]),('empirical',full[i])]:curves[f'row{row}_{method}']=value

    j=jobs['old-holland-1-3-7'];m=bundle['results']['old-holland-1-3-7']['model'];ids={int(x):i for i,x in enumerate(j['rows'])}
    S=np.array(m['base']['S']);fitted_ratio=(.75*S[1]+.25*S[2])/S[0]
    blend_rows=[];effective_weights=[]
    for endpoint,blend in [('measured_row138',curves['row138_measured']),('frozen_row138',curves['row138_km'])]:
        for row,yellow in [(197,.8),(199,.95)]:
            target=curves[f'row{row}_measured'];qy=q(curves['row26_measured']);qd=q(blend);qt=q(target)
            with np.errstate(divide='ignore',invalid='ignore'):
                ratio=yellow*(qy-qt)/((1-yellow)*(qt-qd))
            curves[f'row{row}_ratio_{endpoint}']=ratio
            for b,nm in enumerate(NM):
                if not np.isfinite(ratio[b]) or ratio[b]<=0:continue
                # Closed-form inverse must exactly reproduce that single target
                # under its chosen effective endpoint; no coefficient is fitted.
                mixed=(yellow*qy[b]+(1-yellow)*ratio[b]*qd[b])/(yellow+(1-yellow)*ratio[b])
                decoded=1/(1+mixed+np.sqrt(mixed*(mixed+2)))
                assert abs(decoded-target[b])<1e-12
                blend_rows.append({'source_row':row,'endpoint':endpoint,'nm':int(nm),
                    'implied_blend_over_yellow_S':float(ratio[b]),'frozen_blend_over_yellow_S':float(fitted_ratio[b])})
    curves['frozen_blend_over_yellow_S']=fitted_ratio
    for row in [197,199]:
        i=ids[row]
        for band in [20,25,30]:
            fractions=j['c'][i]*S[:,band];fractions/=fractions.sum()
            effective_weights.append({'source_row':row,'nm':int(NM[band]),'yellow':float(fractions[0]),'scarlet':float(fractions[1]),'viridian':float(fractions[2])})

    shared=[]
    for key,j in jobs.items():
        cols=j['palette']['columns_one_based']
        if 1 not in cols or 7 not in cols:continue
        m=bundle['results'][key]['model'];iy,ig=cols.index(1),cols.index(7);S=np.array(m['base']['S'])
        ratio=S[ig]/S[iy];curves[key+'_viridian_over_yellow_S']=ratio
        for y in [.5,16/17,76/77]:
            c=np.zeros((1,4));c[0,iy]=y;c[0,ig]=1-y;pred=v3.predicted(c,m['base'])[0]
            curves[key+f'_YG_{y:.12g}']=pred
            shared.append({'palette':key,'yellow_fraction_in_binary':y,'measured_recipe_exists':y==.5,
                'R_600':float(pred[20]),'R_650':float(pred[25]),'R_700':float(pred[30]),
                'S_viridian_over_yellow_700':float(ratio[30])})
    assert len(shared)==12
    for k in ['scalar_max_abs','recombination_max_abs','shapley_sum_max_abs','mse_identity_max_abs']:assert checks[k]<1e-12,k
    assert checks['saved_error_max_abs']<1e-11
    for name,rows in [('observations.csv',observations),('pair-contributions.csv',component_rows),('coverage.csv',coverage),
        ('spectral-regions.csv',regions),('binary-consistency.csv',binary),('opaque-envelope.csv',envelopes),
        ('blend-ratios.csv',blend_rows),('effective-weights.csv',effective_weights),('shared-binary.csv',shared)]:write_csv(name,rows)
    np.savez_compressed(OUT/'spectra.npz',**curves)
    files=[Path(__file__),HERE/'PLAN.md',BUNDLE,ROOT/'experiments/oil_ternary_transfer/errors.csv',
        ROOT/'target/measured-oils/source/multispectralPaintDataset.pdf']
    result={'status':'Post-selection frozen diagnosis; no model fit or relabeling.',
        'hashes':{p.relative_to(ROOT).as_posix():v1.sha(p.read_bytes()) for p in files},'upstream_manifest':manifest,
        'checks':checks,'raw_recipe_records':raw_recipes,'local_jacobian':jacobians,
        'case_palettes':{k:jobs[k]['palette'] for k in CASES}}
    v1.write_json(HERE/'summary.json',result)
    assert BUNDLE.read_bytes()==raw
    for name,digest in manifest['hashes'].items():assert v1.sha((ROOT/name).read_bytes())==digest,name
    print(json.dumps({'checks':checks,'local_jacobian':jacobians},indent=2))


if __name__=='__main__':main()
