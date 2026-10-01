"""Test paired scan-order reconstruction against published aggregate scores.

Uses the published scores as constraints/objective, so this is source recovery,
not an independent paint-model validation. No importer or fitted model changes.
"""
import itertools,json,sys
from pathlib import Path
import numpy as np,colour
from scipy.optimize import milp,Bounds,LinearConstraint
HERE=Path(__file__).parent;ROOT=HERE.resolve().parents[1]
sys.path.insert(0,str(HERE));import align_photo as t
sys.path.insert(0,str(ROOT/'experiments/oil_source_trace'));from trace import models
target=np.array(list(json.loads((HERE/'figure6-vector-ticks.json').read_text())['MSE'].values()))
pure=np.array([t.labels.index(x) for x in t.order]);pure_sources=np.array([10,40,24,31,100,97,120])
p=np.empty(175,dtype=int)
for start,end in [(0,60),(60,120),(120,175)]:
    scan=[]
    for col in [0,2,4]:
        rows=([5,6,7,8,9,0,1,2,3,4] if start==0 else list(range(9,-1,-1))) if col==0 else list(range(10))
        for row in rows:
            scan.extend(start+row*6+col+x for x in [0,1] if start+row*6+col+x<end)
    p[start:end]=np.argsort(scan)+start
for a,b in zip([152,153,158,159,164,165,170,171],[149,153,150,154,151,155,152,156]):p[a]=b
X=np.c_[t.lin,np.ones(175)];coef=np.linalg.lstsq(X[pure_sources],t.photo[pure]**1.5,rcond=None)[0]
rgb=np.clip(X@coef,0,1)**(1/1.5);lab=colour.XYZ_to_Lab(colour.sRGB_to_XYZ(rgb));photo_cost=np.linalg.norm(t.plab[:,None]-lab[None],axis=2)
results=[]
for trim,nominal,mixtures in itertools.product([True,False],repeat=3):
    R=t.r[:,10:-10] if trim else t.r;C=t.nom if nominal else t.c
    keep=(C>0).sum(1)>1 if mixtures else np.ones(175,bool)
    pred=list(models(C,R[pure_sources]).values())
    def metric(pp):return np.array([np.mean((v[keep]-R[pp][keep])**2) for v in pred])
    base=metric(p);deltas=[];cost_deltas=[];low=[];high=[]
    for a in range(0,174,2):
        q=p.copy();q[a:a+2]=q[a:a+2][::-1];deltas.append(metric(q)-base)
        cost_deltas.append(float(photo_cost[a,q[a]]+photo_cost[a+1,q[a+1]]-photo_cost[a,p[a]]-photo_cost[a+1,p[a+1]]))
        can0=all(p[i]==j for i,j in zip(pure,pure_sources) if i in [a,a+1])
        can1=all(q[i]==j for i,j in zip(pure,pure_sources) if i in [a,a+1])
        assert can0 or can1;low.append(0 if can0 else 1);high.append(1 if can1 else 0)
    d=np.array(deltas).T;N=len(deltas)
    A=[];ub=[]
    for j in range(7):
        row=np.zeros(N+7);row[:N]=d[j]/target[j];row[N+j]=-1;A.append(row);ub.append(1-base[j]/target[j])
        row=np.zeros(N+7);row[:N]=-d[j]/target[j];row[N+j]=-1;A.append(row);ub.append(base[j]/target[j]-1)
    res=milp(np.r_[np.zeros(N),np.ones(7)],integrality=np.r_[np.ones(N),np.zeros(7)],
             bounds=Bounds(np.r_[low,np.zeros(7)],np.r_[high,np.full(7,np.inf)]),
             constraints=LinearConstraint(A,np.full(14,-np.inf),ub),options={'time_limit':30,'mip_rel_gap':1e-6})
    if res.x is None:continue
    q=p.copy()
    for k in np.flatnonzero(res.x[:N]>.5):q[2*k:2*k+2]=q[2*k:2*k+2][::-1]
    errors=metric(q)
    results.append({'trim':trim,'nominal':nominal,'mixtures_only':mixtures,'MSE':errors.tolist(),
                    'relative_L1':float(abs(errors/target-1).sum()),'max_absolute_difference':float(abs(errors-target).max()),
                    'status':int(res.status),'message':res.message,'mapping':q.tolist(),
                    'photo_cost':float(photo_cost[np.arange(175),q].mean())})
    print({k:v for k,v in results[-1].items() if k not in ['mapping','message']},flush=True)
(HERE/'pair-flip-column-search.json').write_text(json.dumps({'warning':'Scores used as reconstruction objective, not independent validation.',
     'pure_sources':pure_sources.tolist(),'target':target.tolist(),'cases':results},indent=2))
