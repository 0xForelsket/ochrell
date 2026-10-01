"""Re-evaluate the frozen inferred map without searching or changing labels."""
import hashlib,json,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).parent;ROOT=HERE.resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments/oil_public_data'));import audit
sys.path.insert(0,str(ROOT/'experiments/oil_source_trace'));from trace import models,scalar
labels,order,c,nom,nm,r,_=audit.load()
assert hashlib.sha256((HERE/'mapping.json').read_bytes()).hexdigest()=='9e31ac91fcaa334b8bc56e9d3ae501d7ebe79de932ca066dba84ba276f9d6a22'
mapping_doc=json.loads((HERE/'mapping.json').read_text());p=np.array(mapping_doc['canonical_to_source'])
assert mapping_doc['source_archive_sha256']==audit.EXPECTED_SHA
assert mapping_doc['canonical_label_order']==labels
assert sorted(p.tolist())==list(range(175))
reference=json.loads((HERE/'figure6-vector-ticks.json').read_text())
target=np.array(list(reference['MSE'].values()));pure=[labels.index(k) for k in order]
keep=(c>0).sum(1)>1;observed=r[p,10:-10];endmembers=observed[pure]
pred=models(c,endmembers);err=np.array([np.mean((v-observed)**2,axis=1) for v in pred.values()])
assert np.max(err[:,~keep])<1e-25
err[:,~keep]=0
means=err[:,keep].mean(1);best=np.bincount(err.argmin(0),minlength=7).tolist();worst=np.bincount(err.argmax(0),minlength=7).tolist()
assert best==reference['counts']['best'] and worst==reference['counts']['worst']
assert np.max(abs(means-target))<2e-6
scalar_error=0
for i in [0,7,23,33,64,84,110,134,170,174]:
    for j in [0,45,100,165]:
        s=scalar(c[i],endmembers[:,j]);scalar_error=max(scalar_error,max(abs(s[k]-pred[k][i,j]) for k in pred))
assert scalar_error<1e-12
print(json.dumps({'status':'fixed-map checks passed; mapping remains inferred','samples':len(p),
                  'max_absolute_MSE_difference':float(abs(means-target).max()),'best':best,'worst':worst,
                  'scalar_parity':float(scalar_error),'mapping_sha256':hashlib.sha256((HERE/'mapping.json').read_bytes()).hexdigest()},indent=2))
