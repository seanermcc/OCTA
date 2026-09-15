"""Validation-selected thresholds, frozen native predictions, complete-field comparisons."""
from common import *
from train import load_scans,configure,CHANNELS
from model import UNet,infer
from metrics import PROTOCOL,score,aggregate,components
import torch

def evaluate():
    configure(267);device=torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    assert read(HERE/'evaluation/protocol.json')==PROTOCOL
    all_rows=[];all_details={};thresholds={}
    for experiment in 'ABC':
        out=HERE/f'experiment_{experiment}';checkpoint=out/'best.pt'
        ck=torch.load(checkpoint,map_location=device,weights_only=False)
        assert ck['config']['manifest_sha256']==sha(HERE/'data/manifest.json')
        net=UNet(CHANNELS[experiment]).to(device);net.load_state_dict(ck['model']);scans=load_scans(experiment)
        # Write scores for every acquisition before performing any thresholding.
        predictions={}
        for d in scans:
            sid=d['record']['scan_id'];p=infer(net,d['input'],device,4);predictions[sid]=p
            save(out/'scores'/f'{sid}.npz',score=p,scan_id=np.array(sid),axis_order=np.array('B-scan,A-line'),checkpoint_sha256=np.array(sha(checkpoint)),native_shape=np.array([512,512]))
        sweep=[]
        for threshold in PROTOCOL['threshold_grid']:
            tp=pred=truth=0
            for d in scans:
                if d['record']['split']!='validation':continue
                p=predictions[d['record']['scan_id']]>=threshold;k=d['known'];t=d['target']
                tp+=int((p&t&k).sum());pred+=int((p&k).sum());truth+=int(t.sum())
            sweep.append(dict(threshold=threshold,known_dice=2*tp/(pred+truth)))
        selected=max(sweep,key=lambda r:(r['known_dice'],r['threshold']))
        threshold=selected['threshold'];thresholds[experiment]=threshold
        write(out/'threshold.json',dict(selected=selected,sweep=sweep,source='D49 validation only',protocol=PROTOCOL))
        rows=[];details={}
        for d in scans:
            r=d['record'];sid=r['scan_id'];mask=predictions[sid]>=threshold;labels,_=components(mask)
            save(out/'predictions'/f'{sid}.npz',mask=mask,candidate_labels=labels,threshold=np.array(threshold),scan_id=np.array(sid))
            write(out/'predictions'/f'{sid}.json',dict(scan_id=sid,axis_order='B-scan,A-line',human_reviewed=False,threshold=threshold,
                candidates=[dict(id=int(i),runs=encode(labels==i)) for i in np.unique(labels) if i>0]))
            for cutoff in PROTOCOL['iou_thresholds']:
                values,detail=score(mask,d,r['audit']['complete'],cutoff)
                row=dict(model=experiment,scan_id=sid,split=r['split'],eye=r['eye'],visit=r['day_label'],complete=r['audit']['complete'],iou_cutoff=cutoff,threshold=threshold,**values)
                rows.append(row)
                if cutoff==.1:details[sid]=detail
        csv_write(out/'evaluation.csv',rows);write(out/'evaluation_details.json',details)
        all_rows.extend(rows);all_details[experiment]=details
        progress('Model evaluated',experiment=experiment,threshold=threshold)
        del net;torch.cuda.empty_cache()
    scans=load_scans('A');rows=[];details={}
    for d in scans:
        r=d['record'];sid=r['scan_id'];baseline=npz(V3/'proposals'/f'{sid}.npz')
        assert str(baseline['scan_id'].reshape(-1)[0])==sid
        mask=baseline['proposal_mask'].astype(bool);labels=baseline['candidate_labels']
        assert np.array_equal(mask,labels>0)
        for cutoff in PROTOCOL['iou_thresholds']:
            values,detail=score(mask,d,r['audit']['complete'],cutoff,labels)
            rows.append(dict(model='v3',scan_id=sid,split=r['split'],eye=r['eye'],visit=r['day_label'],complete=r['audit']['complete'],iou_cutoff=cutoff,threshold=None,**values))
            if cutoff==.1:details[sid]=detail
    csv_write(HERE/'evaluation/heuristic_v3.csv',rows);all_rows.extend(rows);all_details['v3']=details
    write(HERE/'evaluation/details.json',all_details);csv_write(HERE/'evaluation/per_scan.csv',all_rows)
    summaries=[]
    for model in ['A','B','C','v3']:
        for part in ['train','validation','holdout']:
            for cutoff in PROTOCOL['iou_thresholds']:
                group=[r for r in all_rows if r['model']==model and r['split']==part and r['iou_cutoff']==cutoff and r['known_pixels']]
                summaries.append(dict(model=model,split=part,iou_cutoff=cutoff,**aggregate(group)))
    csv_write(HERE/'evaluation/comparison.csv',summaries);write(HERE/'evaluation/comparison.json',summaries)
    # Eye and availability strata are descriptive; they never enter the image tensor.
    strata=[]
    for model in ['A','B','C','v3']:
        for part in ['validation','holdout']:
            for eye in ['OD','OS']:
                group=[r for r in all_rows if r['model']==model and r['split']==part and r['eye']==eye and r['iou_cutoff']==.1]
                if group:strata.append(dict(model=model,split=part,eye=eye,**aggregate(group)))
    csv_write(HERE/'evaluation/eye_strata.csv',strata)
    availability=[];artifacts=[]
    for model,scandetails in all_details.items():
        for sid,d in scandetails.items():
            part=next(r['split'] for r in read(HERE/'data/manifest.json')['scans'] if r['scan_id']==sid)
            availability.extend(dict(model=model,scan_id=sid,split=part,low_availability=x['available_fraction']<.5,**x) for x in d['lesion_availability'])
            artifacts.extend(dict(model=model,scan_id=sid,split=part,**x) for x in d['false_positive_artifacts'])
    csv_write(HERE/'evaluation/lesion_availability.csv',availability);csv_write(HERE/'evaluation/false_positive_artifacts.csv',artifacts)
    # All overlapping training epochs must have identical acquisition/tile schedules.
    histories={ex:read_history(HERE/f'experiment_{ex}/history.csv') for ex in 'ABC'}
    common_epochs=min(map(len,histories.values()))
    assert all(len({histories[e][i]['sampling_sha256'] for e in 'ABC'})==1 for i in range(common_epochs))
    write(HERE/'evaluation/matched_training_audit.json',dict(sampling_identical_for_common_epochs=common_epochs,
        seed=267,architecture_difference='Input count only',thresholds=thresholds,
        independent_weights=True,all_label_fit=False,additional_seeds_run=False,
        stable_improvement_claim=False,review_time_savings_claim=False))

def read_history(path):
    with Path(path).open() as f:return list(csv.DictReader(f))

if __name__=='__main__':evaluate()
