"""Resumable native-grid export from the separate all-label checkpoint."""
import traceback
import numpy as np
import torch
from torch.nn import functional as F
from common import *
from network import Model,native_prob,resolved_masks

def main():
    inventory=read_json(HERE/'inventory.json');settings=read_json(HERE/'final_settings.json')
    modelpath=HERE/'models/all_eligible/best.pt'
    trained=read_json(HERE/'models/all_eligible/trained.json')
    modelhash=digest(modelpath);assert modelhash==trained['checkpoint_sha256']
    assert trained['protocol_sha256']==digest(HERE/'protocol.json')
    device='cuda' if torch.cuda.is_available() else 'cpu';torch.set_num_threads(4)
    model=Model().to(device);state=torch.load(modelpath,map_location=device,weights_only=False)
    model.load_state_dict(state['model']);model.eval()
    (HERE/'predictions').mkdir(exist_ok=True);(HERE/'records').mkdir(exist_ok=True)
    records=[]
    for i,row in enumerate(inventory):
        sid=row['scan_id'];recordpath=HERE/'records'/f'{sid}.json'
        if row['excluded']:
            record=dict(scan_id=sid,status='excluded',reason='Explicit poor-quality instruction; no segmentation, scoring or analysis',inventory_sha256=digest(HERE/'inventory.json'))
            write_json(recordpath,record);records.append(record);continue
        identity=dict(model_sha256=modelhash,final_settings_sha256=digest(HERE/'final_settings.json'),
                      projection_sha256=row['projection_sha256'],source_volume=row['source_volume'],source_size=row['source_size'],
                      source_mtime_ns=row['source_mtime_ns'],native_shape=row['native_shape'],axis_order=row['axis_order'],retina_band=row['retina_band'])
        pp=HERE/'predictions'/f'{sid}.npz'
        try:
            if recordpath.exists():
                rec=read_json(recordpath)
                if rec.get('status')=='complete' and rec.get('identity')==identity and pp.exists() and digest(pp)==rec['prediction_sha256']:
                    records.append(rec);continue
            assert digest(row['projection_path'])==row['projection_sha256'],'Projection changed since audit'
            stat=Path(row['source_volume']).stat()
            assert stat.st_size==row['source_size'] and stat.st_mtime_ns==row['source_mtime_ns'],'Source changed since audit'
            with np.load(row['projection_path'],allow_pickle=False) as z:im=normalized(z['structural_enface'])
            image=F.avg_pool2d(torch.from_numpy(im)[None,None],2).to(device)
            with torch.no_grad():raw=model(image).sigmoid()[0].cpu().numpy().astype(np.float16)
            prob=native_prob(raw,tuple(row['native_shape']));masks=resolved_masks(prob,settings['thresholds'],settings['min_onh_area'])
            save_npz(pp,probability_model_grid=raw,vessel_mask=masks[0],onh_mask=masks[1],
                scan_id=np.array([sid]),source_volume=np.array([row['source_volume']]),source_size=np.array([row['source_size']],np.int64),
                source_mtime_ns=np.array([row['source_mtime_ns']],np.int64),native_shape=np.array(row['native_shape']),axis_order=np.array([row['axis_order']]),
                retina_band=np.array(row['retina_band']),field_um=np.array([row['field_um']]),model_name=np.array(['all_eligible']),
                model_sha256=np.array([modelhash]),projection_sha256=np.array([row['projection_sha256']]),
                thresholds=np.array(settings['thresholds']),min_onh_area=np.array([settings['min_onh_area']]),
                interpolation=np.array(['sigmoid float16 256x256 -> bilinear float32 align_corners=False 512x512; threshold; ONH components; ONH precedence']),
                human_corrected=np.array([False]),independent_evaluation=np.array([False]))
            record=dict(scan_id=sid,status='complete',identity=identity,prediction_file=str(pp.relative_to(HERE)),prediction_sha256=digest(pp),
                        vessel_pixels=int(masks[0].sum()),onh_pixels=int(masks[1].sum()),overlap_pixels=int((masks[0]&masks[1]).sum()),
                        human_corrections_substituted=False,independent_evaluation=False)
        except Exception:
            record=dict(scan_id=sid,status='failed',identity=identity,error=traceback.format_exc())
        write_json(recordpath,record);records.append(record)
        if (i+1)%20==0 or record['status']=='failed':
            progress('inference',processed=i+1,total=len(inventory),complete=sum(r['status']=='complete' for r in records),excluded=sum(r['status']=='excluded' for r in records),failed=sum(r['status']=='failed' for r in records))
            if record['status']=='failed':print(record['error'],flush=True)
    summary=dict(completed_at=now(),total=len(inventory),complete=sum(r['status']=='complete' for r in records),
                 excluded=sum(r['status']=='excluded' for r in records),failed=sum(r['status']=='failed' for r in records),model_sha256=modelhash)
    summary['status']='complete' if summary['failed']==0 and summary['complete']+summary['excluded']==314 else 'incomplete'
    write_json(HERE/'inference_summary.json',summary);progress('inference_'+summary['status'],**{k:v for k,v in summary.items() if k!='status'})
    if summary['failed']:raise RuntimeError('Inference has failures; see records and resume after resolving them')

if __name__=='__main__':main()
