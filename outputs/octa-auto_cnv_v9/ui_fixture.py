"""Synthetic browser QA only. No human files or genuine model predictions."""
from common import *
from candidates import extract,adjust
from media import png,gray,rgba
import shutil
def run():
 out=HERE/'verification/ui_fixture'
 for name in ('index.html','app.js','review.js','style.css'):shutil.copyfile(HERE/'gallery'/name,dest(out/name))
 html=(out/'index.html').read_text(encoding='utf8');(out/'index.html').write_text(html.replace('TREE SHREW OCT / OCTA','SYNTHETIC UI TEST — NOT MODEL RESULTS'),encoding='utf8')
 cases=[];media=[]
 for i in range(2):
  sid=f'SYNTHETIC_{i}';folder=out/'assets'/sid;volume=np.broadcast_to(np.arange(64,dtype=np.float32)[None,:,None],(512,64,512)).copy();volume[0,:,0]=64;volume[511,:,-1]=64
  p=dest(folder/'images.npy');np.save(p,volume)
  opt=np.tile(np.arange(512,dtype=np.float32),(512,1));png(folder/'structural.png',gray(opt));png(folder/'octa.png',gray(opt.T));z=np.zeros((512,512),bool);v=z.copy();v[:,200:215]=True;o=z.copy();o[100:200,250:350]=True;png(folder/'vessel.png',rgba(v,(20,175,255)));png(folder/'onh.png',rgba(o,(38,235,127)))
  score=np.zeros((512,512),np.float32)
  if i==0:score[0:20,20:40]=.9;score[490:512,470:500]=.8
  c=np.zeros((11,512,512),np.float32);c[2]=1;labels,rr=extract(score,c);adj=adjust(rr,dict(fitted=False,supported_area_pixels=None))
  if adj:adj[1]['adjusted_score']=.1;adj[1]['display_selected']=False
  write(folder/'candidates.json',dict(m1=rr,m2=adj))
  cases.append(dict(scan_id=sid,animal='TEST',eye='OD',session_date=f'2000-01-0{i+1}',day_label='synthetic',day_basis='synthetic fixture; no research results',queue_position=i+1,context_source='synthetic',quality_note='synthetic test fixture',m1_count=len(rr),m2_count=len(rr),hidden_count=1 if rr else 0,adjusted_count=1 if rr else 0,m1_pixels=int((score>=.7).sum()),m2_pixels=int((score>=.7).sum()),disagreement_pixels=0,canonical_crop_offset=0))
  media.append(dict(scan_id=sid,images=fingerprint(p),bscan_display_limits=[0,64]))
 write(out/'data.json',dict(cases=cases,selection_sha256='SYNTHETIC'));write(out/'media_manifest.json',dict(records=media))
if __name__=='__main__':run()
