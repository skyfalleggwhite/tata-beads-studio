import json,argparse
from pathlib import Path
from PIL import Image
p=argparse.ArgumentParser();p.add_argument('site',type=Path,nargs='?',default=Path(__file__).resolve().parents[1]);a=p.parse_args()
rows=json.loads((a.site/'gallery.json').read_text(encoding='utf8'));seen=set()
for r in rows:
 assert r['name'].lower() not in seen, 'Duplicate: '+r['name'];seen.add(r['name'].lower())
 with Image.open(a.site/'images'/r['file']) as im:
  assert im.size==(r['width'],r['height']), 'Dimensions: '+r['name'];im.verify()
 if 'evolution' in r:assert r['grade']=={1:'一阶',2:'二阶',3:'三阶',4:'四阶'}[r['evolution']]
print('Verified',len(rows),'unique images')
