"""Verify upstream model artifacts independently of the frozen selected masks."""
from .inputs import MODEL
from octa_reg_v2.run import read,write,sha

def verify_model_sources(root,manifest):
    cases={r['scan_id']:r for r in read(MODEL/'gallery/data.json')['cases']};hashes={};used=[]
    for chosen in manifest['cnvs']:
        source=chosen['source']
        if source not in ('confirmed_m2','confirmed_m3','automatic_m3'):continue
        model='v9_m2' if source=='confirmed_m2' else 'v9_m3'
        statuses=[p for p in cases[chosen['scan_id']]['status'] if p['model']==model]
        if len(statuses)!=1:raise ValueError('Expected one versioned prediction per scan/model')
        for key in ('prediction','checkpoint'):
            fp=statuses[0][key];path=fp['path']
            if path not in hashes:hashes[path]=sha(path)
            if hashes[path]!=fp['sha256']:raise ValueError('Model artifact changed: '+path)
        used.append(dict(scan_id=chosen['scan_id'],model=model))
    write(root/'CNV_PROVENANCE_AUDIT.json',dict(status='passed',selected_model_fields=used,source_hashes=hashes,
        policy='Selected mask bytes verified against version-bound review contract; upstream predictions and checkpoints verified against gallery fingerprints.'))
    return hashes
