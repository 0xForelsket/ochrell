"""Holdout blue/yellow family; independent seed, no external mixing targets."""
import sys,colorsys,subprocess,io
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from model import ROOT
import numpy as np
rng=np.random.default_rng(20261001);n=2048
ys=np.array([colorsys.hsv_to_rgb(rng.uniform(45,75)/360,rng.uniform(.6,.95),rng.uniform(.5,1)) for _ in range(n)])
bs=np.array([colorsys.hsv_to_rgb(rng.uniform(220,255)/360,rng.uniform(.6,.95),rng.uniform(.2,1)) for _ in range(n)])
x=np.c_[ys,bs,np.full(n,.5)];buf=io.StringIO();np.savetxt(buf,x,delimiter=',',fmt='%.12e')
out=ROOT/'results/revision';(out/'holdout_inputs.csv').write_text('ar,ag,ab,br,bg,bb,t\n'+buf.getvalue())
p=subprocess.run([str(ROOT/'target/release/examples/sample_pairs')],input=buf.getvalue(),text=True,capture_output=True,check=True)
(out/'holdout_outputs.csv').write_text(p.stdout)
