"""Copy the completed portable package to the user's explicitly selected empty folder."""
import hashlib
import json
from pathlib import Path
import shutil

root=Path(__file__).resolve().parents[1]
source=root/'outputs/portable_seg_20260923'
destination=Path('H:/octa/For_Segmentation').resolve()
assert destination==Path('H:/octa/For_Segmentation').resolve()
manifest_path=source/'PORTABLE_CACHE.json'
manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
if destination.exists() and any(destination.iterdir()):
    raise RuntimeError('Refusing to overwrite the nonempty destination')

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

# Refresh the implementation and verifier developed while the data copy ran.
review=Path('outputs/octa-seg/octa-seg_v3/review/code/octa_seg_v3')
for rel in (review/'portable.py',review/'gui.py',Path('code/verify_portable_seg_review.py')):
    shutil.copy2(root/rel,source/rel)
    manifest['files'][rel.as_posix()]=dict(sha256=digest(source/rel),bytes=(source/rel).stat().st_size)
manifest_path.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
destination.mkdir(parents=True,exist_ok=True)
files=[p for p in source.rglob('*') if p.is_file()]
total=sum(p.stat().st_size for p in files)
done=0; last=-1
for p in files:
    target=destination/p.relative_to(source)
    assert target.resolve().is_relative_to(destination)
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(p,target)
    if p.stat().st_size!=target.stat().st_size:raise RuntimeError('Copy size mismatch: '+str(target))
    done+=target.stat().st_size
    progress=int(100*done/total)//10
    if progress>last:
        print(f'Copied {done/1e9:.2f}/{total/1e9:.2f} GB',flush=True);last=progress
print(json.dumps(dict(destination=str(destination),files=len(files),GB=total/1e9)),flush=True)
