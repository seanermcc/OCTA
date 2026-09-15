"""Animal-isolated training, calibration and separately stored evaluation."""
import time,random,os
import numpy as np
import torch
from torch.nn import functional as F
from common import *
from network import Model,masked_loss,native_prob,resolved_masks,confusion,scored

SETTINGS=dict(release='octo-vessel_onh_v2',seed=20260914,network='U-Net widths 8,16,32,64,128; GroupNorm; two logits',
              resolution=256,native_resolution=512,batch_size=4,max_epochs=80,steps_per_epoch=16,
              validation_every=5,early_stopping_checks=6,minimum_epochs=25,learning_rate=0.001,weight_decay=0.0001,
              augmentation='uniform rotations 0/90/180/270 and horizontal reflection; contrast 0.85-1.15 and brightness -0.08..0.08',
              loss='mean per-image/target class-balanced masked logistic loss; exact native positive/negative mass area-pooled 2x2',
              sampling='uniform training animal, then uniform eligible scan; no external/pretrained weights',
              thresholds=[0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9],onh_component_areas=[0,256,1024],
              final_duration='median selected epoch of six folds',final_thresholds='median of six calibration-selected thresholds; median component area',
              probability_storage='float16 sigmoid output at native model grid 256x256, bilinear align_corners=False to source grid before masks',
              notes='Experimental development cross-validation; no untouched final test. All frozen annotations, including test, determine eligibility only.')

def protocol(audit):
    path=HERE/'protocol.json'
    if path.exists():
        p=read_json(path)
        assert p['settings']==SETTINGS,'Settings changed; create a new release'
        assert p['training_code_hashes']==source_code_hash(),'Frozen training implementation changed'
        assert p['audit_sha256']==digest(HERE/'audit_manifest.json')
        return p
    rows=[r for r in audit['annotations'] if r['vessel_eligible'] or r['onh_eligible']]
    animals=sorted({r['animal'] for r in rows})
    calibration={'TS165':'TS169','TS169':'TS241','TS241':'TS247','TS247':'TS267','TS250':'TS241','TS267':'TS169'}
    assert set(animals)==set(calibration),'Revisit protocol if eligible animal set changes before training'
    folds=[]
    for i,animal in enumerate(animals):
        cal=calibration[animal];train=[a for a in animals if a not in [animal,cal]]
        roles={role:[r['scan_id'] for r in rows if r['animal'] in aa] for role,aa in [('train',train),('calibration',[cal]),('evaluation',[animal])]}
        assert not set(roles['train'])&set(roles['evaluation']) and not set(roles['calibration'])&set(roles['evaluation'])
        folds.append(dict(name='held_'+animal,seed=SETTINGS['seed']+i,evaluation_animal=animal,calibration_animal=cal,training_animals=train,
                          scans=roles,counts={k:count_roles([r for r in rows if r['scan_id'] in ids]) for k,ids in roles.items()}))
    p=dict(frozen_at=now(),audit_sha256=digest(HERE/'audit_manifest.json'),training_code_hashes=source_code_hash(),
           settings=SETTINGS,folds=folds,all_label_scans=[r['scan_id'] for r in rows],
           selection='checkpoint: lowest calibration balanced masked logistic loss; thresholds: calibration only, before evaluation predictions are read',
           calibration_objective='Vessel: pooled support Dice. ONH: positive-case mean masked Dice minus 0.5*reviewed-absence detection rate; ties favor higher threshold then larger minimum component area.',
           baseline='Frozen vessel v1 sometimes has human ONH assistance; score on identical support and report assistance per scan. No automatic v1 ONH score.',
           supervision='Vessel: completed review plus direct brush footprint, exclude uncertain/ONH/derived-only removals. Untouched pixels ignored even if automatic vessel is present. ONH: completed assessable review; full footprint/complement minus uncertain pixels. Outside image supplies negative only.',
           limitations=['Brush supervision is sparse and biased toward corrections; scored specificity is not whole-image specificity.',
                        'Major vessels defined by reviewer intent, not a learned exhaustive caliber boundary. Small-vessel omissions are not negatives.',
                        'Saved brush footprints may include inherited legacy footprints; their recorded provenance is preserved, not reconstructed.',
                        'ONH training is uneven by animal; six-outer-fold results are development cross-validation, not a prospective final test.',
                        '256x256 model inputs trade vessel-edge precision for full-field context; outputs restored to native coordinates.'])
    write_json(path,p);return p

