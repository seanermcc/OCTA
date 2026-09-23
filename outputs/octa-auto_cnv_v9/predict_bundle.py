"""Use a delivered bundle with a validated acquisition provider; local v9 outputs only."""
from common import *
import torch,argparse
from v6_model import UNet,infer
from prepare import prepare_case,input_tensor
from candidates import extract,adjust
def run(model,sid):
 torch.set_num_threads(4);torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True
 bundle=HERE/'bundles'/f'v9_m{model}';manifest=read(bundle/'bundle.json');verify(manifest['checkpoint']);verify(manifest['normalization'])
 inv=read(V7/'queue/inventory.json')['scans'];a=next((a for a in inv if a['scan_id']==sid),None)
 if a is None:raise ValueError('Acquisition needs a validated processed-input provider before bundle inference')
 prepare_case(a);cp=torch.load(manifest['checkpoint']['path'],map_location='cpu',weights_only=False);net=UNet(cp['contract']['channels']).cuda();net.load_state_dict(cp['model']);stats=read(manifest['normalization']['path']);score=infer(net,input_tensor(sid,stats,model),torch.device('cuda'),batch_size=4)
 labels,cs=extract(score,npz(HERE/'cache'/sid/'context.npz')['channels'])
 if model==2:
  verify(manifest['scorer']);cs=adjust(cs,read(manifest['scorer']['path']))
 out=HERE/'additional_inference'/f'v9_m{model}'/(sid+'.npz');save(out,score=score,raw_mask=score>=.7,labels=labels,scan_id=np.array(sid),axis_order=np.array('B-scan,A-line'))
 write(out.with_suffix('.json'),dict(scan_id=sid,prediction=fingerprint(out),bundle=fingerprint(bundle/'bundle.json'),candidates=cs,automatic_unreviewed=True));print(out)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--model',type=int,choices=[1,2],required=True);p.add_argument('--scan',required=True);a=p.parse_args()
 with RunLock():run(a.model,a.scan)
