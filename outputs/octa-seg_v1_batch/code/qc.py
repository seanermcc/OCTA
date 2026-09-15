"""Descriptive native-grid QC; no score, calibration, or accuracy inference."""
from batch import *

PERCENTILES=[1,5,25,75,95,99]
def stats(a,mask=None):
    a=np.asarray(a,dtype=float);a=a[np.isfinite(a)&(True if mask is None else mask)]
    d={k:None for k in ['mean','median','sd','iqr','mad','max']+[f'p{p:02d}' for p in PERCENTILES]};d['n']=len(a)
    if len(a):
        q=np.percentile(a,PERCENTILES);d.update({f'p{p:02d}':float(v) for p,v in zip(PERCENTILES,q)})
        d.update(mean=float(a.mean()),median=float(np.median(a)),sd=float(a.std(ddof=0)),iqr=float(q[3]-q[2]),mad=float(np.median(abs(a-np.median(a)))),max=float(a.max()))
    return d
def prefix(p,d):return {p+k:v for k,v in d.items()}
def describe(arr,eligible,p=''):
    a=np.asarray(arr);finite=np.isfinite(a);n=int(eligible.sum());native=a.size
    d=dict(native_n=native,eligible_n=n,finite_native_n=int(finite.sum()),finite_eligible_n=int((finite&eligible).sum()),coverage_native_pct=float(100*finite.mean()),coverage_eligible_pct=float(100*(finite&eligible).sum()/n) if n else None)
    d.update(stats(a,eligible))
    for axis,name in ((1,'aline'),(0,'bscan')):
        adj=np.diff(a,axis=axis);m=(eligible[:,1:]&eligible[:,:-1]) if axis==1 else (eligible[1:]&eligible[:-1])
        d.update(prefix(name+'_abs_jump_',stats(abs(adj),m)))
        d[name+'_eligible_adjacent_pairs']=int(m.sum())
    return prefix(p,d)
def geometry(a,k,offset,height,eligible,p):
    x=a[:,k];fin=np.isfinite(x);cross=np.zeros(x.shape,bool);comparable=np.zeros(x.shape,bool)
    for j in range(a.shape[1]):
        if j==k:continue
        valid=fin&np.isfinite(a[:,j]);comparable|=valid
        cross|=valid&((a[:,j]>=x) if j<k else (x>=a[:,j]))
    out=fin&((x<offset)|(x>offset+height-1));d={}
    for label,m in [('native',np.ones_like(eligible)),('eligible',eligible)]:
        n=int((fin&m).sum());pairs=int((comparable&m).sum())
        d.update({label+'_finite_n':n,label+'_out_of_crop_n':int((out&m).sum()),label+'_out_of_crop_pct':100*int((out&m).sum())/n if n else None,label+'_crossing_n':int((cross&m).sum()),label+'_crossing_comparable_n':pairs,label+'_crossing_pct':100*int((cross&m).sum())/pairs if pairs else None,label+'_invalid_geometry_n':int(((cross|out|~fin)&m).sum())})
    return prefix(p,d)

