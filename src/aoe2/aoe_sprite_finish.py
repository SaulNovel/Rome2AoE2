"""Experimental material-aware 2D finishing for Rome2AoE2 sprites.

This module is deliberately independent of Blender and SLD authoring.  It uses
NumPy for OKLab/color operations and uses OpenCV for edge-aware detail when the
project-local optional wheel is available; a deterministic NumPy/Pillow fallback
keeps every other experiment reproducible when OpenCV cannot be imported.
"""
from __future__ import annotations
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];DEPS=ROOT/"build/python-deps/sld-authoring"
if DEPS.is_dir():sys.path.insert(0,str(DEPS))
import numpy as np
from PIL import Image,ImageFilter
try:
 import cv2
except ImportError:cv2=None

PALETTE={"cloth":(255,0,0),"skin":(0,255,0),"bronze":(0,0,255),"iron/steel":(255,255,0),"shield body":(255,0,255),"shield metal":(0,255,255),"leather":(255,64,0),"wood":(64,255,0),"other":(64,64,64)}

def rgba(image):return np.asarray(image.convert("RGBA"),dtype=np.float32)/255
def srgb_linear(x):return np.where(x<=.04045,x/12.92,((x+.055)/1.055)**2.4)
def linear_srgb(x):return np.where(x<=.0031308,12.92*x,1.055*np.maximum(x,0)**(1/2.4)-.055)
def rgb_oklab(rgb):
 x=srgb_linear(np.clip(rgb,0,1));l=.4122214708*x[...,0]+.5363325363*x[...,1]+.0514459929*x[...,2];m=.2119034982*x[...,0]+.6806995451*x[...,1]+.1073969566*x[...,2];s=.0883024619*x[...,0]+.2817188376*x[...,1]+.6299787005*x[...,2];l,m,s=np.cbrt(l),np.cbrt(m),np.cbrt(s)
 return np.stack((.2104542553*l+.793617785*m-.0040720468*s,1.9779984951*l-2.428592205*m+.4505937099*s,.0259040371*l+.7827717662*m-.808675766*s),-1)
def oklab_rgb(lab):
 l=lab[...,0]+.3963377774*lab[...,1]+.2158037573*lab[...,2];m=lab[...,0]-.1055613458*lab[...,1]-.0638541728*lab[...,2];s=lab[...,0]-.0894841775*lab[...,1]-1.291485548*lab[...,2];l,m,s=l**3,m**3,s**3
 rgb=np.stack((4.0767416621*l-3.3077115913*m+.2309699292*s,-1.2684380046*l+2.6097574011*m-.3413193965*s,-.0041960863*l-.7034186147*m+1.707614701*s),-1)
 return np.clip(linear_srgb(rgb),0,1)
def image(array,alpha):
 q=np.dstack((np.clip(array,0,1),np.clip(alpha,0,1)));return Image.fromarray(np.round(q*255).astype(np.uint8),"RGBA")

def semantic_masks(id_image,active=None):
 """Decode the supersampled emission ID pass; AA comes from its alpha."""
 a=rgba(id_image);rgb=a[...,:3];alpha=a[...,3];colors=np.asarray(list(PALETTE.values()),np.float32)/255;dist=((rgb[...,None,:]-colors[None,None,:,:])**2).sum(-1);index=dist.argmin(-1);names=list(PALETTE)
 out={}
 for i,name in enumerate(names):
  # A semantic class is present only if the ID render contains an opaque pixel
  # close to its exact emission color. This prevents AA mixtures at boundaries
  # from fabricating unsupported classes such as Hastati shield-metal/wood.
  present=(active is None or name in active) and np.any((dist[...,i]<.002)&(alpha>.95));out[name]=((index==i).astype(np.float32)*alpha) if present else np.zeros_like(alpha)
 return out

def tone_reference(source,target_median=.42,dark=.24):
 lab=rgb_oklab(source[...,:3]);active=source[...,3]>.03;vals=lab[...,0][active];p=np.quantile(vals,[0,.1,.25,.5,.75,.95,1]);y=np.array([0,.09,dark,target_median,min(.76,target_median+.22),.86,.93]);lab[...,0]=np.interp(lab[...,0],p,y);return lab
