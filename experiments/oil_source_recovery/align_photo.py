"""Exploratory figure geometry and spectrum matching; no source mutation."""
import sys,hashlib
from pathlib import Path
import numpy as np
import colour
from PIL import Image
from scipy.ndimage import label, find_objects
from scipy.optimize import linear_sum_assignment

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'experiments/oil_public_data'))
from audit import load
labels,order,c,nom,nm,r,_=load()
HERE=Path(__file__).parent
photo_path=ROOT/'target/measured-oils/public-audit/sensors-21-02471-g002.jpg'
assert hashlib.sha256(photo_path.read_bytes()).hexdigest()=='0390ec2f94738a63ff21578a076feeefc78565a9620ee70c54e69cec7794469c'
im=np.array(Image.open(photo_path))
components,n=label(im.mean(2)<150)
points=[]
for i,box in enumerate(find_objects(components)):
    area=(components[box]==i+1).sum()
    if area<100:continue
    y,x=box
    points.append(((x.start+x.stop-1)/2,(y.start+y.stop-1)/2,x.start,y.start))
points.append((141,187,131,177)) # Sole neutral white patch, excluded by dark threshold.
positions=[]
for lo,hi in [(0,245),(245,493),(493,737)]:
    part=sorted([p for p in points if lo<p[0]<hi],key=lambda p:p[1])
    for i in range(0,len(part),6):positions.extend(sorted(part[i:i+6],key=lambda p:p[0]))
assert len(positions)==175
photo=np.array([np.median(im[round(y)-3:round(y)+4,round(x)-3:round(x)+4].reshape(-1,3),axis=0)/255
                for x,y,*_ in positions])
plin=colour.cctf_decoding(photo)
plab=colour.XYZ_to_Lab(colour.sRGB_to_XYZ(photo))
grid=np.arange(410,781,10)
a=colour.MSDS_CMFS['CIE 1931 2 Degree Standard Observer'].copy().align(colour.SpectralShape(410,780,10)).values
d=colour.SDS_ILLUMINANTS['D65'].copy().align(colour.SpectralShape(410,780,10)).values
rs=np.array([np.interp(grid,nm,x) for x in r])
lin=np.clip(colour.XYZ_to_sRGB(rs@(a*d[:,None])/sum(a[:,1]*d),apply_cctf_encoding=False),1e-8,None)

if __name__=='__main__':
    q=np.log(plin[0]/plin[33])/np.log(lin[0]/lin[31])
    transformed=plin[33]*(lin/lin[31])**q
    lab=colour.XYZ_to_Lab(colour.RGB_to_XYZ(transformed,colour.RGB_COLOURSPACES['sRGB']))
    cost=np.linalg.norm(plab[:,None]-lab[None],axis=2)
    for b,e in [(0,60),(60,120),(120,175)]:cost[b:e,:b]=cost[b:e,e:]=1e6
    ii,p=linear_sum_assignment(cost)
    print('mean cost',cost[ii,p].mean(),'pures',p[[labels.index(x) for x in order]])
    for i in range(175):print(i,labels[i],p[i],round(cost[i,p[i]],2))
    np.savez(HERE/'photo-geometric-match.npz',cost=cost,map=p,positions=positions,photo=photo,lin=lin,lab=lab,photo_lab=plab)
