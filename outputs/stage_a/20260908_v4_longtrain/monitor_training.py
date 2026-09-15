"""Compact progress from atomic checkpoints; no training or checkpoint changes."""
import json
from pathlib import Path
from datetime import datetime, timezone
import torch
HERE=Path(__file__).resolve().parent
RUN=HERE/'dev_seed20260908'
ck=torch.load(RUN/'last.pt',map_location='cpu',weights_only=True)
best=torch.load(RUN/'best.pt',map_location='cpu',weights_only=True)
lastlog=next((p for p in (HERE/'logs/train_400.log',HERE/'logs/train_200.log') if p.exists()),None)
lines=lastlog.read_text(encoding='utf-16' if lastlog.read_bytes()[:2] in (b'\xff\xfe',b'\xfe\xff') else 'utf-8').splitlines()
events=[]
for line in lines:
    try: obj=json.loads(line)
    except (ValueError,TypeError): continue
    if 'step' in obj: events.append(obj)
sample=dict(time=datetime.now(timezone.utc).isoformat(),completed_epoch=ck['epoch'],
    step=events[-1]['step'],best_epoch=best['epoch'],best_validation=best['best_validation'],
    recent_mean_training_loss=sum(e['loss'] for e in events[-48:])/len(events[-48:]))
if ck['epoch']<=40 and events:
    old=json.loads((HERE.parent/'20260908_v2/dev_seed20260908/training_history_step001920.archived.json').read_text())['events']
    prefix=events[:min(1920,len(events))]
    sample['sample_sequence_matches_baseline']=all(e['key']==old[e['step']-1]['key'] for e in prefix)
    sample['max_training_loss_difference_from_baseline']=max(abs(e['loss']-old[e['step']-1]['loss']) for e in prefix)
with (HERE/'training_progress.jsonl').open('a') as f:f.write(json.dumps(sample)+'\n')
print(json.dumps(sample))