def load_data(audit):
    inventory={r['scan_id']:r for r in read_json(HERE/'inventory.json')}
    data={}
    for r in audit['annotations']:
        if not (r['vessel_eligible'] or r['onh_eligible']):continue
        sid=r['scan_id'];meta=inventory[sid]
        assert digest(meta['projection_path'])==meta['projection_sha256']
        with np.load(meta['projection_path'],allow_pickle=False) as z: im=normalized(z['structural_enface'])
        with np.load(HERE/r['supervision_file'],allow_pickle=False) as z:
            pos=z['positive'].copy();neg=z['negative'].copy()
        with np.load(meta['proposal_path'],allow_pickle=False) as z:
            baseline=z['predicted_vasculature_mask'].copy();human_onh=z['human_onh_exclusion_mask'].copy()
        image=F.avg_pool2d(torch.from_numpy(im)[None,None],2)[0]
        pooled_pos=F.avg_pool2d(torch.from_numpy(pos.astype(np.float32))[None],2)[0]
        pooled_neg=F.avg_pool2d(torch.from_numpy(neg.astype(np.float32))[None],2)[0]
        data[sid]=dict(row=r,meta=meta,image=image,pos=pos,neg=neg,pooled_pos=pooled_pos,pooled_neg=pooled_neg,baseline=baseline,human_onh=human_onh)
    return data

def configure(seed):
    torch.set_num_threads(4)
    torch.manual_seed(seed);np.random.seed(seed);random.seed(seed)
    if torch.cuda.is_available():torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark=False
    torch.backends.cudnn.deterministic=True
    return 'cuda' if torch.cuda.is_available() else 'cpu'

def checkpoint(path,obj):
    disk_check(12*1024**2)
    tmp=path.with_name(path.name+'.writing');torch.save(obj,tmp);tmp.replace(path)

def predict(model,item,device):
    with torch.no_grad():
        return model(item['image'][None].to(device)).sigmoid()[0].cpu().numpy().astype(np.float16)

def validation_loss(model,data,ids,device):
    values=[];model.eval()
    with torch.no_grad():
        for sid in ids:
            d=data[sid]
            loss=masked_loss(model(d['image'][None].to(device)),d['pooled_pos'][None].to(device),d['pooled_neg'][None].to(device))
            values.append(float(loss))
    return float(np.mean(values))

def train_one(spec,data,protocol_hash,epochs=None):
    folder=HERE/'models'/spec['name'];folder.mkdir(parents=True,exist_ok=True)
    done=folder/'trained.json'
    if done.exists():
        result=read_json(done)
        assert result['protocol_sha256']==protocol_hash
        assert digest(folder/'best.pt')==result['checkpoint_sha256']
        return result
    device=configure(spec['seed']);model=Model().to(device)
    optim=torch.optim.AdamW(model.parameters(),lr=SETTINGS['learning_rate'],weight_decay=SETTINGS['weight_decay'])
    rng=np.random.default_rng(spec['seed'])
    ids=spec['scans']['train'];cal=spec['scans'].get('calibration',[])
    grouped={a:[sid for sid in ids if data[sid]['row']['animal']==a] for a in spec['training_animals']}
    best=float('inf');best_epoch=0;stale=0;start_epoch=0;history=[]
    last=folder/'resume.pt'
    if last.exists():
        state=torch.load(last,map_location=device,weights_only=False)
        assert state['protocol_sha256']==protocol_hash
        model.load_state_dict(state['model']);optim.load_state_dict(state['optimizer'])
        start_epoch=state['epoch'];best=state['best'];best_epoch=state['best_epoch'];stale=state['stale'];history=state['history']
        rng.bit_generator.state=state['numpy_rng'];torch.set_rng_state(state['torch_rng'].cpu())
        if device=='cuda':torch.cuda.set_rng_state_all([x.cpu() for x in state['cuda_rng']])
    limit=epochs or SETTINGS['max_epochs']
    start=time.monotonic()
    epoch=start_epoch
    for epoch in range(start_epoch+1,limit+1):
        model.train();losses=[]
        for _ in range(SETTINGS['steps_per_epoch']):
            xs=[];ps=[];ns=[]
            for j in range(SETTINGS['batch_size']):
                animal=str(rng.choice(spec['training_animals']));sid=str(rng.choice(grouped[animal]));d=data[sid]
                k=int(rng.integers(4));flip=bool(rng.integers(2))
                tensors=[torch.rot90(d[key],k,(-2,-1)) for key in ['image','pooled_pos','pooled_neg']]
                if flip:tensors=[torch.flip(t,[-1]) for t in tensors]
                tensors[0]=(tensors[0]*float(rng.uniform(.85,1.15))+float(rng.uniform(-.08,.08))).clamp(0,1)
                xs.append(tensors[0]);ps.append(tensors[1]);ns.append(tensors[2])
            x=torch.stack(xs).to(device);p=torch.stack(ps).to(device);n=torch.stack(ns).to(device)
            optim.zero_grad(set_to_none=True)
            loss=masked_loss(model(x),p,n)
            if not torch.isfinite(loss):raise RuntimeError('Nonfinite training loss')
            loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),5);optim.step();losses.append(float(loss.detach()))
        check=epoch%SETTINGS['validation_every']==0 or epoch==limit
        if check:
            val=validation_loss(model,data,cal,device) if cal else None
            improved=not cal or val<best-1e-5
            if improved:
                best=val if val is not None else 0.;best_epoch=epoch;stale=0
                checkpoint(folder/'best.pt',dict(model=model.state_dict(),epoch=epoch,protocol_sha256=protocol_hash,model_name=spec['name'],spec=spec))
            else:stale+=1
            history.append(dict(epoch=epoch,training_loss=float(np.mean(losses)),calibration_loss=val))
            checkpoint(last,dict(model=model.state_dict(),optimizer=optim.state_dict(),epoch=epoch,best=best,best_epoch=best_epoch,stale=stale,history=history,
                protocol_sha256=protocol_hash,numpy_rng=rng.bit_generator.state,torch_rng=torch.get_rng_state(),cuda_rng=torch.cuda.get_rng_state_all() if device=='cuda' else []))
            write_json(folder/'history.json',history)
            progress('training',model=spec['name'],epoch=epoch,max_epochs=limit,best_epoch=best_epoch,calibration_loss=val,seconds=round(time.monotonic()-start,1))
            if cal and epoch>=SETTINGS['minimum_epochs'] and stale>=SETTINGS['early_stopping_checks']:break
    result=dict(model=spec['name'],completed_at=now(),protocol_sha256=protocol_hash,checkpoint_sha256=digest(folder/'best.pt'),
                selected_epoch=best_epoch,epochs_run=epoch,parameter_count=sum(p.numel() for p in model.parameters()),device=device,
                gpu=torch.cuda.get_device_name(0) if device=='cuda' else None,spec=spec)
    write_json(done,result)
    # Only this release's redundant optimizer resume file is removed after its model is complete.
    if last.exists():last.unlink()
    return result

