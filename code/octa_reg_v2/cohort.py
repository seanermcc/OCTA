"""All-sample execution of octa-reg_v2; frozen TS247 pilot is preserved."""
import os
for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[_key]='1'
from pathlib import Path
import argparse,itertools,json,time,traceback,warnings
from concurrent.futures import ProcessPoolExecutor,as_completed
import numpy as np
from scipy import ndimage as ndi
from skimage.feature import SIFT
from skimage.exposure import equalize_adapthist
from skimage.morphology import skeletonize
from .run import ROOT,BASE,read,write,sha,matrix,params,apply,sample,inside,candidate,refine,score
from .curves import coarse
from .cohort_graph import components,choose_root,center,assemble,CORNERS

DEFAULT_OUT=ROOT/'outputs/octa-reg_v2/all_samples'
VERSION='octa-reg_v2-cohort-1'

def load_group(group,output):
    records=[(p,read(p)) for p in sorted((BASE/'prepared').glob('*.json'))]
    records=[(p,i) for p,i in records if i['animal']+'_'+i['eye']==group]
    hashes={};scans=[]
    for path,info in records:
        hashes[str(path)]=sha(path)
        s=dict(info=info,excluded=bool(info.get('excluded_from_analysis')),blocked=None)
        if s['excluded']:scans.append(s);continue
        if info.get('status')!='prepared' or 'prepared_sha256' not in info:
            s['blocked']='Baseline preparation unavailable';scans.append(s);continue
        for source,expected in info['input_hashes'].items():
            h=sha(source)
            if h!=expected:raise ValueError('Baseline source changed: '+source)
            hashes[source]=h
        zp=path.with_suffix('.npz');h=sha(zp)
        if h!=info['prepared_sha256']:raise ValueError('Prepared data changed: '+str(zp))
        hashes[str(zp)]=h
        with np.load(zp) as z:
            im=z['enface'].copy();finite=np.isfinite(im);valid=finite&~z['registration_blocked']
            if im.shape!=(512,512) or not np.allclose(z['spacing'],[1460/512]*2):raise ValueError('Unsupported grid; preserve native calibration')
            if finite.sum()<100:s['blocked']='Insufficient finite optical data';scans.append(s);continue
            lo,hi=np.percentile(im[finite],[2,98]);im=np.clip((np.nan_to_num(im,nan=lo)-lo)/max(hi-lo,1e-6),0,1)
            vessel=z['vessel']&valid
        sk=skeletonize(vessel);sk[:8]=False;sk[-8:]=False;sk[:,:8]=False;sk[:,-8:]=False
        pts=np.argwhere(sk)[:,::-1].astype(float);pts=pts[::max(1,len(pts)//1500)]
        dt=ndi.distance_transform_edt(~sk).astype('float32');dt[~valid]=30
        s.update(image=im.astype('float32'),finite=finite,valid=valid,vessel=vessel,skel=sk,points=pts,dt=dt)
        scans.append(s)
    signature=dict(version=VERSION,group=group,scan_ids=[s['info']['scan_id'] for s in scans],sources=hashes,
        algorithms={str(p):sha(p) for p in [Path(__file__),Path(__file__).with_name('cohort_graph.py'),Path(__file__).with_name('run.py'),Path(__file__).with_name('curves.py')]})
    output.mkdir(parents=True,exist_ok=True);context=output/'cache_context.json'
    if context.exists() and read(context)!=signature:raise ValueError('Cache context changed. Choose a fresh --output directory; do not mix versions.')
    write(context,signature)
    return scans,signature

def extract(scans,out):
    folder=out/'features';folder.mkdir(exist_ok=True)
    for i,s in enumerate(scans):
        if s['excluded'] or s.get('blocked'):continue
        p=folder/f'{i:03d}.npz'
        if p.exists():
            with np.load(p) as z:s['kp']=z['points'].copy();s['desc']=z['descriptors'].copy()
            continue
        detector=SIFT(upsampling=1,c_dog=.008)
        try:
            detector.detect_and_extract(equalize_adapthist(s['image'],clip_limit=.015))
            pts=detector.keypoints[:,::-1].astype(float)
            near=ndi.distance_transform_edt(~s['vessel'])<18
            take=(sample(near.astype(float),pts,0)>.5)&(sample(s['valid'].astype(float),pts,0)>.5)&inside(pts,12)
            s['kp']=pts[take];s['desc']=detector.descriptors[take]
        except RuntimeError:
            s['kp']=np.empty((0,2));s['desc']=np.empty((0,128),np.uint8)
        np.savez_compressed(p,points=s['kp'],descriptors=s['desc'])

def descriptor_pair(a,b):
    if min(len(a['kp']),len(b['kp']))<5:return dict(accepted=False,matches=0,inliers=0,reason='Too few vessel-anchored features')
    m,e=candidate(a,b);r=dict(e,method='vessel-anchored SIFT + symmetric centerline refinement',accepted=False)
    if m is None or e['inliers']<5:return r
    first=score(a,b,m);refined=refine(a,b,m);s=score(a,b,refined)
    if s['score']>=first['score']:m=refined
    else:s=first
    r.update(s,matrix=m.tolist());r['accepted']=bool(e['inliers']>=7 and s['overlap']>=.18 and s['support']>=.57 and s['dice']>=.42 and s['span_px']>=23 and s['corr']>=.18)
    return r

def curve_pair(a,b):
    if min(len(a['points']),len(b['points']))<40:return dict(accepted=False,reason='Insufficient centerline observations')
    candidates=[]
    for correlation,m in coarse(a,b):
        m=refine(a,b,m);candidates.append(dict(**score(a,b,m),matrix=m.tolist(),coarse_correlation=correlation))
    # Extend the search through the complementary 180-degree orientation.
    # Existing rotations cover -90..90; flipping both array axes is a 180-degree
    # proposal, never an orientation change to the stored observations.
    flip=matrix([np.pi,511,511]);flipped={**a,'skel':a['skel'][::-1,::-1],'valid':a['valid'][::-1,::-1]}
    for correlation,m in coarse(flipped,b):
        m=refine(a,b,m@flip);candidates.append(dict(**score(a,b,m),matrix=m.tolist(),coarse_correlation=correlation))
    candidates.sort(key=lambda r:-r['score'])
    informative=[r for r in candidates if r['support']>=.64 and r['dice']>=.46 and r['corr']>=.20 and r['span_px']>=28 and r['overlap']>=.18]
    best=(informative or candidates)[0];p=params(np.array(best['matrix']))
    rivals=[r for r in informative if abs(np.arctan2(np.sin(params(np.array(r['matrix']))[0]-p[0]),np.cos(params(np.array(r['matrix']))[0]-p[0])))>.09 or np.linalg.norm(params(np.array(r['matrix']))[1:]-p[1:])>25]
    margin=best['score']-max((r['score'] for r in rivals),default=0)
    return dict(best,method='whole-vessel curves; full rotation search',accepted=bool(informative and margin>=.055),alternative_margin=margin,alternatives=[r for r in candidates if r is not best][:5])

def unique_accepted(pairs):
    unique={}
    for r in pairs:
        if not r.get('accepted'):continue
        k=(r['a'],r['b'])
        if k not in unique or r['score']>unique[k]['score']:unique[k]=r
    return sorted(unique.values(),key=lambda r:(-r['score'],r['a'],r['b']))

def progress(out,**kwargs):
    write(out/'progress.json',dict(group=out.name,updated=time.time(),**kwargs))

def run_group(group,root):
    out=Path(root)/group;t=time.time();scans,signature=load_group(group,out)
    nodes=[i for i,s in enumerate(scans) if not s['excluded'] and not s.get('blocked')]
    progress(out,stage='features',scans=len(scans));extract(scans,out)
    folder=out/'pairs';folder.mkdir(exist_ok=True);allpairs=[];descriptors={}
    for n,(a,b) in enumerate(itertools.combinations(nodes,2)):
        p=folder/f'{a:03d}_{b:03d}_descriptor.json'
        if p.exists():r=read(p)
        else:r=dict(a=a,b=b,**descriptor_pair(scans[a],scans[b]));write(p,r)
        allpairs.append(r);descriptors[(a,b)]=r
        if n%20==0:progress(out,stage='descriptor matches',completed=n+1,total=len(nodes)*(len(nodes)-1)//2)
    if not nodes:
        graph=assemble(scans,[],[])
    else:
        primary=choose_root(nodes,scans);done=set();searches=0
        # Work across components first. The pair with the strongest existing
        # feature evidence is attempted first; stop when the graph connects.
        while True:
            accepted=unique_accepted(allpairs);comps=components(nodes,accepted);membership={i:k for k,c in enumerate(comps) for i in c}
            if len(comps)<=1:break
            options=[(a,b) for a,b in itertools.combinations(nodes,2) if membership[a]!=membership[b] and (a,b) not in done]
            if not options:break
            a,b=max(options,key=lambda k:(descriptors[k].get('inliers',0),descriptors[k].get('matches',0),-(k[0]+k[1])))
            p=folder/f'{a:03d}_{b:03d}_curves.json'
            r=read(p) if p.exists() else dict(a=a,b=b,**curve_pair(scans[a],scans[b]))
            if not p.exists():write(p,r)
            allpairs.append(r);done.add((a,b));searches+=1
            if searches%5==0:progress(out,stage='vessel-curve recovery',searches=searches,components=len(comps))
        # Seek independent links for leaves: high-score false trunks can otherwise
        # look perfect in a spanning tree. Exhaust alternatives until degree 2.
        for i in nodes:
            while True:
                accepted=unique_accepted(allpairs);inc=[e for e in accepted if i in (e['a'],e['b'])]
                if len(inc)>=2:break
                used={(e['a'],e['b']) for e in inc}|done
                options=[tuple(sorted((i,j))) for j in nodes if j!=i and tuple(sorted((i,j))) not in used]
                if not options:break
                a,b=max(options,key=lambda k:(descriptors[k].get('inliers',0),descriptors[k].get('matches',0)))
                p=folder/f'{a:03d}_{b:03d}_curves.json';r=read(p) if p.exists() else dict(a=a,b=b,**curve_pair(scans[a],scans[b]))
                if not p.exists():write(p,r)
                allpairs.append(r);done.add((a,b));searches+=1
                if searches%5==0:progress(out,stage='cross-checking sparse links',searches=searches)
        accepted=unique_accepted(allpairs)
        preliminary=assemble(scans,accepted,allpairs)
        # Separate consensus tier for low-contrast images. Use only the fixed
        # overlap backbone as neighbors; no proposal can confirm itself.
        fixed={int(i):np.array(m) for i,m in preliminary['poses'].items() if preliminary['tiers'][i]=='supported'}
        for i in nodes:
            if preliminary['tiers'].get(str(i))=='supported':continue
            proposals=[]
            for e in allpairs:
                a,b=e['a'],e['b'];j=b if a==i else a
                if i not in (a,b) or j not in fixed or 'matrix' not in e:continue
                if e.get('support',0)<.64 or e.get('dice',0)<.55 or e.get('overlap',0)<.3 or e.get('span_px',0)<28:continue
                m=np.array(e['matrix']);pose=fixed[j]@(m if a==i else np.linalg.inv(m));proposals.append((j,pose,e))
            if not proposals:continue
            clusters=[[q for q in proposals if np.sqrt(np.mean((apply(CORNERS,p[1])-apply(CORNERS,q[1]))**2))<=12] for p in proposals]
            cluster=max(clusters,key=lambda c:len({q[0] for q in c}));cc,ck=center(scans[i]['info'])
            directional=cc is not None and preliminary['origin_kind']!='unresolved' and np.median([np.linalg.norm(apply(cc,q[1])) for q in cluster])<=55
            if len({q[0] for q in cluster})>=3 and directional:
                for j,pose,e in cluster:allpairs.append(dict(e,accepted=True,evidence_tier='geometry_consensus_low_contrast',method='multiple vessel overlaps + ONH convergence; intensity gate waived'))
        graph=assemble(scans,unique_accepted(allpairs),allpairs)
    # Thin records: no arrays enter JSON. Hashes preserve original evidence.
    metadata=[dict(s['info'],cohort_blocked=s.get('blocked')) for s in scans]
    data=dict(version=VERSION,group=group,policy='animal number + eye isolated; all dates pooled by user request',scans=metadata,graph=graph,
              descriptor_comparisons=len(descriptors),curve_searches=sum('coarse_correlation' in p for p in allpairs),seconds=time.time()-t)
    write(out/'registration.json',data);write(out/'pair_evidence.json',allpairs)
    for p,h in signature['sources'].items():
        if sha(p)!=h:raise ValueError('Source changed during run: '+p)
    counts={k:list(graph['tiers'].values()).count(k) for k in ['supported','uncertain','unlocalized','excluded']}
    progress(out,stage='complete',counts=counts,seconds=time.time()-t)
    return dict(group=group,total=len(scans),**counts,origin_kind=graph['origin_kind'],seconds=time.time()-t)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=DEFAULT_OUT);ap.add_argument('--workers',type=int,default=4);ap.add_argument('--groups',nargs='*');args=ap.parse_args()
    groups=sorted({r['animal']+'_'+r['eye'] for r in [read(p) for p in (BASE/'prepared').glob('*.json')]})
    if args.groups:groups=[g for g in groups if g in args.groups]
    args.output.mkdir(parents=True,exist_ok=True);write(args.output/'run_plan.json',dict(groups=groups,workers=args.workers,policy='OD/OS always separate; dates pooled',version=VERSION))
    results=[];failures=[]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        jobs={pool.submit(run_group,g,str(args.output)):g for g in groups}
        for future in as_completed(jobs):
            g=jobs[future]
            try:r=future.result();results.append(r);print(json.dumps(r),flush=True)
            except Exception as e:
                error=dict(group=g,error=str(e),traceback=traceback.format_exc());failures.append(error);write(args.output/g/'ERROR.json',error);print('FAILED',g,str(e),flush=True)
            write(args.output/'batch_status.json',dict(completed=results,failed=failures,total_groups=len(groups)))
    if failures:raise SystemExit(1)

if __name__=='__main__':main()
