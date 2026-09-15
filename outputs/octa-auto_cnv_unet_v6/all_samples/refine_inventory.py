"""Document metadata/exposure distinctions without changing any model input."""
from batch import *

def run():
    m=read(HERE/'inventory.json');pilot={r['scan_id']:r for r in read(PILOT/'data/manifest.json')['scans']}
    notes=[]
    for r in m['scans']:
        record_path=HERE/'records'/f"{r['scan_id']}.json"
        record=read(record_path) if record_path.exists() else {}
        r['inference_status']=record.get('status','pending');r['reason']=record.get('reason','')
        source_folder=Path(r['source']).relative_to(ROOT.parent/'OCTA_RawData').parts[0]
        r['source_session_folder']=source_folder;r['source_folder_differs_from_index']=bool(r.get('session_folder') and r['session_folder']!=source_folder)
        if r['animal']=='TS336' and r['session_date']=='2026-07-28':
            r['metadata_note']='Index nominal label D56; current source folder nominal label D77. Indexed label retained for identity. Actual laser interval is unknown.'
            notes.append(dict(scan_id=r['scan_id'],note=r['metadata_note']))
        if r['scan_id'] in pilot:
            pr=pilot[r['scan_id']];known=pr['audit']['positive_pixels']+pr['audit']['negative_pixels']>0
            r['cnv_training_sample']=pr['split']=='train' and known
            r['cnv_scan_exposure']=('supervised training and normalization input' if known else 'training-visit allocation; unannotated, excluded from fitting and normalization') if pr['split']=='train' else 'validation checkpoint/threshold selection' if pr['split']=='validation' else 'development holdout evaluation'
        else:r['cnv_training_sample']=False;r['cnv_scan_exposure']='inference only; absent from original CNV pilot'
        r['cnv_normalization_source']=r['cnv_training_sample']
    write(HERE/'inventory.json',m);write(HERE/'verification/metadata_discrepancies.json',notes)
    # Early provenance dictionaries also fingerprinted references. They never
    # entered tensors; keep only actual automatic inputs in the input dictionary.
    for folder in ('records','predictions/provenance',*['predictions/'+key for key in KEYS]):
        for p in (HERE/folder).glob('*.json'):
            document=read(p);changed=False
            values=list(document['models'].values()) if folder=='predictions/provenance' else [document]
            for a in values:
                hashes=a.get('input_array_hashes',{})
                if any(k in hashes for k in ('target','known','instances')):
                    a['reference_array_hashes']={k:hashes.pop(k) for k in ('target','known','instances') if k in hashes}
                    a['reference_hash_note']='Separate evaluation references; never passed to tensor_inputs or the models.';changed=True
            if changed:write(p,document)
    status(m)

if __name__=='__main__':run()
