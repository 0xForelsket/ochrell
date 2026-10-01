"""Identify which pair directions remain feasible at declared diagnostic tolerances."""
import json,sys,time
from pathlib import Path
import numpy as np
from scipy.optimize import milp,Bounds,LinearConstraint
HERE=Path(__file__).parent;ROOT=HERE.resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments/oil_public_data'));from audit import load
sys.path.insert(0,str(ROOT/'experiments/oil_source_trace'));from trace import models
l,o,c,n,nm,r,_=load();pure=np.array([l.index(x) for x in o]);keep=(c>0).sum(1)>1
q=np.array(json.loads((HERE/'reconstruction-ambiguity.json').read_text())['mapping']);R=r[:,10:-10]
target=np.array(list(json.loads((HERE/'figure6-vector-ticks.json').read_text())['MSE'].values()))
P=np.array(list(models(c,R[q[pure]]).values()));N=87
def stats(p):
    e=np.mean((P-R[p][None])**2,axis=2);e[:,~keep]=0
    return e[:,keep].mean(1),np.bincount(e.argmin(0),minlength=7),np.bincount(e.argmax(0),minlength=7)
base,bc,wc=stats(q);ds=[];db=[];dw=[];upper=np.ones(N)
for k in range(N):
    p=q.copy();p[2*k:2*k+2]=p[2*k:2*k+2][::-1];a,b,w=stats(p)
    ds.append(a-base);db.append(b-bc);dw.append(w-wc)
    if any(i in [2*k,2*k+1] for i in pure):upper[k]=0
D=np.array(ds).T;DB=np.array(db).T;DW=np.array(dw).T
A=np.vstack([D*1e6,DB,DW]);expected_b=np.array([7,154,2,0,0,0,12]);expected_w=np.array([7,0,0,0,0,168,0])
palette=(c[:,[o.index(k) for k in ['V','O','G']]]==0).all(1)
report={'warning':'Conditional ambiguity within the paired-scan hypothesis, fixed pure identities, and published-mean/count constraints. Not a proof of unrestricted uniqueness.',
        'base_mapping':q.tolist(),'target':target.tolist(),'cases':[]}
start=time.perf_counter()
for tol in [2e-6,5e-6,1e-5]:
    low=np.r_[(target-base-tol)*1e6,expected_b-bc,expected_w-wc]
    high=np.r_[(target-base+tol)*1e6,expected_b-bc,expected_w-wc]
    cons=LinearConstraint(A,low,high);amb=[];unknown=[];tested=0
    for k in np.flatnonzero(upper):
        lower=np.zeros(N);lower[k]=1
        sol=milp(np.zeros(N),integrality=np.ones(N),bounds=Bounds(lower,upper),constraints=cons,options={'time_limit':2})
        tested+=1
        if sol.x is not None:
            p=q.copy()
            for j in np.flatnonzero(sol.x>.5):p[2*j:2*j+2]=p[2*j:2*j+2][::-1]
            amb.append({'pair':int(k),'labels':l[2*k:2*k+2],'affects_four_material_subset':bool(palette[2*k:2*k+2].any()),'example_mapping':p.tolist()})
        elif sol.status!=2:unknown.append({'pair':int(k),'status':int(sol.status),'message':sol.message})
        if tested%20==0:print('tolerance',tol,'tested',tested,'ambiguous',len(amb),'unresolved',len(unknown),flush=True)
    case={'tolerance':tol,'tested_pairs':tested,'ambiguous_pairs':amb,'unresolved_solver_cases':unknown,
          'subset_ambiguous_labels':[label for x in amb for label in x['labels'] if palette[l.index(label)]]}
    report['cases'].append(case)
    (HERE/'pair-ambiguity-audit.json').write_text(json.dumps(report,indent=2))
    print('DONE',tol,[(x['pair'],x['labels']) for x in amb],'subset',case['subset_ambiguous_labels'],'unknown',unknown,flush=True)
report['seconds']=time.perf_counter()-start
(HERE/'pair-ambiguity-audit.json').write_text(json.dumps(report,indent=2))
