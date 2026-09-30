"""Saved-model scalar adding-layer verification, separate from fitting."""
import math, json
from pathlib import Path
import numpy as np
from run import ROOT, predict, v1

out=ROOT/'target/measured-oils/parallel/physical'
artifact=json.loads((out/'frozen-models.json').read_text())
rows,c,r,original=v1.load_source(ROOT/'target/measured-oils/source/spectralDatasets.zip')
checks={}
for name,m in artifact['models'].items():
    actual,q,s=predict(c,np.array(m['pure']),np.array(m['u']))
    reference=np.zeros_like(actual)
    for i,recipe in enumerate(c):
        for band in range(31):
            sm=sum(float(recipe[j])*float(s[j,band]) for j in range(4))
            km=sum(float(recipe[j])*float(s[j,band])*float(q[j,band]) for j in range(4))
            a=1+km/sm; b=math.sqrt((km/sm)*(km/sm+2)); tau=sm*m['x']
            if b==0:
                black=tau/(1+tau); transmission=1/(1+tau)
            else:
                e=math.exp(-b*tau); den=a+b+(b-a)*e*e
                black=(1-e*e)/den; transmission=2*b*e/den
            reference[i,band]=black+transmission*transmission/(1-black)
    error=float(np.max(abs(actual-reference)))
    assert error<1e-11,error
    assert np.isfinite(actual).all() and (actual>=0).all() and (actual<=1).all()
    checks[name]=error
v1.write_json(Path(__file__).with_name('verification.json'),checks)
print(checks)
