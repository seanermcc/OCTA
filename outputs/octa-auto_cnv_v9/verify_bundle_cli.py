"""Exercise both delivered inference entry points on one already selected scan."""
from common import *
import subprocess

sid=next(a['scan_id'] for a in read(HERE/'gallery/data.json')['cases'] if a['m1_count']>0 and a['m2_count']>0)
rows=[]
for model in (1,2):
 command='call "D:\\Anaconda\\Scripts\\activate.bat" octa && python -B predict_bundle.py --model '+str(model)+' --scan '+sid
 subprocess.run(command,shell=True,cwd=HERE,check=True)
 a=npz(HERE/'additional_inference'/f'v9_m{model}'/(sid+'.npz'))
 b=npz(HERE/'fits'/f'final_m{model}'/'predictions'/(sid+'.npz'))
 error=float(np.max(np.abs(a['score']-b['score'])))
 assert error<1e-6,(model,error)
 assert np.array_equal(a['raw_mask'],b['raw_mask'])
 doc=read(HERE/'additional_inference'/f'v9_m{model}'/(sid+'.json'))
 expected=read(HERE/'gallery/assets'/sid/'candidates.json')[f'm{model}']
 assert [c['runs'] for c in doc['candidates']]==[c['runs'] for c in expected]
 if model==2:assert [c['adjusted_score'] for c in doc['candidates']]==[c['adjusted_score'] for c in expected]
 rows.append(dict(model=model,scan_id=sid,max_probability_difference=error,raw_masks_equal=True,candidate_geometry_equal=True))
write(HERE/'verification/BUNDLE_CLI_QA.json',dict(passed=True,records=rows))
print('Both bundle inference entry points reproduce delivered predictions')
