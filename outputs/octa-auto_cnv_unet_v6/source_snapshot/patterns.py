"""Lesion/visit descriptive summaries; geometric interiors are never input channels."""
from common import *
from scipy import ndimage as ndi

def summary(values):
    a=values[np.isfinite(values)]
    if not len(a):return dict(median_um=None,q25_um=None,q75_um=None)
    q=np.percentile(a,[25,50,75]);return dict(median_um=float(q[1]),q25_um=float(q[0]),q75_um=float(q[2]))

def run():
    m=read(HERE/'data/manifest.json');rows=[];patterns=[];lesions=[];contrasts=[]
    for rec in m['scans']:
        sid=rec['scan_id'];d=npz(HERE/'data'/f'{sid}.npz');k=d['known'];target=d['target'];thick=d['thickness_um'];av=d['availability']
        signal=d['optical'][0];qs=np.quantile(signal,[.25,.5,.75]);sigbin=np.digitize(signal,qs)
        yy,xx=np.indices((512,512));edge=np.minimum.reduce([yy,xx,511-yy,511-xx])*UM
        # Match within scan by optical-signal quartile, automatic shadow/vessel, 4x4 location, edge distance bin.
        cell=(yy//128)*4+xx//128
        stratum=sigbin+4*d['shadow'].astype(int)+8*d['vessel'].astype(int)+16*cell+256*(edge<100).astype(int)
        outside=k&~ndi.binary_dilation(target,iterations=int(np.ceil(100/UM)))
        artifact=outside&(d['shadow']|d['vessel']|d['low_signal'])
        regions=[('reviewed_nonlesion',outside,-1,0),('artifact_rich_nonlesion',artifact,-1,0)]
        for i,mask in enumerate(d['instances']):
            if not mask.any():continue
            inside=ndi.distance_transform_edt(mask)*UM;dist=ndi.distance_transform_edt(~mask)*UM
            clipped=bool(mask[0].any() or mask[-1].any() or mask[:,0].any() or mask[:,-1].any())
            lesions.append(dict(scan_id=sid,visit=rec['day_label'],lesion=i,area_mm2=float(mask.sum()*UM**2/1e6),clipped=clipped,
                                interior_10_pixels=int((inside>10).sum()),interior_25_pixels=int((inside>25).sum()),interior_50_pixels=int((inside>50).sum())))
            ring=(dist>0)&(dist<=100)&k&~target
            regions.append(('perilesional_0_100um',ring,i,0))
            for erosion in [10,25,50]:
                interior=(inside>erosion)&mask
                regions += [('geometric_interior',interior,i,erosion),('footprint_edge',mask&~interior,i,erosion)]
            # Weighted stratum contrasts, so a dense pixel stratum does not manufacture independent subjects.
            for layer,(name,_,_) in enumerate(LAYERS):
                paired=[]
                for s in np.unique(stratum[mask]):
                    a=mask&(stratum==s);b=outside&(stratum==s)
                    if b.sum()<25:continue
                    paired.append((int(a.sum()),float(av[layer,a].mean()-av[layer,b].mean()),a,b))
                support=sum(p[0] for p in paired)
                thickness_pairs=[]
                for _,_,a,b in paired:
                    va=thick[layer,a];vb=thick[layer,b];va=va[np.isfinite(va)];vb=vb[np.isfinite(vb)]
                    if len(va)>=25 and len(vb)>=25:thickness_pairs.append((len(va),float(np.median(va)-np.median(vb))))
                measured_support=sum(n for n,_ in thickness_pairs)
                contrasts.append(dict(scan_id=sid,visit=rec['day_label'],lesion=i,layer=name,matched_fraction=support/int(mask.sum()),
                    availability_difference=sum(n*v for n,v,_,_ in paired)/support if support else None,
                    target_measurable_fraction=float(av[layer,mask].mean()),
                    matched_nonlesion_measurable_fraction=sum(n*float(av[layer,b].mean()) for n,_,a,b in paired)/support if support else None,
                    weighted_stratum_median_thickness_difference_um=sum(n*v for n,v in thickness_pairs)/measured_support if measured_support else None,
                    matched_observed_thickness_pixels=measured_support,
                    matching='same scan, signal quartile, shadow, vessel, 4x4 position cell, <100um FOV edge'))
        for region,mask,i,erosion in regions:
            count=int(mask.sum());base=dict(scan_id=sid,split=rec['split'],visit=rec['day_label'],eye=rec['eye'],lesion=i,region=region,erosion_um=erosion,pixels=count)
            for j,(name,_,_) in enumerate(LAYERS):
                rows.append(dict(**base,layer=name,measurable_fraction=float(av[j,mask].mean()) if count else None,
                    shadow_fraction=float(d['shadow'][mask].mean()) if count else None,
                    low_signal_fraction=float(d['low_signal'][mask].mean()) if count else None,
                    automatic_trace_denial_fraction=float(((d['reason_bits'][j,mask]&1)>0).mean()) if count else None,
                    invalid_geometry_fraction=float(((d['reason_bits'][j,mask]&2)>0).mean()) if count else None,**summary(thick[j,mask])))
            if count:
                codes=(~av[:,mask]).T.astype(int)@(1<<np.arange(8));unique,n=np.unique(codes,return_counts=True)
                for c,freq in zip(unique,n):patterns.append(dict(**base,missing_layer_bits=int(c),pixels_in_pattern=int(freq),fraction=float(freq/count)))
    csv_write(HERE/'patterns/regions_by_layer.csv',rows);csv_write(HERE/'patterns/missingness_combinations.csv',patterns)
    csv_write(HERE/'patterns/lesion_geometry.csv',lesions);csv_write(HERE/'patterns/matched_nonlesion_contrasts.csv',contrasts)
    # Equal-lesion within visit then equal-visit summaries, no pixel bootstrap or population inference.
    visits=[]
    for visit in sorted({r['visit'] for r in rows}):
        for name,_,_ in LAYERS:
            for region in ['geometric_interior','footprint_edge','perilesional_0_100um','artifact_rich_nonlesion']:
                group=[r for r in rows if r['visit']==visit and r['layer']==name and r['region']==region and r['erosion_um'] in (0,25) and r['measurable_fraction'] is not None]
                if group:visits.append(dict(visit=visit,layer=name,region=region,n_regions=len(group),mean_region_measurable_fraction=float(np.mean([r['measurable_fraction'] for r in group])),
                    median_of_available_region_medians_um=float(np.median([r['median_um'] for r in group if r['median_um'] is not None])) if any(r['median_um'] is not None for r in group) else None))
    csv_write(HERE/'patterns/visit_summaries.csv',visits)
    write(HERE/'patterns/method.json',dict(erosions_um=[10,25,50],interior='geometric only; not biological core',
        perilesional='0-100um exterior band excluding other lesions and unknown pixels; not assumed healthy',
        independence='Individual entries and visits; repeat lesion identity is unresolved; no pixel or animal-population inference',
        negative_matching='Within acquisition signal/shadow/vessel/location/edge strata; descriptive residual confounding remains',
        thickness_nan='No median when unavailable; measured fraction retained',human_regions_used_as_model_inputs=False))
    progress('Thickness pattern tables complete',lesion_entries=len(lesions),rows=len(rows))

if __name__=='__main__':run()
