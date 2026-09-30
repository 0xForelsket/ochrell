"""Post-fit source consistency check; no fitting, relabelling or data repair."""
import json
from pathlib import Path
import numpy as np
import audit

HERE=Path(__file__).resolve().parent
labels,order,c,nominal,nm,r,files=audit.load()
truth=r[:,10:-10]
endmembers=np.array([truth[labels.index(k)] for k in order])
predictions={'M1_additive':c@endmembers,
             'M2_geometric':np.exp(c@np.log(endmembers)),
             'M6_LIP_additive':1-np.exp(c@np.log1p(-endmembers)),
             'M7_LIP_subtractive':1-np.exp(-np.exp(c@np.log(-np.log1p(-endmembers))))}
mixtures=(c>0).sum(1)>1
band=int(np.argmin(abs(nm-550)))
result={'status':'post-hoc source consistency concern, not an identified data correction',
        'paper_reference':'https://doi.org/10.3390/s21072471',
        'paper_figure_6_visual_reading':'M2 is substantially better than M1; M6 is worse than M1. Graph-only comparison, no exact numeric reproduction target supplied.',
        'native_trimmed_support_nm':[float(nm[10]),float(nm[-11])],
        'as_labelled_forward_mse':{name:{'all175':float(np.mean((p-truth)**2)),
                                      'mixtures168':float(np.mean((p[mixtures]-truth[mixtures])**2))}
                                 for name,p in predictions.items()},
        'white_label_diagnostic':{'wavelength_nm':float(nm[band]),'white_reflectance':float(r[labels.index('W'),band]),
                                  'comparison_bC_reflectance':float(r[labels.index('bC'),band])},
        'limitations':'Different authors endmember extraction or preprocessing could contribute; alignment headers alone do not establish semantic correctness. No permutation search, relabelling, row removal or refit performed.'}
chosen=[order.index(k) for k in ['Y','C','B','W']]
keep=(c[:,[i for i in range(7) if i not in chosen]]==0).all(1)
grid=np.arange(440,741,10)
spec=np.array([np.interp(grid,nm[10:-10],a[10:-10]) for a in r])
pure=np.array([spec[labels.index(k)] for k in ['Y','C','B','W']])
envelope=[]
for label,a,observed in zip(np.array(labels)[keep],c[keep][:,chosen],spec[keep]):
    if (a>0).sum()==1:continue
    low=pure[a>0].min(0);high=pure[a>0].max(0)
    excess=np.maximum(np.maximum(low-observed,observed-high),0)
    envelope.append({'sample':str(label),'max_outside_pure_envelope':float(excess.max()),
                     'bands_above_diagnostic_cutoff_0_001':int((excess>.001).sum())})
result['selected_mixture_pure_envelope']=envelope
result['envelope_caveat']='0.001 is a descriptive cutoff, not a measured noise estimate; finite layers and preparation differences can also leave this opaque fixed-pure envelope.'
(HERE/'source-consistency.json').write_bytes((json.dumps(result,indent=2)+'\n').encode())
print(json.dumps({k:v for k,v in result.items() if k!='selected_mixture_pure_envelope'},indent=2))