def calibrate(spec,data,protocol_hash):
    folder=HERE/'models'/spec['name'];path=folder/'calibration.json'
    if path.exists():
        result=read_json(path);assert result['protocol_sha256']==protocol_hash;assert result['checkpoint_sha256']==digest(folder/'best.pt');return result
    device=configure(spec['seed']);model=Model().to(device)
    state=torch.load(folder/'best.pt',map_location=device,weights_only=False);model.load_state_dict(state['model']);model.eval()
    probs={sid:native_prob(predict(model,data[sid],device)) for sid in spec['scans']['calibration']}
    onh_trials=[]
    for threshold in SETTINGS['thresholds']:
        for area in SETTINGS['onh_component_areas']:
            ds=[];absent=[]
            for sid,p in probs.items():
                d=data[sid]
                if not d['row']['onh_eligible']:continue
                mask=resolved_masks(p,[.5,threshold],area)[1]
                if d['pos'][1].any():
                    ds.append(scored(confusion(mask,d['pos'][1],d['neg'][1]))['dice'])
                elif d['row']['onh_visibility']=='Outside image':absent.append(bool((mask&d['neg'][1]).any()))
            score=float(np.mean(ds) if ds else 0)-.5*float(np.mean(absent) if absent else 0)
            onh_trials.append(dict(threshold=threshold,min_area=area,score=score,positive_dice=float(np.mean(ds)) if ds else None,
                                   absent_false_detection_rate=float(np.mean(absent)) if absent else None,positive_cases=len(ds),absent_cases=len(absent)))
    best_onh=max(onh_trials,key=lambda r:(r['score'],r['threshold'],r['min_area']))
    vessel_trials=[]
    for threshold in SETTINGS['thresholds']:
        counts=dict(tp=0,fn=0,fp=0,tn=0)
        for sid,p in probs.items():
            d=data[sid];mask=resolved_masks(p,[threshold,best_onh['threshold']],best_onh['min_area'])[0]
            c=confusion(mask,d['pos'][0],d['neg'][0])
            for k in counts:counts[k]+=c[k]
        vessel_trials.append(dict(threshold=threshold,**scored(counts)))
    best_v=max(vessel_trials,key=lambda r:((r['dice'] or 0),r['threshold']))
    result=dict(protocol_sha256=protocol_hash,checkpoint_sha256=digest(folder/'best.pt'),
                thresholds=[best_v['threshold'],best_onh['threshold']],min_onh_area=best_onh['min_area'],
                calibration_animal=spec['calibration_animal'],vessel_trials=vessel_trials,onh_trials=onh_trials)
    write_json(path,result);return result