def run(sid):
    from octa_seg_v1.decisions import thickness,REASONS
    from eight_surface import provenance as P
    from eight_surface.config import SURFACE_NAMES,LAYER_DEFS
    o=directory(sid);done=o/'qc_complete.json'
    if done.exists():
        proof=read(done)
        for f in proof['artifacts']+proof['inputs']:verify(f)
        if proof.get('schema_version')==2:return
        done.unlink()
    e=engine();v=e.Volume(o,read(OUT/'launch_config.json'));d=v.d;g=v.g;r=record(sid)
    verify(read(o/'prepared.json')['source']);verify(read(o/'prepared.json')['geometry']);verify(read(o/'prepared.json')['images_fingerprint'])
    assert d['raw_position_branch'].shape==(512,8,512)
    assert d['probabilities'].shape==(512,8,2,512) and d['entropy'].shape==(512,8,512)
    assert np.isfinite(d['probabilities']).all() and ((d['probabilities']>=0)&(d['probabilities']<=1)).all()
    assert not np.isfinite(d['reported_positions'][d['state']!=1]).any()
    assert not np.isfinite(d['uncertain_estimates'][d['state']!=3]).any()
    assert set(np.unique(d['state'])).issubset({1,2,3})
    np.testing.assert_equal(thickness(d['reported_positions'],g['shadow']),d['primary_thickness_um'])
    pack=npz(OUT/'review_packs'/f'{sid}.npz');np.testing.assert_equal(pack['surfaces'],d['reported_positions']-v.offset);np.testing.assert_equal(pack['bscan_index'],np.arange(512));del pack
    for mode in (0,1):
        assert not np.isfinite(v.maps[mode][0][:,g['shadow']]).any()
        for b,x in [(0,0),(128,383),(256,256),(511,511)]:
            for k,point in enumerate(v.point(b,x,mode)):
                value=v.maps[mode][0][k,b,x]
                if np.isfinite(value):assert np.isclose(value,point['thickness_um']) and np.isclose(value,(point['bottom_full_px']-point['top_full_px'])*1.12)
                else:assert point['thickness_um'] is None
    excluded=np.isin(d['reason'],[7,8]).any(axis=1);visibility=np.full(d['state'].shape,P.MARK_UNKNOWN,np.int8);reliability=visibility.copy();human=[]
    for b,(path,lab) in v.index.records.items():
        visibility[b]=P.record_visibility(lab);reliability[b]=P.record_reliability(lab)
        excluded[b]|=lab['region_excluded']
        if lab['verdict']=='rejected':excluded[b]=True
        human.append(dict(scan_id=sid,bscan=b,path=str(path),sha256=fingerprint(path)['sha256'],verdict=lab['verdict'],local_provenance_available=bool(lab.get('local_provenance_available',False))))
    eligible=~excluded;layer_eligible=eligible&~g['shadow'];N=eligible.size
    save(o/'qc_masks.npz',excluded=excluded,boundary_eligible=eligible,layer_eligible=layer_eligible,human_visibility=visibility,human_reliability=reliability)
    boundaries=[]
    for k,name in enumerate(SURFACE_NAMES):
        s=d['state'][:,k];row=dict(scan_id=sid,boundary=name,model_assessment=True,native_n=N,eligible_n=int(eligible.sum()),excluded_n=int(excluded.sum()))
        for label,m in [('native',np.ones_like(eligible)),('eligible',eligible)]:
            den=int(m.sum())
            for value,word in [(1,'reported'),(2,'not_traceable'),(3,'uncertain')]:row[label+'_'+word+'_pct']=100*int(((s==value)&m).sum())/den if den else None
        for key,tag in [('raw_position_branch','raw'),('reported_positions','reported'),('uncertain_estimates','context')]:
            row.update(describe(d[key][:,k]*1.12,eligible,tag+'_um_'))
            row.update(geometry(d[key],k,v.offset,v.images.shape[1],eligible,tag+'_'))
        for h,tag in [(0,'model_traceability'),(1,'model_reliability')]:
            row.update(prefix(tag+'_native_',stats(d['probabilities'][:,k,h])))
            row.update(prefix(tag+'_eligible_',stats(d['probabilities'][:,k,h],eligible)))
        row.update(prefix('entropy_native_',stats(d['entropy'][:,k])));row.update(prefix('entropy_eligible_',stats(d['entropy'][:,k],eligible)))
        for mark,tag in [(P.MARK_YES,'yes'),(P.MARK_NO,'no'),(P.MARK_UNKNOWN,'unknown')]:
            row['human_visibility_'+tag+'_n']=int((visibility[:,k]==mark).sum());row['human_reliability_'+tag+'_n']=int((reliability[:,k]==mark).sum())
        for code,meaning in REASONS.items():row[f'reason_{code}_native_n']=int((d['reason'][:,k]==code).sum())
        boundaries.append(row)
    csvwrite(o/'boundary_qc.csv',boundaries);csvwrite(o/'human_judgments.csv',human,fields=['scan_id','bscan','path','sha256','verdict','local_provenance_available'])
    # One row per layer, with parallel segmentation and unchanged viewer-policy statistics.
    viewer_names={'Full retina':'TOTAL','Photoreceptor composite':'PHOTORECEPTOR','RPE band':'RPE'}
    viewer={viewer_names.get(n,n):k for k,(n,_,_) in enumerate(e.LAYERS)}
    layers=[];maps={}
    for k,name in enumerate(d['thickness_names'].tolist()):
        a=d['primary_thickness_um'][:,k];row=dict(scan_id=sid,layer=name,experimental=True,segmentation_policy='octa-seg_v1 reported endpoints; shadow excluded',preliminary_policy=e.POLICY,preliminary_mode='exclude_unreliable',missing_note='No finite endpoint pair is imputed; absence is not zero thickness')
        row.update(describe(a,layer_eligible,'segmentation_'));maps[('segmentation',name)]=a
        _,top,bottom=(LAYER_DEFS+[('INNER_RETINA','ILM','IPL_INL')])[k]
        top_idx=SURFACE_NAMES.index(top);bottom_idx=SURFACE_NAMES.index(bottom)
        row.update(shadow_native_n=int(g['shadow'].sum()),image_excluded_native_n=int(excluded.sum()),segmentation_missing_top_eligible_n=int((layer_eligible&~np.isfinite(d['reported_positions'][:,top_idx])).sum()),segmentation_missing_bottom_eligible_n=int((layer_eligible&~np.isfinite(d['reported_positions'][:,bottom_idx])).sum()),segmentation_negative_delta_eligible_n=int((layer_eligible&(d['reported_positions'][:,bottom_idx]<d['reported_positions'][:,top_idx])).sum()))
        if name in viewer:
            j=viewer[name];pilot=v.maps[0][0][j];row.update(describe(pilot,layer_eligible,'preliminary_'));maps[('preliminary',name)]=pilot
            row.update(describe(v.maps[1][0][j],layer_eligible,'preliminary_include_unreliable_'))
            row['preliminary_explicit_unreliable_n']=int(v.maps[1][1][j].sum())
            row['preliminary_missing_top_eligible_n']=int((layer_eligible&~np.isfinite(v.endpoints[0][:,top_idx])).sum())
            row['preliminary_missing_bottom_eligible_n']=int((layer_eligible&~np.isfinite(v.endpoints[0][:,bottom_idx])).sum())
        else:row['preliminary_unavailable_reason']='Not an existing octa-thick engine layer; no new measurement policy introduced'
        row['segmentation_status']='no finite measurements; unavailable' if row['segmentation_finite_eligible_n']==0 else 'preliminary automatic; reliability not validated'
        layers.append(row)
    for name in ['ONL','ELM','IS','OS','BM','IPL_S1','IPL_S2','IPL_S3']:
        layers.append(dict(scan_id=sid,layer=name,experimental=True,segmentation_status='unavailable',missing_note='Not separately resolved by frozen eight-boundary model; photoreceptor composite includes ONL/ELM/IS/OS; RPE outer edge is the existing endpoint',preliminary_policy=e.POLICY))
    csvwrite(o/'layer_qc.csv',layers)
    exp=OUT/'thick/exports'/f'{sid}_batch.npz';exp.parent.mkdir(parents=True,exist_ok=True);v.export(exp);write(exp.with_suffix('.json'),v.metadata())
    regional=[];regions={'eligible_nonexcluded':eligible,'automatic_shadow':g['shadow']&eligible,'cnv_footprint':g['cnv']&eligible,'vessel_footprint':g['vessel']&eligible,'other_eligible_outside_footprints':eligible&~(g['cnv']|g['vessel']|g['shadow'])}
    prep=read(o/'prepared.json')
    provenance={n:('automatic shadow proxy' if n=='automatic_shadow' else prep['footprints'].get('status','unknown') if n=='vessel_footprint' else 'saved CNV footprint; may be incomplete' if n=='cnv_footprint' and prep['enface_label'] else 'CNV annotation unavailable' if n=='cnv_footprint' else 'set operation on available masks') for n in regions}
    # Explicit region categories remain distinct from raw outlines and proposals.
    from cnv_review_v1.data import decode_mask
    for source in read(OUT/'launch_config.json').get('region_sources',[]):
        rp=Path(source)/f'{sid}_regions.json'
        if rp.exists():
            rr=read(rp);assert rr['scan_id']==sid and Path(rr['source_volume']).resolve()==Path(r['source']).resolve() and rr['native_shape']==[512,512]
            for reg in rr['regions']:
                name='human_region_'+reg['id']+'_'+reg['category'];regions[name]=decode_mask(reg['runs'],(512,512))&eligible;provenance[name]=str(rp)+'; '+reg['origin']
    for name,mask in regions.items():
        for (policy,layer),arr in maps.items():
            regional.append(dict(scan_id=sid,region=name,region_provenance=provenance[name],policy=policy,layer=layer,cnv_vessel_overlap_n=int((mask&g['cnv']&g['vessel']).sum()),**describe(arr,mask&~g['shadow'])))
    csvwrite(o/'region_layer_qc.csv',regional)
    region_rows=[]
    for name,mask in regions.items():
        n=int(mask.sum());row=dict(scan_id=sid,region=name,region_provenance=provenance[name],nonexcluded_region_n=n,shadow_n=int((mask&g['shadow']).sum()),shadow_pct=100*int((mask&g['shadow']).sum())/n if n else None,low_signal_pct=100*int((mask&g['low_signal']).sum())/n if n else None)
        row.update(prefix('local_cnr_',stats(g['local_cnr'],mask)))
        for value,word in [(1,'reported'),(2,'not_traceable'),(3,'uncertain')]:row['model_'+word+'_pct']=100*float((d['state'].transpose(0,2,1)[mask]==value).mean()) if n else None
        region_rows.append(row)
    csvwrite(o/'region_qc.csv',region_rows)
    acquisition=read(o/'acquisition_qc.json');scan={**acquisition,'native_n':N,'eligible_nonexcluded_n':int(eligible.sum()),'excluded_n':int(excluded.sum()),'shadow_native_pct':float(g['shadow'].mean()*100),'shadow_eligible_pct':float(g['shadow'][eligible].mean()*100) if eligible.any() else None,'model_reported_native_pct':float((d['state']==1).mean()*100),'model_uncertain_native_pct':float((d['state']==3).mean()*100),'model_not_traceable_native_pct':float((d['state']==2).mean()*100),'human_quality_rating':'','model_version':'octa-seg_v1','analysis_policy':e.POLICY,'completed':True}
    write(o/'scan_qc.json',scan)
    figures(sid,v,eligible)
    summary=f'# {sid}\n\nPreliminary automatic output; no accuracy claim. Native grid: 512 B-scans × 512 A-lines.\n\nAcquisition CNR: {acquisition["retina_cnr"]}; low-signal fraction: {acquisition["low_signal_frac"]}; shadow coverage: {scan["shadow_native_pct"]:.2f}%.\n\nModel reports {scan["model_reported_native_pct"]:.2f}% of boundary locations. Model traceability is not confirmed human visibility. {scan["excluded_n"]} native locations are excluded by human image judgments.\n\nThickness statistics use finite non-shadow, non-excluded locations, without filling gaps. Segmentation reporting and the existing preliminary thickness policy are separate columns. Spatial SD can reflect pathology and is not uncertainty. Isolated ONL and other unresolved sublayers are explicitly unavailable.\n\n[Diagnostic figure](diagnostic.png) · [Boundary state maps](boundary_states.png) · [Boundary QC](boundary_qc.csv) · [Layer QC](layer_qc.csv) · [Region QC](region_layer_qc.csv)\n'
    (o/'SUMMARY.md').write_text(summary,encoding='utf-8')
    inputs=[fingerprint(o/p) for p in ['measurements.npz','geometry.npz','images.npy','neural_complete.json','human_overrides_provenance.json']]+[fingerprint(p) for p in v.correction_hashes]
    for path,sha in v.correction_hashes.items():
        assert fingerprint(path)['sha256']==sha,'Human correction changed during QC; rerun QC against a consistent snapshot'
    for f in inputs:verify(f)
    files=['boundary_qc.csv','layer_qc.csv','region_layer_qc.csv','region_qc.csv','scan_qc.json','qc_masks.npz','diagnostic.png','boundary_states.png','SUMMARY.md']
    write(done,dict(schema_version=2,scan_id=sid,verified=True,checks=['all native B-scans/A-lines','full image equality during fresh inference or verified reuse','fresh orientation and crop offset','state and contextual masking','exact v1 thickness recomputation','actual octa-thick engine load/export','shadow NaNs in both engine modes','point/map native-coordinate units agreement','separate human visibility'],inputs=inputs,artifacts=[fingerprint(o/p) for p in files]+[fingerprint(exp),fingerprint(exp.with_suffix('.json'))],reused=bool(v.neural.get('reused',False))))

