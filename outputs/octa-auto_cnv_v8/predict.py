"""Inference only on the frozen 30 acquisitions; thresholds never selected here."""
from common import *
from models import UNet,StructuralCNN,infer_structural,filter_mask
from inference_structural import infer_structural
from v6_model import infer
from legacy import tensor_inputs
from scipy import ndimage as ndi
import torch,argparse

def components(mask):return int(ndi.label(mask,structure=np.ones((3,3)))[1])
def compare(pred,target,known):
    p=pred&known;t=target&known;intersection=int((p&t).sum());den=int(p.sum()+t.sum());union=int((p|t).sum())
    tc,nt=ndi.label(t,structure=np.ones((3,3)));pc,npred=ndi.label(p,structure=np.ones((3,3)))
    return dict(label='training-case comparison; not accuracy validation',dice=2*intersection/den if den else 1.,iou=intersection/union if union else 1.,missed_components=sum(not (p&(tc==i)).any() for i in range(1,nt+1)),extra_components=sum(not (t&(pc==i)).any() for i in range(1,npred+1)),reference_components=nt,predicted_components_within_reviewed=npred,false_positive_area_pixels=int((p&~t).sum()),false_positive_area_um2=float((p&~t).sum()*(1460/512)**2),false_positive_fraction_reviewed_background=float((p&~t).sum()/max(1,(known&~t).sum())),missed_area_pixels=int((t&~p).sum()),matching_rule='8-connected footprint components; any reviewed-pixel intersection; split/merge identity not adjudicated')

def run(model_id):
    torch.set_num_threads(4);device=torch.device('cuda');folder=HERE/f'model{model_id}'
    completed=read(folder/'complete.json');verify(completed['checkpoint']);cp=torch.load(completed['checkpoint']['path'],map_location='cpu',weights_only=False)
    assert cp['epoch']==100 and completed['optimizer_steps']==3200
    net=(UNet(19) if model_id==1 else StructuralCNN()).to(device);net.load_state_dict(cp['model']);net.eval()
    stats_path=HERE/'data'/('normalization_enface.json' if model_id==1 else 'normalization_structural.json')
    assert sha(stats_path)==cp['config']['normalization_sha256'];stats=read(stats_path)
    cases=read(HERE/'data/preview.json')['cases']
    for i,c in enumerate(cases):
        sid=c['scan_id'];path=HERE/f'predictions/model{model_id}'/(sid+'.npz');jp=path.with_suffix('.json')
        if jp.exists():verify(read(jp)['prediction']);continue
        cache=HERE/'cache'/sid
        if model_id==1:score=infer(net,tensor_inputs(npz(cache/'enface.npz'),stats,'C'),device,batch_size=4)
        else:score=infer_structural(net,np.load(cache/'structural.npy',mmap_mode='r'),stats['structural'],device)
        if score.shape!=(512,512) or not np.isfinite(score).all() or score.min()<0 or score.max()>1:raise FloatingPointError('Unusable native prediction '+sid)
        if float(score.max()-score.min())<1e-6:raise FloatingPointError('Spatially constant unusable prediction '+sid)
        raw=score>=(.7 if model_id==1 else .5)
        arrays,suppressed=filter_mask(raw) if model_id==1 else (dict(raw_mask=raw,filtered_mask=raw.copy()),[])
        target_file=HERE/'data/targets'/(sid+'.npz');unknown=~npz(target_file)['known'] if c['training_exposure'] else np.ones((512,512),bool)
        save(path,score=score,unknown_score=np.where(unknown,score,np.nan),unknown_mask=unknown,scan_id=np.array(sid),axis_order=np.array('B-scan,A-line'),**arrays)
        write(jp,dict(scan_id=sid,source_identity=c['acquisition']['source_identity'],role=c['role'],animal_training_exposure=True,checkpoint=completed['checkpoint'],prediction=fingerprint(path),threshold=.7 if model_id==1 else .5,threshold_status='fixed provisional display setting; not validated',raw_components=components(raw),display_components=components(arrays['filtered_mask']),raw_pixels=int(raw.sum()),display_pixels=int(arrays['filtered_mask'].sum()),suppressed=suppressed,removal_reason_codes={1:'one-native-pixel disk binary opening',2:'8-connected component smaller than 64 native pixels after opening'} if model_id==1 else {},score_range=[float(score.min()),float(score.max())]))
        progress('Frozen comparison inference',model=model_id,completed=i+1,total=30,scan=sid)

def summarize():
    manifest=read(HERE/'data/manifest.json');cases=read(HERE/'data/preview.json')['cases'];results=[];policy=[]
    for r in manifest['records']:
        z=npz(r['target_file']['path']);filtered,_=filter_mask(z['target']);p=z['target'];removed=p&~filtered['filtered_mask']
        policy.append(dict(scan_id=r['scan_id'],training_positive_pixels=int(p.sum()),pixels_hypothetically_removed=int(removed.sum()),fraction_removed=float(removed.sum()/max(1,p.sum())),original_components=components(p),remaining_components=components(filtered['filtered_mask']),training_targets_unchanged=True))
    for c in cases:
        sid=c['scan_id'];z1=npz(HERE/'predictions/model1'/(sid+'.npz'));z2=npz(HERE/'predictions/model2'/(sid+'.npz'));v6=npz(HERE/'cache'/sid/'v6.npz')
        row=dict(scan_id=sid,role=c['role'],animal_training_exposure=True,model1=read(HERE/'predictions/model1'/(sid+'.json')),model2=read(HERE/'predictions/model2'/(sid+'.json')),v6_components=components(v6['mask']))
        unknown=z1['unknown_mask'];unknown_path=HERE/'predictions/frozen_v6'/(sid+'_unknown.npz')
        save(unknown_path,scan_id=np.array(sid),axis_order=np.array('B-scan,A-line'),unknown_mask=unknown,unknown_score=np.where(unknown,v6['score'],np.nan),unknown_threshold_mask=v6['mask']&unknown,source_prediction_sha256=np.array(sha(HERE/'cache'/sid/'v6.npz')))
        row['frozen_v6_unknown_prediction']=fingerprint(unknown_path);row['unknown_pixels']=int(unknown.sum())
        if c['training_exposure']:
            truth=npz(HERE/'data/targets'/(sid+'.npz'))
            row['training_case_comparisons']={key:compare(mask.astype(bool),truth['target'],truth['known']) for key,mask in [('v6',v6['mask']),('model1_raw',z1['raw_mask']),('model1_filtered',z1['filtered_mask']),('model2',z2['raw_mask'])]}
        else:row['interpretation']='Unlabeled acquisition: predictions and reviewer observations only; no accuracy measurement'
        results.append(row)
    write(HERE/'reports/comparison.json',results);write(HERE/'reports/display_policy_training_impact.json',dict(policy='Hypothetical application to immutable known footprints; diagnostic only. Human training targets were never filtered and these settings were not tuned.',cases=policy))
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--model',type=int,choices=[1,2]);parser.add_argument('--summarize',action='store_true');args=parser.parse_args()
    if args.model:run(args.model)
    if args.summarize:summarize()
