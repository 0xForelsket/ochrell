from explore import *
import csv
basis=fit_basis()
pairs=PAIRS+[('official_default',[0,33,133],[252,210,0])]
def optical(r,beta):
 q=(1-r)**2/(2*r);y=r@m.xyz[:,1];sn=2*y/(1+y*y)
 s=(1+q)**(-beta)*sn**(1-beta)
 return q*s,s
def candidate(a,b,t,beta,white):
 ra,ea=encode(a,basis);rb,eb=encode(b,basis)
 ka,sa=optical(ra,beta);kb,sb=optical(rb,beta)
 aa=1+(white-1)*min(linear(a));bb=1+(white-1)*min(linear(b))
 ka*=aa;sa*=aa;kb*=bb;sb*=bb
 q=((1-t)*ka+t*kb)/((1-t)*sa+t*sb);r=1/(1+q+np.sqrt(q*(q+2)))
 return srgb(gamut(r@A.T+(1-t)*ea+t*eb))
def run():
 rows=[]
 for beta in [0,.125,.25,.5,.75,1]:
  for white in [1,2,4]:
   for name,a,b in pairs:
    x=candidate(np.array(a)/255,np.array(b)/255,.5,beta,white)
    rows.append({'beta':beta,'white':white,'pair':name,'r':x[0],'g':x[1],'b':x[2]})
 with (ROOT/'results/revision/optics_sweep.csv').open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 for beta in [0,.125,.25,.5,.75,1]:
  print('beta',beta)
  for r in rows:
   if r['beta']==beta and r['white']==2:
    print(r['pair'],np.rint(np.array([r[x] for x in 'rgb'])*255).astype(int).tolist())

if __name__=="__main__":run()
