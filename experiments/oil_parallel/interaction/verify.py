"""Post-fit invariants, without model selection or parameter changes."""
import json
import run as m
import numpy as np

rows,c,r,original=m.v1.load_source(m.ROOT/'target/measured-oils/source/spectralDatasets.zip')
primary,pairs,multi,folds=m.v3.design(c,original)
artifact=json.loads((m.ROOT/'target/measured-oils/parallel/interaction/frozen-models.json').read_text())
result={}
for name,(train,test) in folds.items():
    assert not (train&test).any() and not (train&multi).any()
    changed=r.copy();changed[test]=np.random.default_rng(137).uniform(0,1,changed[test].shape)
    # Only training arrays cross the fit boundary; changed withheld targets do
    # not affect either stage. This checks the actual production fit function.
    again=m.fit(c[train],changed[train],artifact['manifest']['settings'])
    frozen=artifact['models'][name]
    np.testing.assert_array_equal(again['theta'],frozen['theta'])
    np.testing.assert_array_equal(again['base']['log_relative_s'],frozen['base']['log_relative_s'])
    np.testing.assert_allclose(m.predict(c[test],frozen),m.v3.predicted(c[test],frozen['base']),atol=0,rtol=0)
    result[name]={'withheld_target_perturbation_max_change':0,'unseen_pair_equals_fold_base':True,'train_rows':int(train.sum()),'test_rows':int(test.sum())}
m.v1.write_json(m.Path(__file__).with_name('verification.json'),result)
corpus=np.vstack([np.eye(4)[a]*t+np.eye(4)[b]*(1-t) for a,b in m.PAIRS for t in np.linspace(0,1,101)])
rng=np.random.default_rng(811)
faces=[]
for omitted in range(4):
    face=np.zeros((500,4));face[:,[i for i in range(4) if i!=omitted]]=rng.dirichlet(np.ones(3),500);faces.append(face)
corpus=np.vstack([corpus,*faces]);model=artifact['models']['primary29'];pred=m.predict(corpus,model)
delta=pred-m.v3.predicted(corpus,model['base'])
boundary={'count':len(corpus),'min':float(pred.min()),'max':float(pred.max()),'finite':bool(np.isfinite(pred).all()),'correction_min':float(delta.min()),'correction_max':float(delta.max())}
assert np.isfinite(pred).all() and (pred>0).all() and (pred<1).all()
result['simplex_boundaries']=boundary
m.v1.write_json(m.Path(__file__).with_name('verification.json'),result)
print(json.dumps(result,indent=2))