def chroma_preserve(source,toned_lab,masks,cloth_scale=1.0,selective=False):
 src=rgb_oklab(source[...,:3]);out=toned_lab.copy();out[...,1:]=src[...,1:]
 if selective:
  cloth=masks["cloth"][...,None];out[...,1:]=out[...,1:]*(1-cloth)+src[...,1:]*(1.15*cloth)
 else:
  cloth=masks["cloth"][...,None];out[...,1:]=out[...,1:]*(1-cloth)+src[...,1:]*(cloth_scale*cloth)
 return out
def boundary_finish(lab,masks,amount=.012):
 # One source-pixel material-boundary band; signs follow local class mean, not
 # a universal black outline.  At final x2 this becomes a bounded 1–2px cue.
 labels=np.argmax(np.stack(list(masks.values()),-1),-1).astype(np.uint8);im=Image.fromarray(labels);mx=np.asarray(im.filter(ImageFilter.MaxFilter(3)));mn=np.asarray(im.filter(ImageFilter.MinFilter(3)));edge=(mx!=mn)&(np.max(np.stack(list(masks.values()),-1),-1)>.2)
 local=np.asarray(Image.fromarray(np.round(lab[...,0]*255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2)),np.float32)/255;sign=np.sign(lab[...,0]-local);out=lab.copy();out[...,0]=np.clip(out[...,0]+edge*sign*amount,0,1);return out,edge.astype(np.float32)
def luminance_detail(lab,mode):
 if mode=="D00":return lab
 L=lab[...,0];pil=Image.fromarray(np.round(L*255).astype(np.uint8));radius=2;blur=np.asarray(pil.filter(ImageFilter.GaussianBlur(radius)),np.float32)/255
 if mode in ("D01","D02"):amount=.18 if mode=="D01" else .30;new=L+(L-blur)*amount
 elif mode=="D03" and cv2 is not None:
  base=cv2.bilateralFilter(L.astype(np.float32),7,.08,5);new=L+(L-base)*.22
 elif mode=="D03":
  # Edge-preserving fallback: suppress detail where the local gradient is high.
  gx=np.gradient(L,axis=1);gy=np.gradient(L,axis=0);weight=np.exp(-18*np.hypot(gx,gy));new=L+(L-blur)*.22*weight
 elif mode=="D04":new=L+(L-blur)*.16
 else:raise ValueError(mode)
 out=lab.copy();out[...,0]=np.clip(new,0,1);return out
def resize_mask(mask,size,filter=Image.Resampling.LANCZOS):return np.asarray(Image.fromarray(np.round(mask*255).astype(np.uint8)).resize(size,filter),np.float32)/255
def finish(master,id_image,cloth_scale=1.0,selective=False,boundary=False,detail="D00",active=None):
 src=rgba(master);masks=semantic_masks(id_image,active)
 if master.size!=id_image.size:masks={k:resize_mask(v,master.size) for k,v in masks.items()}
 lab=tone_reference(src);lab=chroma_preserve(src,lab,masks,cloth_scale,selective);edge=np.zeros(src.shape[:2],np.float32)
 if boundary:lab,edge=boundary_finish(lab,masks)
 lab=luminance_detail(lab,detail);return image(oklab_rgb(lab),src[...,3]),masks,edge,{"opencv_available":cv2 is not None,"detail_backend":"opencv-bilateral" if detail=="D03" and cv2 is not None else "numpy-pillow"}

def semantic_hue_restore(graded,semantic_reference,cloth_mask,strength,chroma_scale=1.0):
 """Keep graded OKLab L/detail and blend only a/b toward source semantics."""
 g=rgba(graded);r=rgba(semantic_reference);gl=rgb_oklab(g[...,:3]);rl=rgb_oklab(r[...,:3]);target=rl[...,1:]*chroma_scale
 # Strength controls semantic hue restoration; continuous material coverage is
 # composited exactly once. This preserves anti-aliased edges without squaring
 # their coverage and leaves every non-cloth pixel byte-for-byte unchanged.
 restored=gl.copy();restored[...,1:]=gl[...,1:]*(1-strength)+target*strength;restored=oklab_rgb(restored)
 coverage=np.clip(cloth_mask,0,1)[...,None];out=g[...,:3]*(1-coverage)+restored*coverage
 return image(out,g[...,3])
