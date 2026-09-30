"""Bounded source reconstruction diagnostics; no fitting or data correction."""
import csv
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'experiments/oil_public_data'))
import audit


def models(c,e):
    linear=c@e
    geometric=np.exp(c@np.log(e))
    mean_root=c@np.sqrt(e)
    return {'M1':linear,'M2':geometric,'M3':mean_root**2,
            'M4':.5*linear+.5*geometric,'M5':mean_root*np.sqrt(geometric),
            'M6':1-np.exp(c@np.log1p(-e)),
            'M7':1-np.exp(-np.exp(c@np.log(-np.log1p(-e))))}


def scalar(recipe,values):
    linear=math.fsum(float(c)*float(r) for c,r in zip(recipe,values))
    geometric=math.prod(float(r)**float(c) for c,r in zip(recipe,values))
    root=math.fsum(float(c)*math.sqrt(float(r)) for c,r in zip(recipe,values))
    return {'M1':linear,'M2':geometric,'M3':root**2,'M4':.5*(linear+geometric),
            'M5':root*math.sqrt(geometric),
            'M6':1-math.prod((1-float(r))**float(c) for c,r in zip(recipe,values)),
            'M7':1-math.exp(-math.prod((-math.log1p(-float(r)))**float(c) for c,r in zip(recipe,values)))}


def main():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    labels,order,c,nominal,nm,r,files=audit.load()
    n=len(labels);band=int(np.argmin(abs(nm-550)))
    figure=json.loads((HERE/'figure6-values.json').read_text())['bar_width_derived_mse']
    mappings={'identity':np.arange(n)}
    for start in (0,1):
        enumerated=sorted(range(start,start+n),key=str)
        mappings[f'lexical_decimal_{start}based']=np.array([enumerated.index(i+start) for i in range(n)])
    records=[];pure=[];scalar_max=0.0;baseline=None
    for scenario,index in mappings.items():
        assert sorted(index.tolist())==list(range(n))
        for k in order:
            i=labels.index(k);j=int(index[i])
            pure.append({'case':scenario,'paint':k,'label_position_zero_based':i,
                         'hypothesized_spectrum_position_zero_based':j,
                         'wavelength_nm':float(nm[band]),'reflectance':float(r[j,band])})
        for grid,mask in [('full186',np.ones(len(nm),dtype=bool)),
                          ('trimmed166',(np.arange(len(nm))>=10)&(np.arange(len(nm))<len(nm)-10))]:
            observed=r[index][:,mask]
            endmembers=np.array([observed[labels.index(k)] for k in order])
            for mass,weights in [('stored',c),('nominal',nominal)]:
                predictions=models(weights,endmembers)
                assert all(np.isfinite(v).all() and (v>0).all() and (v<1).all() for v in predictions.values())
                # Power-mean relations establish implementation consistency, not
                # which model must have the smallest measurement residual.
                assert np.all(predictions['M2']<=predictions['M3']+1e-14)
                assert np.all(predictions['M3']<=predictions['M1']+1e-14)
                assert np.all(predictions['M1']<=predictions['M6']+1e-14)
                for sample in (0,14,33,64,110,174):
                    for wavelength in (0,len(endmembers[0])//2,len(endmembers[0])-1):
                        reference=scalar(weights[sample],endmembers[:,wavelength])
                        scalar_max=max(scalar_max,max(abs(reference[k]-predictions[k][sample,wavelength]) for k in reference))
                for population,keep in [('all175',np.ones(n,dtype=bool)),('mixtures168',(c>0).sum(1)>1)]:
                    mse={k:float(np.mean((v[keep]-observed[keep])**2)) for k,v in predictions.items()}
                    records.append({'ordering':scenario,'grid':grid,'fractions':mass,'population':population,
                                    **mse,'M2_less_than_M1':mse['M2']<mse['M1'],
                                    'M6_greater_than_M1':mse['M6']>mse['M1']})
                    if (scenario,grid,mass,population)==('identity','trimmed166','stored','all175'):
                        baseline=mse
    assert scalar_max<1e-12
    for file,values in [('cases.csv',records),('pure-identities.csv',pure)]:
        with (HERE/file).open('w',newline='',encoding='utf-8') as f:
            writer=csv.DictWriter(f,fieldnames=list(values[0]),lineterminator='\n');writer.writeheader();writer.writerows(values)
    identity=[x for x in records if x['ordering']=='identity']
    summary={'status':'No source correction established; all hypothesized mappings are diagnostic only',
             'case_count':len(records),'figure6_approximate_mse':figure,
             'identity_trimmed_stored_all175_mse':baseline,
             'identity_M2_range':[min(x['M2'] for x in identity),max(x['M2'] for x in identity)],
             'identity_M2_to_M1_ratio_range':[min(x['M2']/x['M1'] for x in identity),max(x['M2']/x['M1'] for x in identity)],
             'all_case_M2_less_than_M1_count':sum(x['M2_less_than_M1'] for x in records),
             'all_case_both_reported_order_relations_count':sum(x['M2_less_than_M1'] and x['M6_greater_than_M1'] for x in records),
             'white_reflectance_by_order':{x['case']:x['reflectance'] for x in pure if x['paint']=='W'},
             'scalar_max_abs_difference':scalar_max,
             'source_sha256':audit.EXPECTED_SHA,
             'hashes':{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in [HERE/'PLAN.md',Path(__file__),HERE/'extract_figure.py',Path(audit.__file__),HERE/'figure6-values.json']},
             'notes':['No optimization or permanent source relabelling; hypothetical pairings are diagnostic only.',
                      'No input rows deleted and no fitted coefficients changed.',
                      'No hypothesis chosen by reconstruction score.',
                      'Graph values are approximate; comparison is not exact reproduction of original numeric results.']}
    (HERE/'summary.json').write_bytes((json.dumps(summary,indent=2)+'\n').encode())
    fig,ax=plt.subplots(figsize=(9,4.5),layout='constrained')
    x=np.arange(7)
    ax.bar(x-.18,[figure[k] for k in figure],.36,label='Paper Figure 6 (approximate)',color='#8095a5')
    ax.bar(x+.18,[baseline[k] for k in figure],.36,label='Supplied tables, labelled order',color='#b16840')
    ax.set_xticks(x,list(figure));ax.set_ylabel('Mean spectral squared error')
    ax.set_title('Forward-model reconstruction does not reproduce the published ranking')
    ax.legend();ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
    fig.savefig(HERE/'baseline-comparison.png',dpi=170);plt.close(fig)
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
