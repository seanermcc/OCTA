"""Include CNV events saved in layer-review journals; replace before inference."""
from common import *
from prepare import prepare_case
import re,shutil
def run():
 out=HERE/'data/novelty_supplement.json'
 if out.exists():
  d=read(out)
  for r in d['records']:verify(r['source'])
  if d['selection_sha256']!=sha(HERE/'data/selection.json'):raise ValueError('Supplement selection changed')
  return d
 records=[];dirs=[]
 for directory,children,files in os.walk(ROOT/'outputs'):
  p=Path(directory);children[:]=[c for c in children if c not in {'cache','checkpoints','predictions','proposals','figures','images','inputs','volumes','verification','__pycache__','node_modules','code_snapshot','implementation_snapshot'} and not (p/c).is_relative_to(HERE)]
  if 'journals' not in p.parts:continue
  dirs.append(str(p))
  for name in files:
   if not name.endswith('.json'):continue
   fp=p/name;d=read(fp);events=d.get('events',[])
   actions=[e.get('action') for e in events if e.get('action') in ('cnv_region','cnv_edge','cnv_edge_mark','hyper_ref')]
   if actions:records.append(dict(scan_id=d['scan_id'],source=fingerprint(fp),actions=sorted(set(actions)),revision=d.get('revision'),reason='prior human CNV/lesion event in layer-review journal, regardless of later undo'))
 excluded={r['scan_id'] for r in records};selection=read(HERE/'data/selection.json');initial=sha(HERE/'data/selection.json');old=dest(HERE/'data/selection_initial.json');shutil.copyfile(HERE/'data/selection.json',old);changes=[]
 exby={r['scan_id']:r for r in read(EXPORT/'manifest.json')['records']}
 for i,a in enumerate(selection['acquisitions']):
  if a['scan_id'] not in excluded:continue
  options=[r for r in selection['reserve'] if r['scan_id'] not in excluded]
  same=[r for r in options if r['animal']==a['animal']];replacement=(same or options)[0]
  selection['reserve']=[r for r in selection['reserve'] if r['scan_id']!=replacement['scan_id']]
  c=exby[replacement['scan_id']];replacement.update(queue_position=i+1,context_source=c['selection'],prior_vessel_review=c['vessel_reviewed'],prior_automatic_cnv_inference=True,prior_cnv_supervision=False,visit_group=f"{replacement['animal']}_{replacement['eye']}_{replacement['session_date']}")
  prepare_case(replacement);selection['acquisitions'][i]=replacement
  changes.append(dict(removed=a['scan_id'],replacement=replacement['scan_id'],reason='prior CNV lesion event in layer-review journal; same-animal first available in pre-frozen reserve; before any selected-scan prediction'))
 selection['replacements']+=changes;selection['initial_selection_sha256']=initial;write(HERE/'data/selection.json',selection)
 d=dict(records=records,searched_journal_directories=dirs,additional_cnv_acquisitions=sorted(excluded),changes=changes,initial_selection_sha256=initial,selection_sha256=sha(HERE/'data/selection.json'),prediction_independent=True)
 write(out,d);print(json.dumps(dict(additional_cnv_acquisitions=sorted(excluded),changes=changes)),flush=True);return d
if __name__=='__main__':run()