def figures(sid,v,eligible):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap,BoundaryNorm
    d=v.d;o=directory(sid)
    fig,axes=plt.subplots(3,3,figsize=(15,12),layout='constrained')
    colors=plt.cm.tab10(np.arange(8))
    for ax,b in zip(axes[0],[0,256,511]):
        img=v.images[b];ax.imshow(img,cmap='gray',aspect='auto',vmin=np.percentile(img,2),vmax=np.percentile(img,98))
        for k in range(8):
            ax.plot(d['raw_position_branch'][b,k]-v.offset,color=colors[k],alpha=.25,lw=.5)
            ax.plot(d['reported_positions'][b,k]-v.offset,color=colors[k],lw=.8)
            ax.plot(d['uncertain_estimates'][b,k]-v.offset,color=colors[k],lw=.8,ls=':')
        ax.set(title=f'Native B-scan {b}: raw faint / reported solid',xlabel='A-line',ylabel='Canonical cropped depth (px)',ylim=(img.shape[0]-.5,-.5))
    maps=[(v.enface,'Structural en-face','gray'),((d['state']==1).mean(axis=1)*100,'Reported boundaries (%)','viridis'),(np.mean(d['entropy'],axis=1),'Mean positional entropy','magma'),(v.maps[0][0][0],'Preliminary full retina (µm)','viridis'),(d['primary_thickness_um'][:,7],'Segmentation-reported total (µm)','viridis'),(v.g['shadow'].astype(float)+2*(~eligible),'Shadow (1), exclusion (2), overlap (3)','cividis')]
    for ax,(a,title,cmap) in zip(axes[1:].ravel(),maps):
        im=ax.imshow(a,cmap=cmap,aspect='equal');ax.set(title=title,xlabel='A-line',ylabel='B-scan')
        if np.isfinite(a).any():fig.colorbar(im,ax=ax,shrink=.8)
        else:ax.text(.5,.5,'No finite measurements\nunder this reporting policy',transform=ax.transAxes,ha='center',va='center')
    fig.suptitle(sid+'\nPreliminary automatic results; spatial variability is not uncertainty',fontsize=13)
    fig.savefig(o/'diagnostic.png',dpi=125);plt.close(fig)
    fig,axes=plt.subplots(2,4,figsize=(14,8),layout='constrained');cm=ListedColormap(['#31865b','#303846','#e9b44c']);norm=BoundaryNorm([.5,1.5,2.5,3.5],3)
    for k,ax in enumerate(axes.ravel()):ax.imshow(d['state'][:,k],cmap=cm,norm=norm);ax.set(title=str(d['surface_names'][k]),xlabel='A-line',ylabel='B-scan')
    fig.suptitle(sid+'\nModel assessment: green reported · charcoal not traceable · amber uncertain')
    fig.savefig(o/'boundary_states.png',dpi=125);plt.close(fig)

