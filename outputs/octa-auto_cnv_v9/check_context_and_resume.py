from common import *
import argparse
p=argparse.ArgumentParser();p.add_argument('--resume',action='store_true');a=p.parse_args()
if a.resume:
 from training import train
 f=HERE/'fits/outer0_m1';before=fingerprint(f/'final.pt');config=read(f/'config.json');result=train('outer0_m1',1,config['training_animals']);after=fingerprint(f/'final.pt');assert before==after
 write(HERE/'verification/COMPLETE_FIT_RESUME_QA.json',dict(passed=True,checkpoint_unchanged=True,epoch=result['completed_epochs'],optimizer_steps=result['optimizer_steps']))
 print('Completed fit resume leaves checkpoint unchanged')
else:
 from deliver import provenance_audit
 d=provenance_audit(read(HERE/'data/supervision.json'));print(json.dumps({k:d[k] for k in ['source_counts','positive_pixels','vessel_overlap_pixels','onh_overlap_pixels']}))
