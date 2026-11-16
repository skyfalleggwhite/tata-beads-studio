import json
from pathlib import Path
import numpy as np
from PIL import Image

def shadow_triangles(vertices,uv,triangles,texture):
 """Locate separate low, flat, neutral atlas pieces; do not erase grey character pixels."""
 v=np.array(vertices,dtype=float)[:,:2];u=np.array(uv,dtype=float);t=np.array(triangles).reshape(-1,3)
 parent=list(range(len(v)))
 def find(a):
  while parent[a]!=a:parent[a]=parent[parent[a]];a=parent[a]
  return a
 for a,b,c in t:
  ra=find(int(a));parent[find(int(b))]=ra;parent[find(int(c))]=ra
 groups={}
 for i,tri in enumerate(t):groups.setdefault(find(int(tri[0])),[]).append(i)
 tex=np.array(texture.convert('RGBA'));candidates=[];used=v[np.unique(t)];height=np.ptp(used[:,1])
 for ids in groups.values():
  verts=np.unique(t[ids]);p=v[verts];extent=np.ptp(p,axis=0)
  if extent[0]<2.2*extent[1] or extent[0]<np.ptp(used[:,0])*.18 or p[:,1].mean()>used[:,1].min()+height*.6:continue
  coords=u[verts];lo=coords.min(axis=0);hi=coords.max(axis=0)
  x0=max(0,int(np.floor(lo[0]*texture.width)));x1=min(texture.width,int(np.ceil(hi[0]*texture.width)))
  y0=max(0,int(np.floor((1-hi[1])*texture.height)));y1=min(texture.height,int(np.ceil((1-lo[1])*texture.height)))
  patch=tex[y0:y1,x0:x1];pixels=patch[patch[:,:,3]>32]
  if len(pixels)<8:continue
  rgb=pixels[:,:3].astype(float)
  # A ground ellipse has nearly uniform neutral grey, unlike shaded fur or feet.
  if np.ptp(rgb.mean(axis=0))<20 and 15<rgb.mean()<100 and np.max(rgb.std(axis=0))<5:
   candidates.append((extent[0],ids))
 return np.array(max(candidates,key=lambda x:x[0])[1] if candidates else [],dtype=int)

def render(vertices,uv,triangles,texture,size=700,remove_shadow=False,shadow_texture=None):
 if remove_shadow:
  triangles=np.array(triangles).reshape(-1,3)
  removed=shadow_triangles(vertices,uv,triangles,shadow_texture if shadow_texture is not None else texture)
  triangles=np.delete(triangles,removed,axis=0)
 v=np.array(vertices,dtype=float)[:,:2];u=np.array(uv,dtype=float)
 lo=v.min(axis=0);hi=v.max(axis=0);scale=(size-40)/max(hi-lo)
 v=(v-lo)*scale+20;v[:,1]=(hi[1]-lo[1])*scale+40-v[:,1]
 width,height=np.ceil((hi-lo)*scale+40).astype(int)
 out=np.zeros((height,width,4),dtype=float);tex=np.array(texture.convert('RGBA'),dtype=float)/255
 for ids in np.array(triangles).reshape(-1,3):
  p=v[ids];t=u[ids]
  xmin,ymin=np.maximum(np.floor(p.min(axis=0)).astype(int),0);xmax,ymax=np.minimum(np.ceil(p.max(axis=0)).astype(int),[width-1,height-1])
  if xmax<xmin or ymax<ymin:continue
  den=(p[1,1]-p[2,1])*(p[0,0]-p[2,0])+(p[2,0]-p[1,0])*(p[0,1]-p[2,1])
  if abs(den)<1e-8:continue
  yy,xx=np.mgrid[ymin:ymax+1,xmin:xmax+1];xx=xx+.5;yy=yy+.5
  a=((p[1,1]-p[2,1])*(xx-p[2,0])+(p[2,0]-p[1,0])*(yy-p[2,1]))/den
  b=((p[2,1]-p[0,1])*(xx-p[2,0])+(p[0,0]-p[2,0])*(yy-p[2,1]))/den;c=1-a-b
  mask=(a>=-1e-7)&(b>=-1e-7)&(c>=-1e-7)
  tu=a*t[0,0]+b*t[1,0]+c*t[2,0];tv=a*t[0,1]+b*t[1,1]+c*t[2,1]
  tx=np.clip(np.rint(tu*texture.width-.5).astype(int),0,texture.width-1);ty=np.clip(np.rint((1-tv)*texture.height-.5).astype(int),0,texture.height-1)
  src=tex[ty,tx].copy();src[~mask]=0
  dst=out[ymin:ymax+1,xmin:xmax+1];alpha=src[:,:,3:4]
  dst[:,:,:3]=src[:,:,:3]*alpha+dst[:,:,:3]*(1-alpha);dst[:,:,3:4]=alpha+dst[:,:,3:4]*(1-alpha)
 alpha=out[:,:,3:4];out[:,:,:3]=np.divide(out[:,:,:3],alpha,out=np.zeros_like(out[:,:,:3]),where=alpha>0)
 return Image.fromarray(np.uint8(np.clip(out,0,1)*255),'RGBA')

if __name__=='__main__':
 root=Path('work/beads-full-probe');m=json.load(open(root/'mesh.json'))
 d=json.load(open(root/'-4368009602056746672_MonoBehaviour.json',encoding='utf8'))
 positions=np.fromfile(root/'pbch_gpu_spine_mantisp_position_all.raw',dtype='<f2').reshape(290,277,4)
 colors=np.array(Image.open(root/'pbch_gpu_spine_mantisp_color_all.png'))[::-1]
 for name,frame,group in [('idle',52,0),('cheer',0,1)]:
  vertices=positions[frame,:276,group*2:group*2+2].astype(float)
  triangles=np.array(d['triangleIndexList'][len(m['indices']):2*len(m['indices'])]).reshape(-1,3)
  im=render(vertices,m['uv'],triangles,Image.open(root/'Spine_MantisP.png'))
  box=im.getbbox();im.crop(box).save(root/('mantisp-'+name+'.png'))