def aggregate():
    import msvcrt
    p=OUT/'locks/aggregate.lock';p.parent.mkdir(exist_ok=True)
    with p.open('a+b') as f:
        if f.tell()==0:f.write(b'0');f.flush()
        while True:
            try:f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1);break
            except OSError:time.sleep(.5)
        try:_aggregate()
        finally:f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)

def _aggregate():
    from scan_quality import add_repeat_agreement
    import msvcrt
    m=manifest();scans=[];bs=[];ls=[];rs=[];rqs=[];ready=[];fps={};failed=[];reused=[]
    for r in m['scans']:
        sid=r['scan_id'];o=directory(sid)
        # Read a consistent scan snapshot while QC may refresh its marker/tables.
        # Lock order is aggregate -> scan; scan workers never aggregate in-lock.
        with (OUT/'locks'/f'{sid}.lock').open('a+b') as scan_lock:
            if scan_lock.tell()==0:scan_lock.write(b'0');scan_lock.flush()
            while True:
                try:scan_lock.seek(0);msvcrt.locking(scan_lock.fileno(),msvcrt.LK_NBLCK,1);break
                except OSError as exc:
                    if exc.errno not in (11,13):raise
                    time.sleep(.2)
            try:
                if (o/'qc_complete.json').exists():
                    proof=read(o/'qc_complete.json')
                    scans.append(read(o/'scan_qc.json'));bs+=csvread(o/'boundary_qc.csv');ls+=csvread(o/'layer_qc.csv');rs+=csvread(o/'region_layer_qc.csv');ready.append(str(o));fps[sid]=npz(o/'acquisition_fingerprint.npz')['fingerprint']
                    if (o/'region_qc.csv').exists():rqs+=csvread(o/'region_qc.csv')
                    if proof.get('reused'):
                        reused.append(dict(scan_id=sid,**{k:v for k,v in read(o/'neural_complete.json').items() if k.startswith('reuse')}))
                elif (OUT/'failures'/f'{sid}.json').exists():failed.append(read(OUT/'failures'/f'{sid}.json'))
            finally:scan_lock.seek(0);msvcrt.locking(scan_lock.fileno(),msvcrt.LK_UNLCK,1)
    add_repeat_agreement(scans,fps)
    if scans:csvwrite(OUT/'scan_qc.csv',scans)
    if bs:csvwrite(OUT/'boundary_qc.csv',bs)
    if ls:csvwrite(OUT/'layer_qc.csv',ls)
    if rs:csvwrite(OUT/'region_layer_qc.csv',rs)
    if rqs:csvwrite(OUT/'region_qc.csv',rqs)
    csvwrite(OUT/'failures.csv',failed,fields=['scan_id','stage','exit_code','log','investigated'])
    write(OUT/'thick/volumes.json',ready)
    write(OUT/'reused_artifacts.json',reused)
    counts=dict(expected=len(m['scans']),completed=len(ready),reused=len(reused),failed=len(failed),unavailable=len(m['unavailable']),pending=len(m['scans'])-len(ready)-len(failed))
    write(OUT/'counts.json',counts)
    complete=counts['pending']==0 and counts['failed']==0
    report=f'''# Frozen octa-seg_v1 acquisition batch

Status: {'complete' if complete else 'processing; not complete'}. Preliminary automatic results for review; no new validation or accuracy claim.

Expected available: {counts['expected']}; completed and QC verified: {counts['completed']}; verified raw-neural reuse within completed scans: {counts['reused']}; failed: {counts['failed']}; unavailable: {counts['unavailable']}; pending: {counts['pending']}.

Every available repeat, eye and visit is included. See `reconciliation.json`, `acquisitions.csv`, `unavailable_acquisitions.csv` and `failures.csv`. Completion requires both segmentation and QC markers. Unavailable RAW is never reconstructed here.

## Results

- `scan_qc.csv`: acquisition axes and separate model coverage; repeat disagreement is interpretable only when repeat_comparable is true. Repeat groups remain provisional until the batch is complete.
- `boundary_qc.csv`: one row per acquisition/boundary, model probabilities and entropy, native and eligible coverage, geometry and adjacent jumps.
- `layer_qc.csv`: one row per acquisition/layer; separate segmentation and unchanged octa-thick policies, plus explicitly unavailable layers.
- `region_layer_qc.csv`: region-stratified statistics, with provenance and overlap counts.
- `volumes/<scan>/SUMMARY.md`, `diagnostic.png`, `boundary_states.png`: per-scan review.
- `qualitative_ratings.csv`: human Good / Usable / Poor / Unsure ratings and comments; blank until explicitly rated.
- `METRIC_DICTIONARY.md`: definitions, denominators, masking, interpretation and limitations.
- `thick/exports/`: native-grid thickness exports from the actual engine; `thick/volumes.json`: completed-volume selection.

## Verification and limitations

Each QC completion marker records input/artifact hashes and checks. Full native image grids are compared during inference; fresh orientation and canonical crop offsets are retained. The actual octa-thick engine loads every completed volume, verifies shadow masking and point/map units, and exports both existing modes. Model checkpoints and dependency files are fingerprinted. Source identity uses file size, mtime and three 1-MiB SHA-256 samples, not a full-source cryptographic digest.

The experimental model's traceability/reliability values are model assessments, not calibrated correctness or human visibility. Human visibility is separately counted. SD/IQR/MAD measure spatial variation, which may include genuine CNV pathology. Vessel proposals and automatic shadows are not human annotations. Footprint groups may overlap; “other” is their complement, not confirmed normal retina. No combined quality score or quality-based exclusions are introduced. Isolated ONL and unresolved sublayers remain explicitly unavailable.

## Anaconda Prompt commands

Open the completed portion (all volumes after completion):
```bat
conda activate octa
cd /d G:\\OCT_TreeShrew\\octa
call outputs\\octa-thick_v1\\octa-thick_batch_v1.cmd
```

Resume all remaining stages, retrying failures:
```bat
conda activate octa
cd /d G:\\OCT_TreeShrew\\octa
call outputs\\octa-seg_v1_batch\\RUN_ALL.cmd
```

Rebuild tables and compare subsequently supplied human ratings:
```bat
call outputs\\octa-seg_v1_batch\\BATCH.cmd aggregate
```
'''
    (OUT/'REPORT.md').write_text(report,encoding='utf-8')
    if complete:write(OUT/'COMPLETE.json',counts);write(OUT/'status.json',dict(status='complete',**counts))
