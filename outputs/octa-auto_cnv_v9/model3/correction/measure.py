"""Confirmed footprint areas and derived training targets; never writes labels."""
from common import *
from review_store import Store, targets, completion_kind, valid_confirmation
from scipy import ndimage as ndi
import csv, io

PX_UM=1460/512

def csv_write(path,rows,columns):
    path=destination(path);stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=columns)
    writer.writeheader();writer.writerows(rows)
    tmp=path.with_suffix('.tmp');tmp.write_text(stream.getvalue(),encoding='utf-8-sig');os.replace(tmp,path)

def lesion_measurements(state,shape):
    positive,background,ignored,_,_=targets(state,shape,require_complete=True)
    kept=[r for r in state['regions'] if r['state']=='kept']
    masks=[decode(r['runs'],shape)&~ignored for r in kept]
    coverage=np.zeros(shape,np.uint16)
    for m in masks:coverage+=m
    rows=[]
    for r,m in zip(kept,masks):
        y,x=np.nonzero(m);pixels=int(m.sum())
        if not pixels:continue
        edge=bool(m[0].any() or m[-1].any() or m[:,0].any() or m[:,-1].any())
        uncertainty=bool((ndi.binary_dilation(m,structure=np.ones((3,3)))&ignored).any())
        overlap=int((m&(coverage>1)).sum());n=ndi.label(m,structure=np.ones((3,3)))[1]
        area=pixels*PX_UM**2
        rows.append(dict(region_id=r['id'],origin=r['origin']['kind'],area_pixels=pixels,
            area_um2=area,area_mm2=area/1e6,equivalent_diameter_um=float(np.sqrt(4*area/np.pi)),
            bbox_width_um=float((x.max()-x.min()+1)*PX_UM),bbox_height_um=float((y.max()-y.min()+1)*PX_UM),
            touches_fov_edge=edge,touches_ignored=uncertainty,overlap_pixels=overlap,components=n,
            complete_size_eligible=not(edge or uncertainty or overlap or n!=1)))
    return rows,positive,background,ignored

def distribution(rows):
    values=np.array([r['area_um2'] for r in rows],float)
    if not len(values):return dict(n=0,min_um2=None,q25_um2=None,median_um2=None,q75_um2=None,max_um2=None,mean_um2=None)
    q=np.percentile(values,[0,25,50,75,100])
    return dict(n=len(values),**dict(zip(('min_um2','q25_um2','median_um2','q75_um2','max_um2'),map(float,q))),mean_um2=float(values.mean()))

def run(directory=None,output=None,synthetic=False):
    directory=Path(directory or HERE/'review/regions');output=Path(output or HERE/'reports/quantification')
    queue=read(HERE/'queue/queue.json')['acquisitions'];lesions=[];scans=[];training=[];errors=[]
    for a in queue:
        sid=a['scan_id'];path=directory/(sid+'.json')
        base={k:a[k] for k in ('scan_id','animal','eye','session_date','day_label','days_post_laser','preview_role','model3_training_exposure')}
        row=dict(base,status='pending',revision=None,confirmed_regions=None,total_area_pixels=None,total_area_um2=None,total_area_mm2=None,ignored_pixels=None)
        if path.exists():
            try:
                record_hash=sha(path);store=Store(a,directory,synthetic=synthetic)
                row.update(status=completion_kind(store.state,store.shape),revision=store.revision)
                if valid_confirmation(store.state):
                    rr,p,b,ig=lesion_measurements(store.state,store.shape)
                    for r in rr:lesions.append(dict(base,revision=store.revision,label_sha256=record_hash,**r))
                    row.update(confirmed_regions=len(rr),total_area_pixels=int(p.sum()),total_area_um2=float(p.sum()*PX_UM**2),total_area_mm2=float(p.sum()*PX_UM**2/1e6),ignored_pixels=int(ig.sum()))
                    target_path=destination(output/'targets'/f'{sid}_{record_hash[:16]}.npz')
                    if not target_path.exists():
                        tmp=target_path.with_suffix('.tmp')
                        with tmp.open('wb') as f:np.savez_compressed(f,target=p,known=p|b,ignored=ig,scan_id=np.array(sid),axis_order=np.array('B-scan,A-line'),label_sha256=np.array(record_hash))
                        os.replace(tmp,target_path)
                    training.append(dict(**base,revision=store.revision,label=fingerprint(path),targets=fingerprint(target_path),
                        source_identity=a['source_identity'],model3_provenance=a['model3_provenance'],
                        animal_split_group=a['animal'],visit_group=f'{a["animal"]}_{a["eye"]}_{a["session_date"]}'))
                if sha(path)!=record_hash:raise RuntimeError('Annotation changed during measurement; rerun')
            except Exception as exc:
                # Never publish a partially collected set if validation fails.
                errors.append(dict(scan_id=sid,error=str(exc)))
        scans.append(row)
    if errors:
        atomic(output/'FAILED.json',dict(at=now(),errors=errors));raise ValueError('Quantification failed validation: '+str(errors))
    complete=[r for r in lesions if r['complete_size_eligible']]
    finished=sum(s['status'] in ('positive','negative') for s in scans)
    summary=dict(generated_at=now(),acquisitions=len(queue),confirmed_images=finished,pending_images=len(queue)-finished,
        confirmed_positive_images=sum(s['status']=='positive' for s in scans),confirmed_negative_images=sum(s['status']=='negative' for s in scans),
        confirmed_lesion_regions=len(lesions),total_observed_cnv_area_um2=sum(s['total_area_um2'] or 0 for s in scans),
        visible_region_area_distribution=distribution(lesions),complete_lesion_size_distribution=distribution(complete),
        calibration=dict(x_um_per_pixel=PX_UM,y_um_per_pixel=PX_UM,status='approximate 1460 um field over 512 pixels'),
        interpretation='En-face footprint area. Sum across acquisitions is repeated observations, not unique biological lesions or tissue. Edge/uncertain/overlapping/disconnected regions excluded from complete-size distribution; all retained in lesion table.',
        cohort_complete=finished==len(queue),synthetic=synthetic)
    basecols=['scan_id','animal','eye','session_date','day_label','days_post_laser','preview_role','model3_training_exposure']
    csv_write(output/'lesions.csv',lesions,basecols+['revision','label_sha256','region_id','origin','area_pixels','area_um2','area_mm2','equivalent_diameter_um','bbox_width_um','bbox_height_um','touches_fov_edge','touches_ignored','overlap_pixels','components','complete_size_eligible'])
    csv_write(output/'scans.csv',scans,basecols+['status','revision','confirmed_regions','total_area_pixels','total_area_um2','total_area_mm2','ignored_pixels'])
    atomic(output/'training_manifest.json',dict(generated_at=now(),schema='derived-confirmed-targets-v1',synthetic=synthetic,records=training,
        policy='Use only these manifest entries, never glob targets. Whole-field confirmed only; unknown pixels ignored. No training launched.'))
    atomic(output/'summary.json',summary)
    destination(output/'FAILED.json').unlink(missing_ok=True)
    return summary

if __name__=='__main__':print(json.dumps(run(),indent=2))

