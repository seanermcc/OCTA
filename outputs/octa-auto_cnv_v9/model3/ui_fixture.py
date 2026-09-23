from common import *
from candidates import extract,adjust
from media import png,gray,rgba
import shutil

out=HERE/'verification/ui_fixture'
for name in ('index.html','app.js','style.css'):shutil.copyfile(HERE/'gallery'/name,dest(out/name))
p=out/'index.html';p.write_text(p.read_text(encoding='utf8').replace('TREE SHREW OCT / OCTA','SYNTHETIC UI TEST — NOT MODEL RESULTS'),encoding='utf8')
cases=[];media=[]
for i in range(2):
 sid=f'SYNTHETIC_{i}';folder=out/'assets'/sid
 volume=np.broadcast_to(np.arange(64,dtype=np.float32)[None,:,None],(512,64,512)).copy()
 p=dest(folder/'images.npy');np.save(p,volume);fp=fingerprint(p)
 opt=np.tile(np.arange(512,dtype=np.float32),(512,1));png(folder/'structural.png',gray(opt));png(folder/'octa.png',gray(opt.T))
 v=np.zeros((512,512),bool);v[:,200:215]=True;o=np.zeros_like(v);o[100:200,250:350]=True
 png(folder/'vessel.png',rgba(v,(20,175,255)));png(folder/'onh.png',rgba(o,(38,235,127)))
 score=np.zeros((512,512),np.float32)
 if i==0:score[0:20,20:40]=.9;score[490:512,470:500]=.8
 labels,cs=extract(score,np.zeros((11,512,512),np.float32));cs=adjust(cs,dict(fitted=False,supported_area_pixels=None))
 if cs:cs[1]['adjusted_score']=.1;cs[1]['display_selected']=False
 manual=[dict(id='human-test',runs=[[y,50,80] for y in range(80,110)],area_pixels=900,area_um2=900*PX_UM**2)] if i==0 else []
 ms=dict(confirmed=True,kind='positive' if i==0 else 'negative',source_version=7,regions=len(manual),ignored_pixels=0)
 write(folder/'candidates.json',dict(m2=cs,m3=cs,manual=manual,manual_status=ms))
 cases.append(dict(scan_id=sid,source_identity='synthetic-'+str(i),animal='TEST',eye='OD',session_date='2000-01-01',day_label='TEST',queue_position=i+1,context_source='synthetic',context_notes='',training_scan=True,manual_status=ms,m2_count=1 if cs else 0,m3_count=1 if cs else 0,m2_hidden_count=1 if cs else 0,m3_hidden_count=1 if cs else 0,m2_pixels=400 if cs else 0,m3_pixels=400 if cs else 0,disagreement_pixels=0,canonical_crop_offset=0,status=[dict(model='v9_m'+str(m),prediction=fp,checkpoint=fp) for m in (2,3)]))
 media.append(dict(scan_id=sid,images=fp,bscan_display_limits=[0,64]))
write(out/'data.json',dict(cases=cases,selection_sha256='synthetic'));write(out/'media_manifest.json',dict(records=media))
