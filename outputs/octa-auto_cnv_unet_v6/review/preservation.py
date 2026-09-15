"""Hash immutable study assets; never modify them."""
from common import *

def paths():
    sources=set()
    for name in ('predictions','inputs','references','records','comparison','upstream_automatic'):
        sources.update(p for p in (HERE/name).rglob('*') if p.is_file())
    for name in ('references.zip','FINAL_VERIFIED.json','models.json','inventory.json'):
        sources.add(HERE/name)
    for name in ('data','evaluation','experiment_A','experiment_B','experiment_C','patterns'):
        sources.update(p for p in (REVIEW.parent/name).rglob('*') if p.is_file())
    for p in (HERE/'records').glob('*.json'):
        rec=read(p)
        for fp in rec.get('annotation_audit',{}).get('sources',[]):sources.add(Path(fp['path']))
    # Include original pilot review assets and active human records copied at migration.
    archive=REVIEW.parent/'old_review/20260914_231418'
    for rec in read(archive/'MANIFEST.json'):
        rel=rec['relative_path'].replace('\\','/')
        if rel.startswith('review/'):sources.add(REVIEW.parent/rel)
    return sorted(sources)

def run(check=False):
    p=REVIEW/'verification/protected_assets.json'
    if check:
        records=read(p)['files'];mismatch=[]
        for i,rec in enumerate(records):
            file=Path(rec['path'])
            if not file.exists() or file.stat().st_size!=rec['bytes'] or sha(file)!=rec['sha256']:mismatch.append(str(file))
            if i%500==0:print('Checked',i,flush=True)
        write(REVIEW/'verification/preservation_result.json',dict(passed=not mismatch,files_checked=len(records),changed=mismatch))
        assert not mismatch,mismatch
    else:
        records=[]
        for i,file in enumerate(paths()):
            records.append(dict(path=str(file),bytes=file.stat().st_size,sha256=sha(file)))
            if i%500==0:print('Fingerprinted',i,flush=True)
        write(p,dict(files=records,created=time.time()))
    print('Protected assets:',len(records),flush=True)

if __name__=='__main__':run('--check' in sys.argv)
