import UnityPy,tarfile,collections,json,warnings,time
from pathlib import Path
import argparse
p=argparse.ArgumentParser();p.add_argument("archive",type=Path);p.add_argument("--output",type=Path,default=Path("asset-index"));args=p.parse_args()
warnings.filterwarnings('ignore');UnityPy.config.FALLBACK_UNITY_VERSION='2022.3.20f1'
out=args.output;out.mkdir(parents=True,exist_ok=True);rows=[];errors=[]
with tarfile.open(args.archive) as tar:
 for number,m in enumerate(tar.getmembers()):
  if not m.isfile() or not m.name.endswith('.lpak'):continue
  b=tar.extractfile(m).read();starts=[];pos=0
  while True:
   pos=b.find(b'UnityFS\0',pos)
   if pos<0:break
   starts.append(pos);pos+=8
  for i,start in enumerate(starts):
   try:
    env=UnityPy.load(b[start:starts[i+1] if i+1<len(starts) else len(b)])
    for obj in env.objects:
     if obj.type.name not in ('Sprite','Texture2D'):continue
     d=obj.read();rows.append({'pack':m.name,'bundle':i,'path_id':obj.path_id,'type':obj.type.name,'name':d.m_Name,'width':getattr(d,'m_Width',None),'height':getattr(d,'m_Height',None)})
   except Exception as e:errors.append([m.name,i,str(e)[:180]])
  if number%100==0:print('packs',number,'images',len(rows),flush=True)
(out/'inventory.json').write_text(json.dumps(rows,ensure_ascii=False),encoding='utf8')
(out/'errors.json').write_text(json.dumps(errors,ensure_ascii=False),encoding='utf8')
print('finished',len(rows),'errors',len(errors),flush=True)
