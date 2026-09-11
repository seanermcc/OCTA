"""Numbered figures derived from exported tables; no interpolation of measurements."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from .common import LAYERS,ORIENTATION,read,write,npz,save,fingerprint,sha,csvwrite
from .statistics import balanced,cohort
from .geometry import grid,transform

COLORS=['#202a44','#e69f00','#56b4e9','#009e73','#b65a9c','#0072b2','#d55e00','#817d23']
BANDS=['Interior','0–0.5D','0.5–1D','1–1.5D','1.5–2D','2–2.5D','2.5–3D']
GROUP=['region_definition','distance_basis','layer','band']

def cleaned(rows):
    d=rows.copy()
    for k in ['identity_eligible','normalized_eligible','post_d0','prelaser','complete_band','diameter_complete']:
        if k in d: d[k]=d[k].astype(str).str.lower().isin(['true','1'])
    for k in ['mean_thickness_um','day','band','onh_distance_um','onh_dx_um','onh_dy_um','diameter_um','fov_coverage']:
        if k in d: d[k]=pd.to_numeric(d[k],errors='coerce')
    return d

class Figures:
    def __init__(self,out):
        self.out=out; self.entries=[]; self.folder=out/'fig'; self.folder.mkdir(exist_ok=True)
        self.previous=read(out/'figure_manifest.json') if (out/'figure_manifest.json').exists() else []

    def add(self,fig,slug,caption,table,selection):
        number=len(self.entries)+1; name=f'{number:03d}_{slug}.png'
        fig.text(.5,.008,'Experimental thickness measurements; missing measurements remain blank.',ha='center',fontsize=8)
        fig.savefig(self.folder/name,dpi=140,bbox_inches='tight',facecolor='white'); plt.close(fig)
        if not Path(table).exists(): raise AssertionError('Figure table missing')
        self.entries.append(dict(number=number,file='fig/'+name,caption=caption,table=str(Path(table).relative_to(self.out)),
                                 selection=selection,table_sha256=sha(table)))

    def finish(self):
        text='# Figure captions\n\n'+ORIENTATION+'\n\n'
        for e in self.entries:
            text+=f"**{e['number']:03d}. {Path(e['file']).stem}** {e['caption']}\n\nSource: `{e['table']}`. Selection: {e['selection']}.\n\n"
        (self.out/'FIGURE_CAPTIONS.md').write_text(text,encoding='utf-8')
        current={e['file'] for e in self.entries}
        for entry in self.previous:
            old=(self.out/entry['file']).resolve()
            if entry['file'] not in current and old.is_relative_to(self.folder.resolve()): old.unlink(missing_ok=True)
        write(self.out/'figure_manifest.json',self.entries)
        # Verify decoding, dimensions, numbering, caption and source integrity.
        from PIL import Image
        checks=[]
        for e in self.entries:
            with Image.open(self.out/e['file']) as image:
                image.load(); size=image.size
                assert min(size)>300
            assert f"**{e['number']:03d}." in text
            assert sha(self.out/e['table'])==e['table_sha256']
            checks.append(dict(number=e['number'],size=list(size),table_verified=True,caption_verified=True,artifact=fingerprint(self.out/e['file'])))
        write(self.out/'verification/figures.json',dict(passed=True,figures=checks))

def distance_figure(figs,table,animal,source,raw):
    fig,axes=plt.subplots(2,4,figsize=(15,7),sharex=True)
    for k,(ax,layer) in enumerate(zip(axes.flat,LAYERS)):
        g=table[table.layer==layer].sort_values('band')
        if len(g):
            ax.plot(g.band,g.mean_thickness_um,'o-',color=COLORS[k])
            if 'ci_low_um' in g: ax.fill_between(g.band,g.ci_low_um,g.ci_high_um,color=COLORS[k],alpha=.18)
            for _,r in g.iterrows():
                if 'n_animals' in g: label=f"a{int(r.n_animals)} l{int(r.n_lesions)} v{int(r.n_animal_visits)}"
                else: label=f"l{int(r.n_lesions)} v{int(r.n_visits)}"
                ax.annotate(label,(r.band,r.mean_thickness_um),xytext=(0,6),textcoords='offset points',ha='center',fontsize=6)
        else:
            ax.text(.5,.5,'Unavailable',transform=ax.transAxes,ha='center',color='#666666')
            ax.set_yticks([])
        # Unmatched observations remain visible as faint points; they do not
        # contribute to the balanced line or its uncertainty interval.
        obs=raw[(raw.layer==layer)&raw.post_d0&raw.normalized_eligible]
        if animal!='cohort': obs=obs[obs.animal==animal]
        ax.scatter(obs.band,obs.mean_thickness_um,s=9,c='#999999',alpha=.22,zorder=0)
        partial=obs[~obs.complete_band]
        ax.scatter(partial.band,partial.mean_thickness_um,s=14,facecolors='none',edgecolors='#cc6600',alpha=.4)
        ax.set_title(layer); ax.set_ylabel('Thickness (µm)'); ax.set_xticks(range(7),BANDS,rotation=45,ha='right',fontsize=7); ax.grid(alpha=.15)
    fig.suptitle(f'{animal}: all eligible post-D0 visits\nBalanced means; orange outlines indicate partial bands',fontsize=13)
    fig.tight_layout(rect=(0,.04,1,.91))
    figs.add(fig,f'{animal}_distance',
        'Arithmetic thickness means balanced across repeats, visits, tracked lesions, eyes, and animals. '
        'Cohort intervals resample whole animals (95% percentile); fewer than two animals has no interval. '
        'Gray points include unmatched observations. Orange open points indicate incomplete field coverage. '
        'Labels give contributing animals (a), lesions (l), and visits (v); cohort visits are animal–visit counts.',
        source,f'{animal}; changing footprints, normalized distance, post-D0')

def schematic(figs,table,source,name):
    values=table.pivot(index='layer',columns='band',values='mean_thickness_um').reindex(index=LAYERS,columns=range(7))
    fig,ax=plt.subplots(figsize=(11,5)); im=ax.imshow(np.ma.masked_invalid(values.values),aspect='auto',cmap='viridis')
    ax.set_xticks(range(7),BANDS); ax.set_yticks(range(8),LAYERS); ax.set_title(f'{name}: schematic layer-by-distance averages')
    fig.colorbar(im,ax=ax,label='Thickness (µm)'); fig.tight_layout(rect=(0,.035,1,1))
    figs.add(fig,f'{name}_heatmap','Schematic averages; rows represent different layers and blank cells have no supported observations. No angular anatomy is implied.',source,name)
    xy=np.linspace(-3.5,3.5,301); xx,yy=np.meshgrid(xy,xy); radius=np.hypot(xx,yy)
    band=np.clip(np.ceil((radius-.5)/.5).astype(int),0,6)
    fig,axes=plt.subplots(2,4,figsize=(14,7))
    for ax,layer in zip(axes.flat,LAYERS):
        arr=values.loc[layer].values[band]; arr=np.where(radius<=3.5,arr,np.nan)
        im=ax.imshow(arr,extent=[-3.5,3.5,-3.5,3.5],origin='lower',cmap='viridis')
        ax.set_title(layer); ax.set_xlabel('Schematic x / D'); ax.set_ylabel('Schematic y / D'); fig.colorbar(im,ax=ax,shrink=.7)
    fig.suptitle(f'{name}: schematic concentric averages — circular interior radius 0.5D')
    fig.tight_layout(rect=(0,.03,1,.95))
    figs.add(fig,f'{name}_rings','Schematic concentric averages, not observed lesion anatomy. A circular equivalent-area interior (radius 0.5D) is followed by six outward half-diameter bands.',source,name)

def longitudinal(figs,d,out):
    normalized=d[(d.distance_basis=='normalized')&d.normalized_eligible]
    records=[]
    for (animal,definition),g in normalized.groupby(['animal','region_definition']):
        # Keep D0/prelaser separate in the figures, never treating D0 as prelaser.
        # A changing-footprint animal mean at one visit needs unique lesions
        # within that visit, not an asserted identity across visits. A single
        # annotated acquisition in an eye/visit supplies that local uniqueness.
        # Multiple unmatched acquisitions may be repeats and stay out of means.
        local_unique=g.groupby(['eye','visit_id']).scan_id.transform('nunique').eq(1)
        within_visit=local_unique & (definition=='changing')
        eligible=g[g.identity_eligible|within_visit].copy()
        local_only=~eligible.identity_eligible
        eligible.loc[local_only,'track_id']='visit_local:'+eligible.loc[local_only,'scan_id']+':'+eligible.loc[local_only,'lesion_id']
        if eligible.empty: continue
        categorical=g.day.isna().any()
        # Every observed visit belongs on the axis, including unmatched lesions
        # that cannot contribute to the balanced line but must remain visible.
        visit=g[['visit_id','day','day_label','day_basis','session_date']].drop_duplicates().sort_values('session_date')
        axis={r.visit_id:float(i if categorical else r.day) for i,(_,r) in enumerate(visit.iterrows())}
        # Same-day repeat acquisitions -> lesion visit -> eye -> animal for each day.
        keys=['visit_id','day_basis','layer','band']
        repeats=eligible.groupby(keys+['eye','track_id'],dropna=False).mean_thickness_um.mean().reset_index()
        eyes=repeats.groupby(keys+['eye'],dropna=False).mean_thickness_um.mean().reset_index()
        means=eyes.groupby(keys,dropna=False).mean_thickness_um.mean().reset_index()
        counts=repeats[np.isfinite(repeats.mean_thickness_um)].groupby(keys,dropna=False).track_id.nunique().reset_index(name='n_lesions')
        means=means.merge(counts,on=keys,how='left'); means['n_lesions']=means.n_lesions.fillna(0).astype(int)
        means['animal']=animal; means['region_definition']=definition
        means['identity_scope']='unique within eye/visit; cross-visit identities may be unmatched' if definition=='changing' else 'verified registered fixed tissue'
        records.extend(means.to_dict('records'))
        path=out/'tables'/f'longitudinal_{animal}_{definition}.csv'; means.to_csv(path,index=False)
        for full in (True,False):
            fig,axes=plt.subplots(2,4,figsize=(15,8)); axes.flat[-1].axis('off')
            for band,ax in enumerate(axes.flat[:7]):
                layers=['Full retina'] if full else LAYERS[1:]
                for layer in layers:
                    m=means[(means.band==band)&(means.layer==layer)].copy(); m['x']=m.visit_id.map(axis); m=m.sort_values('x')
                    ax.plot(m.x,m.mean_thickness_um,'o-',color=COLORS[LAYERS.index(layer)],label=layer,markersize=3)
                    if full:
                        # All lesion/visit observations, including unmatched, are visible.
                        pts=g[(g.band==band)&(g.layer==layer)].copy()
                        pts['point_track']=np.where(pts.identity_eligible,pts.track_id,pts.scan_id+':'+pts.lesion_id)
                        pts=pts.groupby(['visit_id','point_track']).mean_thickness_um.mean().reset_index()
                        ax.scatter(pts.visit_id.map(axis),pts.mean_thickness_um,s=12,color='#999999',alpha=.5)
                        for _,r in m.iterrows(): ax.annotate(f'n={r.n_lesions}',(r.x,r.mean_thickness_um),fontsize=7,xytext=(0,5),textcoords='offset points')
                for _,v in visit.iterrows():
                    pre=g[g.visit_id==v.visit_id].prelaser.any()
                    if pre or v.day==0: ax.axvline(axis[v.visit_id],color='#777777',ls=':',alpha=.5)
                labels=[f'{r.day_label}\n{r.day_basis}' if categorical else f'{r.day:g}\n{r.day_basis}' for _,r in visit.iterrows()]
                if not full:
                    for j,(_,v) in enumerate(visit.iterrows()):
                        ns=means[(means.visit_id==v.visit_id)&(means.band==band)].set_index('layer').n_lesions
                        labels[j]+='\nn='+('/'.join(str(int(ns.get(layer,0))) for layer in LAYERS[1:]))
                ax.set_xticks([axis[r.visit_id] for _,r in visit.iterrows()],labels,rotation=45,ha='right',fontsize=7)
                ax.set_title(BANDS[band]); ax.set_ylabel('Thickness (µm)'); ax.grid(alpha=.15)
            handles,labels=axes.flat[0].get_legend_handles_labels(); axes.flat[-1].legend(handles,labels,loc='center',fontsize=9)
            kind='full_retina' if full else 'other_layers'
            fig.suptitle(f'{animal} — {definition} regions — {kind.replace("_"," ")}\n'+('Categorical visits; timing unresolved' if categorical else 'Day after laser (basis shown at each visit)')+('' if full else '\nCounts n follow legend layer order'),fontsize=12)
            fig.tight_layout(rect=(0,.04,1,.92))
            figs.add(fig,f'{animal}_{definition}_{kind}',
                'Every available lesion–visit mean is shown for full retina; lines balance repeat observations and eyes. '
                'Other-layer panels contain seven colored mean lines. Dashed markers identify separately retained D0/prelaser observations; D0 is not assumed prelaser. '
                'Unresolved month labels remain categorical. Lesion counts are recorded per layer and band in the source table. '
                'Changing-region mean lines use unique lesions within each eye/visit: a single annotated acquisition can support that visit mean without claiming identity across visits. Multiple unmatched acquisitions in a visit remain excluded from the line. '
                'Fixed regions can appear without a new outline; missing detections do not establish disappearance.',path,f'{animal}; {definition}')
    csvwrite(out/'tables/longitudinal_means.csv',records)

def onh_figures(figs,d,out):
    g=d[(d.region_definition=='changing')&(d.distance_basis=='normalized')&d.normalized_eligible&d.onh_distance_um.notna()]
    path=out/'tables/onh_descriptive.csv'; g.to_csv(path,index=False)
    if g.empty: return
    for band in range(7):
        fig,axes=plt.subplots(2,4,figsize=(14,7))
        for k,(ax,layer) in enumerate(zip(axes.flat,LAYERS)):
            s=g[(g.band==band)&(g.layer==layer)]
            for animal,a in s.groupby('animal'): ax.scatter(a.onh_distance_um,a.mean_thickness_um,label=animal,s=16,alpha=.7)
            ax.set_title(layer); ax.set_xlabel('Lesion centroid → ONH center (µm)'); ax.set_ylabel('Thickness (µm)')
        handles,labels=axes.flat[0].get_legend_handles_labels(); fig.legend(handles,labels,loc='lower center',ncol=5,fontsize=8)
        fig.suptitle(f'ONH distance association: {BANDS[band]} — descriptive'); fig.tight_layout(rect=(0,.08,1,.95))
        figs.add(fig,f'onh_distance_band_{band}','Descriptive lesion-centroid distance associations, separated by band; day, lesion diameter, eye, localization uncertainty, and identity status remain in the source table.',path,f'band={band}')
    fig,axes=plt.subplots(2,4,figsize=(14,7)); sectors=['D*','V*','N*','T*']
    for k,(ax,layer) in enumerate(zip(axes.flat,LAYERS)):
        for band in range(1,7):
            s=g[(g.layer==layer)&(g.band==band)]
            # Descriptive mean per animal and sector, then equal animal weight.
            b=balanced(s,['dvnt_sector'])
            vals=b.groupby('dvnt_sector').mean_thickness_um.mean().reindex(sectors) if not b.empty else pd.Series(np.nan,index=sectors)
            ax.plot(range(4),vals,'o-',label=BANDS[band],markersize=3)
        ax.set_title(layer); ax.set_xticks(range(4),sectors); ax.set_ylabel('Thickness (µm)')
    handles,labels=axes.flat[0].get_legend_handles_labels(); fig.legend(handles,labels,loc='lower center',ncol=6,fontsize=8)
    fig.suptitle('Surrounding thickness by provisional DVNT sector\n'+ORIENTATION,fontsize=10); fig.tight_layout(rect=(0,.08,1,.9))
    figs.add(fig,'dvnt_sectors','Equal-animal sector summaries, balanced within animals. '+ORIENTATION,path,'post-D0; surroundings, bands 1–6')
    fig,axes=plt.subplots(2,4,figsize=(14,7))
    for ax,layer in zip(axes.flat,LAYERS):
        s=g[(g.layer==layer)&(g.band==1)]
        scatter=ax.scatter(s.onh_dx_um,-s.onh_dy_um,c=s.mean_thickness_um,cmap='viridis',s=30)
        ax.scatter([0],[0],marker='+',c='black'); ax.set_aspect('equal'); ax.set_title(layer)
        ax.set_xlabel('T* ← x (µm) → N*'); ax.set_ylabel('V* ← y (µm) → D*'); fig.colorbar(scatter,ax=ax,shrink=.7,label='µm')
    fig.suptitle('ONH-centered lesion locations; color = first surrounding band\n'+ORIENTATION,fontsize=10)
    fig.tight_layout(rect=(0,.03,1,.9)); figs.add(fig,'onh_locations','Observed lesion centroids colored by mean thickness in the 0–0.5D surrounding band. '+ORIENTATION,path,'band=1')

def observed_maps(figs,runner,d):
    out=runner.out; records=read(out/'maps/index.json'); observed=[]
    # Show each measured outline in native-grid samples, centered and scaled by D.
    # Without verified registration, local image axes are retained only in this
    # individual panel; no angular pooling or anatomical orientation is asserted.
    for rec in records:
        if rec['definition']!='changing' or rec['basis']!='normalized' or not rec['diameter_complete']: continue
        sid=rec['scan_id']; geometry=npz(out/'maps'/f'{rec["map"]}.npz'); maps=npz(out/'thickness'/f'{sid}.npz')['exclude_unreliable_um']
        radius=np.linspace(-3.5,3.5,141); xx,yy=np.meshgrid(radius,radius)
        points=np.stack((xx,yy),axis=-1)*float(geometry['diameter_um'])+geometry['centroid_um']
        if rec['alignment_supported']:
            reg=read(out/'registration/registrations.json')[sid]
            rotation=np.array(reg['alignment']['matrix'])[:2,:2]
            points=(points-geometry['centroid_um'])@rotation+geometry['centroid_um']
        spacing=geometry['spacing_um_yx']; x=np.floor(points[...,0]/spacing[1]+.5).astype(int); y=np.floor(points[...,1]/spacing[0]+.5).astype(int)
        in_fov=(x>=0)&(x<maps.shape[2])&(y>=0)&(y<maps.shape[1])
        xc=np.clip(x,0,maps.shape[2]-1); yc=np.clip(y,0,maps.shape[1]-1)
        included=in_fov&(geometry['bands'][yc,xc]>=0)
        sampled=maps[:,yc,xc].copy(); sampled[:,~included]=np.nan
        coverage=np.isfinite(sampled).astype('uint8')
        name=rec['map']; save(out/'maps'/f'{name}_normalized.npz',thickness_um=sampled,valid_coverage=coverage,fov_coverage=in_fov,x_over_d=radius,y_over_d=radius)
        # A compact numeric table links each panel to the native measurement table.
        selection=d[(d.scan_id==sid)&(d.lesion_id==rec['lesion_id'])&(d.region_definition=='changing')&(d.distance_basis=='normalized')]
        table=out/'tables/spatial'/f'{name}.csv'; table.parent.mkdir(exist_ok=True); selection.to_csv(table,index=False)
        fig,axes=plt.subplots(4,4,figsize=(15,14))
        for k,layer in enumerate(LAYERS):
            ax=axes.flat[2*k]; im=ax.imshow(sampled[k],extent=[-3.5,3.5,3.5,-3.5],cmap='viridis'); ax.set_title(layer)
            fig.colorbar(im,ax=ax,shrink=.7,label='µm')
            cov=axes.flat[2*k+1]; cov.imshow(np.where(in_fov,coverage[k],np.nan),extent=[-3.5,3.5,3.5,-3.5],vmin=0,vmax=1,cmap='Greys'); cov.set_title('Valid coverage (white = missing)')
            for a in (ax,cov): a.set_xlabel('x / D'); a.set_ylabel('y / D')
        fig.suptitle(f'{sid}: {rec["lesion_id"]}\nObserved native-grid samples, diameter normalized\n'+(ORIENTATION if rec['alignment_supported'] else 'Local image axes only; angular alignment unavailable'),fontsize=11)
        fig.tight_layout(rect=(0,.02,1,.94))
        figs.add(fig,f'observed_{name}',
            'Observed lesion-centered thickness and companion valid-coverage maps. Nearest native pixels are sampled without smoothing or filling NaNs. '
            'Outside-FOV coverage is blank; missing or excluded in-FOV samples are white. Other lesion interiors and ONH tissue are excluded from rings. '
            'Angular axes follow verified eye alignment where available; otherwise only local image coordinates are shown.',table,f'scan={sid}; lesion={rec["lesion_id"]}')
        observed.append(dict(**rec,normalized_map=f'maps/{name}_normalized.npz'))
    write(out/'maps/observed_index.json',observed)

def build(runner):
    out=runner.out; path=out/'tables/lesion_visit_layer_band.csv'; d=cleaned(pd.read_csv(path))
    figs=Figures(out)
    if d.empty:
        figs.finish(); runner.status('figures',state='no_eligible_measurements'); return
    animal=balanced(d,GROUP)
    cohort_table=cohort(animal,GROUP,runner.c['bootstrap_samples'],runner.c['random_seed'])
    ap=out/'tables/animal_distance_summary.csv'; cp=out/'tables/cohort_distance_summary.csv'
    animal.to_csv(ap,index=False); cohort_table.to_csv(cp,index=False)
    complete=balanced(d[d.complete_band],GROUP)
    complete.to_csv(out/'tables/complete_band_animal_summary.csv',index=False)
    cohort(complete,GROUP,runner.c['bootstrap_samples'],runner.c['random_seed']).to_csv(out/'tables/complete_band_cohort_summary.csv',index=False)
    raw=d[(d.region_definition=='changing')&(d.distance_basis=='normalized')]
    if not animal.empty:
        selected=animal[(animal.region_definition=='changing')&(animal.distance_basis=='normalized')]
        for name,g in selected.groupby('animal'):
            distance_figure(figs,g,name,ap,raw); schematic(figs,g,ap,name)
        selected=cohort_table[(cohort_table.region_definition=='changing')&(cohort_table.distance_basis=='normalized')]
        if not selected.empty: distance_figure(figs,selected,'cohort',cp,raw); schematic(figs,selected,cp,'cohort')
    longitudinal(figs,d,out); onh_figures(figs,d,out); observed_maps(figs,runner,d)
    if runner.c['release']=='v2':
        ref=Path(runner.c['thickness_reference']); v1=cleaned(pd.read_csv(ref/'tables/lesion_visit_layer_band.csv'))
        matched=set(v1.scan_id)&set(d.scan_id)
        for name,subset in [('matched_scan',d[d.scan_id.isin(matched)]),('expanded_coverage',d[~d.scan_id.isin(matched)])]:
            a=balanced(subset,GROUP); a.to_csv(out/'tables'/f'{name}_animal_summary.csv',index=False)
            cohort(a,GROUP,runner.c['bootstrap_samples'],runner.c['random_seed']).to_csv(out/'tables'/f'{name}_cohort_summary.csv',index=False)
        balanced(v1[v1.scan_id.isin(matched)],GROUP).to_csv(out/'tables/matched_scan_v1_animal_summary.csv',index=False)
    figs.finish()
    files=[fingerprint(p) for folder in ['tables','maps','registration','fig','verification','code_snapshot'] for p in sorted((out/folder).rglob('*')) if p.is_file()]
    manifest=dict(version='cnv_analysis_v1.0',experimental=True,artifacts=files,
        configuration=fingerprint(out/'config.json'),frozen_inputs=fingerprint(out/'frozen_inputs.json'),
        code_revision=runner.code_revision,annotations=fingerprint(out/'provenance/annotations.json'),
        limitations=['octa-seg_v1 remains experimental; available-position policy is not validated acquisition quality.',
            'Photoreceptor composite includes ONL; isolated ONL is unavailable.',
            'Missing review is not absence; missing detection is not disappearance.',
            ORIENTATION,'Automatic cores partly depend on thickness; v2 thickness patterns are not independent detection validation.'])
    write(out/'reproducibility_manifest.json',manifest)
    write(out/'ANALYSIS_COMPLETE.json',dict(passed=True,release=runner.c['release'],figures=len(figs.entries),
        scans=int(d.scan_id.nunique()),animals=sorted(d.animal.unique()),measurement_rows=len(d),
        experimental=True,manifest=fingerprint(out/'reproducibility_manifest.json')))
    runner.status('complete',figures=len(figs.entries),scans=int(d.scan_id.nunique()))