def evaluate(spec,data,cal,protocol_hash):
    folder=HERE/'models'/spec['name'];out=HERE/'evaluation';out.mkdir(exist_ok=True)
    resultpath=out/(spec['name']+'.json')
    if resultpath.exists():
        old=read_json(resultpath);assert old['protocol_sha256']==protocol_hash
        for r in old['scans']:assert digest(HERE/r['prediction_file'])==r['prediction_sha256']
        return old
    device=configure(spec['seed']);model=Model().to(device)
    checkpoint_path=folder/'best.pt'
    state=torch.load(checkpoint_path,map_location=device,weights_only=False);model.load_state_dict(state['model']);model.eval()
    rows=[]
    for sid in spec['scans']['evaluation']:
        d=data[sid];raw=predict(model,d,device);prob=native_prob(raw);mask=resolved_masks(prob,cal['thresholds'],cal['min_onh_area'])
        pp=out/(sid+'.npz')
        save_npz(pp,probability_model_grid=raw,vessel_mask=mask[0],onh_mask=mask[1],scan_id=np.array([sid]),model=np.array([spec['name']]),
                 checkpoint_sha256=np.array([digest(checkpoint_path)]),thresholds=np.array(cal['thresholds']),min_onh_area=np.array([cal['min_onh_area']]))
        r=dict(scan_id=sid,animal=d['row']['animal'],onh_visibility=d['row']['onh_visibility'],
               prediction_file=str(pp.relative_to(HERE)),prediction_sha256=digest(pp),frozen_human_onh_pixels=int(d['human_onh'].sum()),
               onh_eligible=d['row']['onh_eligible'],vessel_eligible=d['row']['vessel_eligible'])
        for i,target in enumerate(TARGETS):
            r[target]=scored(confusion(mask[i],d['pos'][i],d['neg'][i]));r[target]['coverage_fraction']=float((d['pos'][i]|d['neg'][i]).mean())
        r['v1_vessel']=scored(confusion(d['baseline'],d['pos'][0],d['neg'][0]))
        r['onh_false_detection']=bool((mask[1]&d['neg'][1]).any()) if d['row']['onh_eligible'] and d['row']['onh_visibility']=='Outside image' else None
        r['onh_false_area_pixels']=int((mask[1]&d['neg'][1]).sum()) if r['onh_false_detection'] is not None else None
        # Diagnostic isolates vessel head performance outside any reviewed/frozen human ONH region.
        common=~(d['pos'][1]|d['human_onh'])
        r['common_onh_exclusion_new_vessel']=scored(confusion(prob[0]>=cal['thresholds'][0],d['pos'][0]&common,d['neg'][0]&common))
        r['common_onh_exclusion_v1_vessel']=scored(confusion(d['baseline'],d['pos'][0]&common,d['neg'][0]&common))
        rows.append(r)
    result=dict(protocol_sha256=protocol_hash,model=spec['name'],checkpoint_sha256=digest(checkpoint_path),
                evaluation_animal=spec['evaluation_animal'],calibration_animal=spec['calibration_animal'],training_animals=spec['training_animals'],
                thresholds=cal['thresholds'],min_onh_area=cal['min_onh_area'],scans=rows)
    write_json(resultpath,result);progress('evaluation_complete',animal=spec['evaluation_animal'],scans=len(rows));return result

def main():
    from audit import main as audit_main
    audit=audit_main();p=protocol(audit);ph=digest(HERE/'protocol.json');data=load_data(audit)
    trained=[];cals=[]
    for spec in p['folds']:
        trained.append(train_one(spec,data,ph));cals.append(calibrate(spec,data,ph))
        evaluate(spec,data,cals[-1],ph)
    final_settings=dict(epochs=int(np.median([r['selected_epoch'] for r in trained])),
        thresholds=np.median([r['thresholds'] for r in cals],axis=0).tolist(),min_onh_area=int(np.median([r['min_onh_area'] for r in cals])),
        source='Median of six calibration-selected settings; all-label inference only',protocol_sha256=ph)
    path=HERE/'final_settings.json'
    if path.exists():assert read_json(path)==final_settings
    else:write_json(path,final_settings)
    spec=dict(name='all_eligible',seed=SETTINGS['seed']+100,training_animals=sorted({data[s]['row']['animal'] for s in p['all_label_scans']}),scans=dict(train=p['all_label_scans'],calibration=[],evaluation=[]))
    train_one(spec,data,ph,epochs=final_settings['epochs'])
    progress('models_complete',evaluation_models=len(trained),final_training_scans=len(p['all_label_scans']),final_settings=final_settings)

if __name__=='__main__':main()
