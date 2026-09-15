"""Combine invocation histories and apply the prespecified development budget rule."""
import csv
import json
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent
RUN=HERE/'dev_seed20260908'
histories=[json.loads(p.read_text()) for p in sorted(RUN.glob('run_step_*.json'))]
events=[e for h in histories for e in h['events']]
assert len({e['step'] for e in events})==len(events)
assert [e['step'] for e in events]==list(range(1,len(events)+1))
epochs=[]
for end in events:
    if 'animal_macro_validation_loss' not in end: continue
    window=[e for e in events if end['step']-48<e['step']<=end['step']]
    train=float(np.mean([e['loss'] for e in window]))
    epochs.append(dict(epoch=end['step']//48,step=end['step'],train_loss=train,
        validation_loss=end['animal_macro_validation_loss'],
        validation_minus_train=end['animal_macro_validation_loss']-train))
def csvwrite(path,rows):
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f, list(dict.fromkeys(k for r in rows for k in r)))
        w.writeheader();w.writerows(rows)
csvwrite(RUN/'training_history_steps.csv',events)
csvwrite(RUN/'training_history_epochs.csv',epochs)
early=[e for e in epochs if 161<=e['epoch']<=180]
late=[e for e in epochs if 181<=e['epoch']<=200]
assert len(early)==len(late)==20
v0,v1=[float(np.mean([e['validation_loss'] for e in group])) for group in (early,late)]
g0,g1=[float(np.mean([e['validation_minus_train'] for e in group])) for group in (early,late)]
first200=[e for e in epochs if e['epoch']<=200]
best200=min(first200,key=lambda e:e['validation_loss'])
decision=dict(rule='Extend if validation window mean improves at least 1%, best epoch >180, and gap increase <=0.5.',
    earlier_window=[161,180],later_window=[181,200],earlier_val_mean=v0,later_val_mean=v1,
    relative_improvement=(v0-v1)/v0,earlier_gap=g0,later_gap=g1,gap_increase=g1-g0,
    best_epoch_at_200=best200['epoch'],best_loss_at_200=best200['validation_loss'],
    extend_to_400=bool(v1<=v0*.99 and best200['epoch']>180 and g1-g0<=.5))
(RUN/'extension_decision.json').write_text(json.dumps(decision,indent=2))
oldpath=HERE.parent/'20260908_v2/dev_seed20260908/training_history_step001920.archived.json'
old=json.loads(oldpath.read_text())
old_events=old['events']
prefix=events[:len(old_events)]
assert len(prefix)==len(old_events)==1920
assert all(a['key']==b['key'] and a['animal']==b['animal'] and a['step']==b['step'] for a,b in zip(prefix,old_events))
lossdiff=max(abs(a['loss']-b['loss']) for a,b in zip(prefix,old_events))
valdiff=max(abs(a['animal_macro_validation_loss']-b['animal_macro_validation_loss']) for a,b in zip(prefix,old_events) if 'animal_macro_validation_loss' in a)
summary=dict(epochs=len(epochs),steps=len(events),best=min(epochs,key=lambda e:e['validation_loss']),
    finite_losses=bool(all(np.isfinite(e['loss']) for e in events)),
    finite_nonzero_gradients=bool(all(np.isfinite(e['gradient_norm']) and e['gradient_norm']>0 for e in events)),
    gradient_min=min(e['gradient_norm'] for e in events),gradient_max=max(e['gradient_norm'] for e in events),
    training_elapsed_s=sum(h['elapsed_s'] for h in histories),
    peak_cuda_memory_bytes=max(h['peak_cuda_memory_bytes'] for h in histories),
    checkpoint_reload_exact=all(h['checkpoint_reload_exact'] for h in histories),
    first40_sample_sequence_identical=True,first40_max_loss_difference=lossdiff,first40_max_validation_difference=valdiff,
    config=histories[0]['config'],identity=histories[0]['identity'],code_identity=histories[0]['code_identity'])
(RUN/'training_summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(dict(summary=summary,extension=decision),indent=2))
