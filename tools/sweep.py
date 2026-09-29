from model import *
import csv
(ROOT/CFG['paths']['results']/'exploration').mkdir(parents=True,exist_ok=True)
rows=[]
for ye in [490,510,530,550]:
 for be in [490,510,530]:
  CFG['model']['yellow_edge_nm']=ye;CFG['model']['blue_edge_nm']=be
  m=Model();a=np.array([255,220,0])/255;b=np.array([20,70,255])/255
  w,e=m.encode(a);v,f=m.encode(b);c=m.mix(a,b,.5)
  rows.append([ye,be,*np.rint(srgb(c)*255).astype(int),100*np.linalg.norm(e),100*np.linalg.norm(f)])
print(rows)
with open(ROOT/CFG['paths']['results']/'exploration/edge_sweep.csv','w') as f:
 writer=csv.writer(f);writer.writerow(['yellow_edge_nm','blue_edge_nm','r','g','b','yellow_residual_linear100','blue_residual_linear100']);writer.writerows(rows)
