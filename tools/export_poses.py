import sys,json,tarfile,warnings,re,collections
from pathlib import Path
import argparse
import UnityPy,numpy as np
from PIL import Image
from UnityPy.helpers.MeshHelper import MeshHandler
from beads_render_mesh import render
warnings.filterwarnings('ignore');UnityPy.config.FALLBACK_UNITY_VERSION='2022.3.20f1'
parser=argparse.ArgumentParser(description='Restore static Idle poses from locally owned Unity lpak archives.')
parser.add_argument('archive',type=Path);parser.add_argument('inventory',type=Path)
parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parents[1])
parser.add_argument('--profiles',type=Path,default=Path(__file__).with_name('profiles.json'))
parser.add_argument('--only',nargs='*',default=[])
args=parser.parse_args();root=args.output;root.mkdir(parents=True,exist_ok=True);(root/'images').mkdir(exist_ok=True)
rows=json.loads(args.inventory.read_text(encoding='utf8'))
profiles=json.loads(args.profiles.read_text(encoding='utf8'))
if args.only:profiles=[p for p in profiles if p['name'] in args.only]
textures={r['name'].lower():r for r in rows if r['type']=='Texture2D'}
selected=[]
for profile in profiles:
 source=profile['name'].removeprefix('stinky_full_').removeprefix('full_')
 record=textures.get('spine_'+source.lower())
 if record:selected.append((record,profile))
