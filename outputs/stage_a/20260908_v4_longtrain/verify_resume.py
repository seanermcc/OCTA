"""Exercise real training/checkpoint IO with tiny synthetic data, outside package."""
from argparse import Namespace
from pathlib import Path
import contextlib
import hashlib
import json
from unittest.mock import patch
import torch
import stage_a.train as train

HERE=Path(__file__).resolve().parent
OUT=HERE/'resume_regression'
class Synthetic:
    def __init__(self,*args):
        self.records=[dict(key='synthetic',animal='synthetic')]
        self.animals=['synthetic']
        self.identity={'synthetic':True}
    def __len__(self): return 1
    def sample(self,index,device='cpu',flip=False):
        x=torch.linspace(0,1,32*16).reshape(1,1,32,16).to(device)
        rows=torch.arange(8,device=device).reshape(1,8,1).expand(1,8,16)*2+5.
        valid=torch.ones_like(rows,dtype=torch.bool)
        regions=torch.full((1,32,16),-100,dtype=torch.long,device=device)
        return x,rows,valid,regions

def hashes():
    return {p.name:dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),mtime_ns=p.stat().st_mtime_ns)
            for p in OUT.iterdir() if p.suffix in ('.json','.pt')}

a=Namespace(device='cpu',data=None,smoke_steps=0,out=OUT,resume=None,
    base=8,lr=.0003,region_weight=.1,seed=20260908,steps_per_epoch=1,epochs=1)
with patch.object(train,'Dataset',Synthetic):
    train.run(a)
    before=hashes()
    a.resume=OUT/'last.pt'
    train.run(a)
    after=hashes()
    assert before==after, 'No-op resume modified history or checkpoints'
    a.epochs=2
    train.run(a)
    assert hashes()['run_step_000001.json']==before['run_step_000001.json']
    new=json.loads((OUT/'run_step_000002.json').read_text())
    assert len(new['events'])==1 and new['events'][0]['step']==2
result=dict(noop_preserves_history_and_checkpoints=True,positive_step_resume_writes_new_history=True,
    checkpoint_roundtrip_exact=True,synthetic_only=True,code_identity_after=train.code_identity())
(HERE/'resume_regression_result.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result))
