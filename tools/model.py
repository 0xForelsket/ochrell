"""Independent f64 model and generation utilities. No external mixing code."""
from pathlib import Path
import tomllib
import numpy as np
from scipy.optimize import minimize, lsq_linear
ROOT=Path(__file__).resolve().parents[1]
CFG=tomllib.loads((ROOT/'config.toml').read_text())
M=np.array([[3.2409699419045226,-1.537383177570094,-.4986107602930034],[-.9692436362808796,1.8759675015077202,.04155505740717559],[.05563007969699366,-.20397695888897652,1.0569715142428786]])
LMS=np.array([[.4122214708,.5363325363,.0514459929],[.2119034982,.6806995451,.1073969566],[.0883024619,.2817188376,.6299787005]])
LAB=np.array([[.2104542553,.7936177850,-.0040720468],[1.9779984951,-2.4285922050,.4505937099],[.0259040371,.7827717662,-.8086757660]])
def linear(x):
 x=np.asarray(x);return np.where(x<=.04045,x/12.92,((np.maximum(x,0)+.055)/1.055)**2.4)
def srgb(x):
 x=np.asarray(x);return np.where(x<=.0031308,12.92*x,1.055*np.maximum(x,0)**(1/2.4)-.055)
def lab(x): return np.cbrt(np.asarray(x)@LMS.T)@LAB.T
def unlab(x): return (np.asarray(x)@np.linalg.inv(LAB).T)**3@np.linalg.inv(LMS).T
def gamut(x):
 # Continuous linear-RGB neutral-axis compression; preserves luminance where in range.
 x=np.asarray(x);y=np.clip(x@np.array([.2126,.7152,.0722]),0,1)
 d=x-y[...,None];den=np.where(np.abs(d)>1e-30,d,1)
 lim=np.where(d>0,(1-y[...,None])/den,np.where(d<0,-y[...,None]/den,1))
 a=np.minimum(1,np.min(lim,axis=-1));return np.clip(y[...,None]+a[...,None]*d,0,1)
def prior(rgb):
 r,g,b=rgb;lo=min(rgb);hi=max(rgb)
 # W,C,M,Y,R,G,B,K. Smits-like algebra, not borrowed spectra.
 w=np.zeros(8);w[0]=lo;w[7]=1-hi
 if r<=g and r<=b: w[1]=min(g,b)-r;w[5 if g>b else 6]=abs(g-b)
 elif g<=r and g<=b: w[2]=min(r,b)-g;w[4 if r>b else 6]=abs(r-b)
 else: w[3]=min(r,g)-b;w[4 if r>g else 5]=abs(r-g)
 return w
class Model:
 def __init__(self,step=5,active=None,white_s=None):
  cfg=CFG['model'];d=np.loadtxt(ROOT/'data/cie_380_780_1nm.csv',delimiter=',',skiprows=1)[::step];self.nm=d[:,0]
  self.xyz=d[:,1:4]*d[:,4,None];self.xyz[[0,-1]]*=.5;self.xyz/=self.xyz[:,1].sum()
  self.rgb=self.xyz@M.T
  # Normalize neutral reflector to exactly linear [1,1,1]. Not exact standard colorimetry.
  self.rgb/=self.rgb.sum(axis=0)
  sigmoid=lambda edge:1/(1+np.exp(-(self.nm-edge)/cfg['transition_nm']))
  blue=1-sigmoid(cfg['blue_edge_nm']);red=sigmoid(cfg['red_edge_nm']);yellow=sigmoid(cfg['yellow_edge_nm']);cyan=1-red;green=yellow*cyan;magenta=1-green
  bands=np.array([np.ones(len(d)),cyan,magenta,yellow,red,green,blue,np.zeros(len(d))])
  self.r=cfg['reflectance_floor']+(cfg['reflectance_ceiling']-cfg['reflectance_floor'])*bands
  self.s=np.array([cfg['white_scattering'] if white_s is None else white_s]+[cfg['chromatic_scattering']]*6+[cfg['black_scattering']])
  self.k=(1-self.r)**2/(2*self.r)*self.s[:,None]
  self.active=np.arange(8) if active is None else np.array(active)
 def forward(self,w):
  q=(np.asarray(w)@self.k)/(np.asarray(w)@self.s)[...,None];r=1/(1+q+np.sqrt(q*(q+2)));return r@self.rgb
 def invert(self,c):
  target=lab(linear(c));p=prior(c);p[np.setdiff1d(np.arange(8),self.active)]=0
  if p.sum()==0:p[self.active]=1/len(self.active)
  p/=p.sum();reg=CFG['model']['regularization']
  def obj(x):
   w=np.zeros(8);w[self.active]=x
   return np.sum((lab(self.forward(w))-target)**2)+reg*np.sum((w-p)**2)
  sol=minimize(obj,p[self.active],method='SLSQP',bounds=[(0,1)]*len(self.active),constraints={'type':'eq','fun':lambda x:x.sum()-1},options={'ftol':1e-10,'maxiter':150})
  w=np.zeros(8);w[self.active]=sol.x;return w/w.sum()
 def encode(self,c):
  w=self.invert(c);return w,linear(c)-self.forward(w)
 def mix(self,a,b,t,residual=True):
  wa,ea=self.encode(a);wb,eb=self.encode(b);x=self.forward((1-t)*wa+t*wb)
  return gamut(x+(1-t)*ea+t*eb) if residual else gamut(x)
 def reconstruct(self,c):
  # Bounded Tikhonov first-difference smoothing, A path (not Burns' exact algorithm).
  n=len(self.nm);D=np.diff(np.eye(n),axis=0)
  A=np.vstack([self.rgb.T,.01*D]);b=np.r_[linear(c),np.zeros(n-1)]
  return lsq_linear(A,b,bounds=(.001,.999),tol=1e-10).x
 def mix_spectral(self,a,b,t):
  ra=self.reconstruct(a);rb=self.reconstruct(b)
  q=(1-t)*(1-ra)**2/(2*ra)+t*(1-rb)**2/(2*rb)
  return gamut((1/(1+q+np.sqrt(q*(q+2))))@self.rgb)
PAIRS=[('yellow_blue',[255,220,0],[20,70,255]),('red_blue',[230,30,40],[20,70,255]),('red_yellow',[230,30,40],[255,220,0]),('cyan_magenta',[0,190,210],[220,0,160]),('magenta_yellow',[220,0,160],[255,220,0]),('black_white',[0,0,0],[255,255,255]),('red_green',[230,30,40],[30,170,55]),('blue_orange',[20,70,255],[255,130,0]),('yellow_purple',[255,220,0],[140,30,180]),('blue_white',[20,70,255],[255,255,255]),('red_white',[230,30,40],[255,255,255]),('extreme_yellow_blue',[255,255,0],[0,0,255])]
