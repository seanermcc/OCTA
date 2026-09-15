"""Two prespecified extra seeds for all three matched experiments; no architecture tuning."""
from common import *
from train import run as train,load_scans,configure,CHANNELS
from model import UNet,infer
from metrics import PROTOCOL,score,aggregate,components
import torch

def run():
    write(HERE/'evaluation/seed_protocol.json',dict(seeds=[267,268,269],experiments=['A','B','C'],
        scope='Repeat all matched comparisons with unchanged recipe; checkpoints and thresholds remain validation-only',
        no_holdout_hyperparameter_tuning=True))
    results=[];details={}
    for seed in [268,269]:
        for ex in 'ABC':
            train(ex,dict(seed=seed))
            out=HERE/f'experiment_{ex}'/f'seed_{seed}';configure(seed);device=torch.device('cuda' if torch.cuda.is_available() else 'cpu')
            ck=torch.load(out/'best.pt',map_location=device,weights_only=False);net=UNet(CHANNELS[ex]).to(device);net.load_state_dict(ck['model'])
            scans=load_scans(ex);predictions={}
            for d in scans:
                sid=d['record']['scan_id'];p=infer(net,d['input'],device,4);predictions[sid]=p
                save(out/'scores'/f'{sid}.npz',score=p,scan_id=np.array(sid),axis_order=np.array('B-scan,A-line'),checkpoint_sha256=np.array(sha(out/'best.pt')))
            sweep=[]
            for threshold in PROTOCOL['threshold_grid']:
                tp=pred=truth=0
                for d in scans:
                    if d['record']['split']!='validation':continue
                    p=predictions[d['record']['scan_id']]>=threshold;k=d['known'];t=d['target']
                    tp+=int((p&t&k).sum());pred+=int((p&k).sum());truth+=int(t.sum())
                sweep.append(dict(threshold=threshold,known_dice=2*tp/(pred+truth)))
            selected=max(sweep,key=lambda r:(r['known_dice'],r['threshold']));th=selected['threshold']
            write(out/'threshold.json',dict(selected=selected,sweep=sweep,source='D49 only'))
            rows=[];det={}
            for d in scans:
                r=d['record'];sid=r['scan_id'];mask=predictions[sid]>=th;labels,_=components(mask)
                save(out/'predictions'/f'{sid}.npz',mask=mask,candidate_labels=labels,threshold=np.array(th),scan_id=np.array(sid))
                write(out/'predictions'/f'{sid}.json',dict(scan_id=sid,human_reviewed=False,axis_order='B-scan,A-line',
                    candidates=[dict(id=int(i),runs=encode(labels==i)) for i in np.unique(labels) if i>0]))
                for cutoff in PROTOCOL['iou_thresholds']:
                    v,detail=score(mask,d,r['audit']['complete'],cutoff)
                    rows.append(dict(seed=seed,model=ex,scan_id=sid,split=r['split'],eye=r['eye'],visit=r['day_label'],complete=r['audit']['complete'],iou_cutoff=cutoff,threshold=th,**v))
                    if cutoff==.1:det[sid]=detail
            csv_write(out/'evaluation.csv',rows);write(out/'evaluation_details.json',det)
            results.extend(rows);details[f'{ex}_{seed}']=det
            csv_write(HERE/'evaluation/extra_seed_per_scan.csv',results)
            del net,scans;torch.cuda.empty_cache()
    with (HERE/'evaluation/per_scan.csv').open() as f:
        first=list(csv.DictReader(f))
    combined=[]
    for r in first:
        if r['model']=='v3':continue
        converted={k:(None if v=='' else v) for k,v in r.items()}
        for k in ['pixel_tp','predicted_known_pixels','reference_pixels','reference_lesions','matched','false_positives','known_pixels','additions_proxy','removals_proxy','outline_corrections_proxy','merges','splits']:
            converted[k]=int(converted[k]) if converted[k] is not None else None
        converted['iou_cutoff']=float(r['iou_cutoff']);converted['complete']=r['complete']=='True'
        converted['area_error_mm2']=float(r['area_error_mm2']) if r['area_error_mm2'] else None
        converted['seed']=267;combined.append(converted)
    combined.extend(results);summary=[]
    for seed in [267,268,269]:
        for ex in 'ABC':
            for part in ['train','validation','holdout']:
                for cutoff in PROTOCOL['iou_thresholds']:
                    group=[r for r in combined if r['seed']==seed and r['model']==ex and r['split']==part and r['iou_cutoff']==cutoff and r['known_pixels']]
                    summary.append(dict(seed=seed,model=ex,split=part,iou_cutoff=cutoff,**aggregate(group)))
    write(HERE/'evaluation/seed_comparison.json',summary);csv_write(HERE/'evaluation/seed_comparison.csv',summary)
    matched=[]
    for seed in [268,269]:
        histories=[]
        for ex in 'ABC':
            with (HERE/f'experiment_{ex}'/f'seed_{seed}/history.csv').open() as f:histories.append(list(csv.DictReader(f)))
        common=min(map(len,histories))
        assert all(len({h[i]['sampling_sha256'] for h in histories})==1 for i in range(common))
        matched.append(dict(seed=seed,matched_epochs=common))
    write(HERE/'evaluation/seed_sampling_audit.json',matched)
    progress('Three-seed matched pilot complete')

if __name__=='__main__':run()
