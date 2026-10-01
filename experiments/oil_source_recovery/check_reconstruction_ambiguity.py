"""Minimax recovery and ambiguity audit; published means/counts enter constraints."""
import json,sys
from pathlib import Path
import numpy as np
from scipy.optimize import milp,Bounds,LinearConstraint
HERE=Path(__file__).parent;ROOT=HERE.resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments/oil_public_data'));from audit import load
sys.path.insert(0,str(ROOT/'experiments/oil_source_trace'));from trace import models
l,o,c,n,nm,r,_=load();pure=np.array([l.index(x) for x in o]);keep=(c>0).sum(1)>1
source=json.loads((HERE/'pair-flip-column-search.json').read_text())
start=min(source['cases'],key=lambda x:x['relative_L1']);p=np.array(start['mapping'])
target=np.array(list(json.loads((HERE/'figure6-vector-ticks.json').read_text())['MSE'].values()))
R=r[:,10:-10];P=np.array(list(models(c,R[p[pure]]).values()));N=87
def stats(q):
    err=np.mean((P-R[q][None])**2,axis=2);err[:,~keep]=0
    return err[:,keep].mean(1),np.bincount(err.argmin(0),minlength=7),np.bincount(err.argmax(0),minlength=7)
base,bc,wc=stats(p);delta=[];db=[];dw=[];upper=[]
for k in range(N):
    q=p.copy();q[2*k:2*k+2]=q[2*k:2*k+2][::-1];a,b,w=stats(q)
    delta.append(a-base);db.append(b-bc);dw.append(w-wc);upper.append(0 if any(i in [2*k,2*k+1] for i in pure) else 1)
D=np.array(delta).T;DB=np.array(db).T;DW=np.array(dw).T
A=[];low=[];high=[]
for j in range(7):
    row=np.r_[D[j]*1e6,-1];A.append(row);low.append(-np.inf);high.append((target[j]-base[j])*1e6)
    row=np.r_[-D[j]*1e6,-1];A.append(row);low.append(-np.inf);high.append((base[j]-target[j])*1e6)
for mat,base_count,expected in [(DB,bc,[7,154,2,0,0,0,12]),(DW,wc,[7,0,0,0,0,168,0])]:
    for j in range(7):A.append(np.r_[mat[j],0]);low.append(expected[j]-base_count[j]);high.append(expected[j]-base_count[j])
objective=np.r_[np.zeros(N),1];integral=np.r_[np.ones(N),0]
res=milp(objective,integrality=integral,bounds=Bounds(np.zeros(N+1),np.r_[upper,np.inf]),
         constraints=LinearConstraint(A,low,high),options={'time_limit':60,'mip_rel_gap':1e-7})
assert res.x is not None,res.message
bits=(res.x[:N]>.5).astype(int);q=p.copy()
for k in np.flatnonzero(bits):q[2*k:2*k+2]=q[2*k:2*k+2][::-1]
mean,best,worst=stats(q)
report={'warning':'Means and best/worst counts used in reconstruction; not independent validation.',
        'status':int(res.status),'message':res.message,'maximum_absolute_MSE_difference':float(abs(mean-target).max()),
        'MSE':mean.tolist(),'best':best.tolist(),'worst':worst.tolist(),'mapping':q.tolist(),
        'different_samples_from_L1_candidate':np.flatnonzero(q!=p).tolist()}
print({k:v for k,v in report.items() if k!='mapping'},flush=True)
# Search for a second distinct map within 5e-6 MSE of every published bar.
# This is a diagnostic tolerance, not a claim about original data uncertainty.
nogood=np.r_[np.where(bits==1,-1,1),0]
A2=np.vstack([A,nogood]);low2=np.r_[low,1-bits.sum()];high2=np.r_[high,np.inf]
other=milp(np.zeros(N+1),integrality=integral,bounds=Bounds(np.zeros(N+1),np.r_[upper,5]),
           constraints=LinearConstraint(A2,low2,high2),options={'time_limit':60})
report['alternative_search_status']=int(other.status);report['alternative_search_message']=other.message
if other.x is not None:
    alt=p.copy()
    for k in np.flatnonzero(other.x[:N]>.5):alt[2*k:2*k+2]=alt[2*k:2*k+2][::-1]
    a,b,w=stats(alt)
    report['alternative']={'mapping':alt.tolist(),'MSE':a.tolist(),'max_absolute_MSE_difference':float(abs(a-target).max()),
                           'best':b.tolist(),'worst':w.tolist(),'different_samples':np.flatnonzero(alt!=q).tolist()}
    print('alternative',report['alternative']['different_samples'],report['alternative']['max_absolute_MSE_difference'],flush=True)
(HERE/'reconstruction-ambiguity.json').write_text(json.dumps(report,indent=2))