manifest=json.loads((root/'gallery.json').read_text(encoding='utf8')) if (root/'gallery.json').exists() else []
selected_names={p['name'] for _,p in selected};manifest=[r for r in manifest if r['name'] not in selected_names]
errors=[{'model':p['name'],'error':'Texture not present in inventory'} for p in profiles if p['name'] not in selected_names];success=[];cache=collections.OrderedDict()
with tarfile.open(args.archive) as tar:
 for ri,(r,profile) in enumerate(selected):
  model=re.split('_color_',r['name'][6:],flags=re.I)[0];safe=profile['name']
  try:
   posrow=next(x for x in rows if x['name'].lower()=='pbch_gpu_spine_'+model.lower()+'_position_all')
   objects={};envs=[]
   for pack in [posrow['pack']]:
    if pack in cache:
     objects,envs=cache[pack];cache.move_to_end(pack);continue
    b=tar.extractfile(pack).read();starts=[];pos=0
    while True:
     pos=b.find(b'UnityFS\0',pos)
     if pos<0:break
     starts.append(pos);pos+=8
    for i,s in enumerate(starts):
     e=UnityPy.load(b[s:starts[i+1] if i+1<len(starts) else len(b)]);envs.append(e)
     for o in e.objects:objects[o.path_id]=o
    cache[pack]=(objects,envs)
    if len(cache)>2:cache.popitem(last=False)
   controls=[]
   for o in objects.values():
    if o.type.name=='MonoBehaviour':
     d=o.read_typetree()
     if d.get('gpuAnimData') and d.get('MeshHashList'):
      go=objects[d['m_GameObject']['m_PathID']].read().m_Name.lower()
      if go=='pbch_gpu_spine_'+model.lower() or go.startswith('pbch_gpu_spine_'+model.lower()+'_'):controls.append(d)
   control=next((d for d in controls if 'color' not in objects[d['m_GameObject']['m_PathID']].read().m_Name.lower()),controls[0])
   anim=next(a for a in control['gpuAnimData'] if a['name'].lower()=='idle')
   meshid=next(x['Mesh']['m_PathID'] for x in control['MeshHashList'] if x['Hash']==anim['meshHash'])
   mh=MeshHandler(objects[meshid].read());mh.process()
   material=None
   for o in objects.values():
    if o.type.name!='Material':continue
    d=o.read_typetree();tex=dict(d['m_SavedProperties']['m_TexEnvs'])
    if '_VertexPositionTexture' in tex:
     position_obj=objects.get(tex['_VertexPositionTexture']['m_Texture']['m_PathID'])
     if position_obj is not None and position_obj.read().m_Name.lower()=='pbch_gpu_spine_'+model.lower()+'_position_all':material=tex;break
   if material is None:raise ValueError('matching VAT material not found')
   pt=objects[material['_VertexPositionTexture']['m_Texture']['m_PathID']].read()
   if pt.m_TextureFormat!=17:raise ValueError('unsupported VAT format '+str(pt.m_TextureFormat))
   p=np.frombuffer(pt.get_image_data(),dtype='<f2').reshape(pt.m_Height,pt.m_Width,4)
   group=0 if anim['isTextureGroup0'] else 1
   vertex_ids=np.rint(np.array(mh.m_UV1)[:,0]).astype(int)
   invalid_vertex_ids=np.flatnonzero((vertex_ids<0)|(vertex_ids>=p.shape[1]));safe_vertex_ids=vertex_ids.copy();safe_vertex_ids[invalid_vertex_ids]=0
   vertices=p[anim['startFrame'],safe_vertex_ids,group*2:group*2+2].astype(float)
   count=len(mh.m_IndexBuffer);offset=0
   for ti in range(anim['trianglesIndex']):
    prior=next(a for a in control['gpuAnimData'] if a['trianglesIndex']==ti)
    priorid=next(x['Mesh']['m_PathID'] for x in control['MeshHashList'] if x['Hash']==prior['meshHash'])
    ph=MeshHandler(objects[priorid].read());ph.process();offset+=len(ph.m_IndexBuffer)
   indices=control['triangleIndexList'][offset:offset+count]
   if set(invalid_vertex_ids)&set(indices):raise ValueError('Active vertex outside animation texture')
   if len(indices)!=count:raise ValueError('triangle segment incomplete')
   texture_obj=objects.get(r['path_id'])
   if texture_obj is None:
    data=tar.extractfile(r['pack']).read();bounds=[];at=0
    while True:
     at=data.find(b'UnityFS\0',at)
     if at<0:break
     bounds.append(at);at+=8
    bi=r['bundle'];extra=UnityPy.load(data[bounds[bi]:bounds[bi+1] if bi+1<len(bounds) else len(data)]);envs.append(extra)
    texture_obj=next(o for o in extra.objects if o.path_id==r['path_id'])
   texture=texture_obj.read().image
   # Use the normal atlas to detect shadow geometry, since variant atlases recolour it.
   normal_texture=next((o.read().image for o in objects.values() if o.type.name=='Texture2D' and o.read().m_Name.lower()=='spine_'+model.lower()),texture)
   im=render(vertices,mh.m_UV0,indices,texture,size=600,remove_shadow=True,shadow_texture=normal_texture)
   # Remove very faint raster residue separated from the visible character, not grey body pixels.
   alpha=np.array(im)[:,:,3];strong=np.flatnonzero(alpha.max(axis=1)>8)
   if len(strong):
    weak=np.flatnonzero((alpha.max(axis=1)>0)&((np.arange(im.height)<strong[0]-40)|(np.arange(im.height)>strong[-1]+40)))
    for y in weak:
     if alpha[y].max()<=8:im.paste((0,0,0,0),(0,int(y),im.width,int(y)+1))
   box=im.getbbox()
   if box is None:raise ValueError('empty pose')
   im=im.crop(box);im.save(root/'images'/(safe+'.png'))
   row={**profile,'name':safe,'file':safe+'.png','width':im.width,'height':im.height,'group':'完整姿势','pack':r['pack'],'model':model,'pose':'Idle','source':'客户端预烘焙动画'}
   manifest.append(row);success.append(row)
  except Exception as e:
   errors.append({'model':model,'error':str(e)[:200]})
   if ri<5:print('error',model,str(e)[:100],flush=True)

  if ri%5==0:print('processed',ri+1,'/',len(selected),'model',model,'exported',len(success),'errors',len(errors),flush=True)
manifest.sort(key=lambda r:(not r['name'].startswith('full_'),r['name']))
(root/'gallery.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
(root/'extraction-report.json').write_text(json.dumps({'success':success,'errors':errors},ensure_ascii=False,indent=2),encoding='utf8')
print('done',len(success),'errors',len(errors),flush=True)
