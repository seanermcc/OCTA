"""Lossless preview bundles avoid large exFAT allocation overhead for tiny files."""
from common import *
import base64,io
import zipfile

def pack_comparison_cache():
    p=HERE/'comparison/scan_cache.json';cache=read(p) if p.exists() else {}
    folder=(HERE/'comparison/scans').resolve();assert folder.is_relative_to(HERE/'comparison')
    originals={q.stem:read(q) for q in folder.glob('*.json')} if folder.exists() else {}
    if not originals:return
    for sid,data in originals.items():
        if sid not in cache:cache[sid]=data
        else:
            # All numerical comparison content must agree; metadata may have been refined.
            assert cache[sid]['pairwise']==data['pairwise']
    write(p,cache);saved=read(p)
    for sid,data in originals.items():
        assert saved[sid]['pairwise']==data['pairwise']
        (folder/f'{sid}.json').unlink()
    if not any(folder.iterdir()):folder.rmdir()
    write(HERE/'verification/comparison_cache_storage.json',dict(numerical_comparisons_unchanged=True,consolidated_scans=len(originals),cache=fingerprint(p)))

def pack_references():
    archive=HERE/'references.zip';tmp=archive.with_suffix('.tmp.zip');members={}
    if archive.exists():
        with zipfile.ZipFile(archive) as z:members={name:z.read(name) for name in z.namelist()}
    originals={}
    for p in (HERE/'references').glob('*.npz'):
        rp=HERE/'records'/f'{p.stem}.json'
        if rp.exists() and read(rp).get('status')=='completed':originals[p.name]=p.read_bytes()
    if not originals:return
    members.update(originals)
    with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_STORED) as z:
        for name,data in sorted(members.items()):z.writestr(name,data)
    with zipfile.ZipFile(tmp) as z:
        for name,data in members.items():assert z.read(name)==data
    tmp.replace(archive)
    for name,data in originals.items():
        p=(HERE/'references'/name).resolve();assert p.is_relative_to(HERE/'references')
        assert p.read_bytes()==data;p.unlink()
    write(HERE/'verification/reference_archive.json',dict(byte_exact=True,archive=fingerprint(archive),members={name:hashlib.sha256(data).hexdigest() for name,data in members.items()}))

def asset_bytes(im,name,format,assets,**options):
    buffer=io.BytesIO();im.save(buffer,format=format,**options)
    mime='image/jpeg' if format=='JPEG' else 'image/png'
    assets[name]='data:'+mime+';base64,'+base64.b64encode(buffer.getvalue()).decode('ascii')

def save_assets(sid,assets):
    p=dest(HERE/'comparison/assets'/f'{sid}.js')
    body='window.CNV_ASSETS=window.CNV_ASSETS||{};window.CNV_ASSETS['+json.dumps(sid)+']='+json.dumps(assets,separators=(',',':'))+';'
    tmp=p.with_suffix('.tmp');tmp.write_text(body,encoding='utf-8');tmp.replace(p)

def read_assets(sid):
    text=(HERE/'comparison/assets'/f'{sid}.js').read_text(encoding='utf-8')
    return json.loads(text.split(']=',1)[1].rstrip(';'))

def pack_existing_assets(sid):
    directory=(HERE/'comparison/assets'/sid).resolve()
    assert directory.is_relative_to(HERE/'comparison/assets')
    if not directory.exists():return 0
    originals={p.name:p.read_bytes() for p in directory.iterdir() if p.is_file() and p.suffix in ('.jpg','.png')}
    if not originals:return 0
    assets={name:'data:'+('image/jpeg' if name.endswith('.jpg') else 'image/png')+';base64,'+base64.b64encode(data).decode('ascii') for name,data in originals.items()}
    save_assets(sid,assets);recovered=read_assets(sid)
    for name,data in originals.items():assert base64.b64decode(recovered[name].split(',',1)[1])==data
    # Only regenerated preview media owned by this task is removed, after byte-exact verification.
    for name in originals:(directory/name).unlink()
    if not any(directory.iterdir()):directory.rmdir()
    return len(originals)

def compact_completed():
    from batch import KEYS
    checks=[]
    for rp in sorted((HERE/'records').glob('*.json')):
        rec=read(rp)
        if rec.get('status')!='completed':continue
        sid=rec['scan_id'];models={k:prediction_provenance(HERE/'predictions',k,sid) for k in KEYS}
        packed=HERE/'predictions/provenance'/f'{sid}.json'
        write(packed,dict(format='six-model-native-prediction-provenance',scan_id=sid,models=models))
        assert read(packed)['models']==models
        removed=0
        for key in KEYS:
            old=(HERE/'predictions'/key/f'{sid}.json').resolve()
            assert old.is_relative_to(HERE/'predictions')
            if old.exists():
                assert read(old)==models[key];old.unlink();removed+=1
        audit=(HERE/'annotation_audit'/f'{sid}.json').resolve()
        assert audit.is_relative_to(HERE/'annotation_audit')
        if audit.exists():assert read(audit)==rec['annotation_audit'];audit.unlink();removed+=1
        n=pack_existing_assets(sid)
        checks.append(dict(scan_id=sid,provenance_equal=True,removed_redundant_metadata_files=removed,preview_files_packed_byte_exact=n))
    write(HERE/'verification/storage_compaction.json',dict(lossless=True,prediction_arrays_modified=False,checks=checks))
    pack_references()
    pack_comparison_cache()
    print('Lossless storage compaction complete:',len(checks),'acquisitions',flush=True)

if __name__=='__main__':compact_completed()
