"""Readable entry figures from existing frozen results; no re-segmentation."""
from pathlib import Path
import json
import hashlib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT=Path(__file__).resolve().parent
LAYERS=['Full retina','RNFL','GCL','IPL','INL','OPL','Photoreceptor composite','RPE band']
COLORS=['#202a44','#e69f00','#56b4e9','#009e73','#b65a9c','#0072b2','#d55e00','#817d23']
BANDS=['Interior','0–0.5D','0.5–1D','1–1.5D','1.5–2D','2–2.5D','2.5–3D']

def read(p): return json.loads(p.read_text(encoding='utf-8'))
def fp(p): return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size)

def main():
    inv=read(OUT/'inventory.json'); frozen=read(OUT/'frozen_inputs.json')
    assert len(frozen['scans'])==len(inv['scans'])==314
    coverage=[]; provenance=[]
    for r in inv['scans']:
        meta=OUT/'thickness'/f"{r['scan_id']}.json"
        assert fp(meta)['sha256']==frozen['scans'][r['scan_id']]['metadata']['sha256']
        m=read(meta); total=int(np.prod(r['native_shape']))
        for layer,n in zip(LAYERS,m['finite_pixels']):
            coverage.append(dict(scan_id=r['scan_id'],animal=r['animal'],eye=r['eye'],layer=layer,
                grid_pixels=total,finite_pixels=n,available_percent=100*n/total,
                has_manual_cnv_outline=bool(r['lesion_count'])))
        provenance.append(fp(meta))
    cov=pd.DataFrame(coverage)
    cov.to_csv(OUT/'tables/segmentation_measurement_coverage.csv',index=False)
    summary=cov.groupby('layer').available_percent.agg(['median','min','max']).reindex(LAYERS)
    summary['scans_with_any_measurement']=cov[cov.finite_pixels>0].groupby('layer').scan_id.nunique().reindex(LAYERS,fill_value=0)
    summary.to_csv(OUT/'tables/segmentation_coverage_summary.csv')
    d=pd.read_csv(OUT/'tables/cohort_distance_summary.csv')
    d=d[d.region_definition.eq('changing')&d.distance_basis.eq('normalized')]
    fig=plt.figure(figsize=(15,10),facecolor='white')
    fig.suptitle('CNV thickness — cohort summary',x=.055,y=.98,ha='left',fontsize=24,fontweight='bold',color='#202a44')
    for x,num,desc in [(.055,'314','scans with segmentation outputs'),(.385,'19','scans with manual CNV outlines'),(.715,'7','animals in normalized cohort means')]:
        fig.text(x,.895,num,fontsize=29,fontweight='bold',color='#1658a4')
        fig.text(x,.866,desc,fontsize=12,color='#344054')
    gs=fig.add_gridspec(2,4,left=.065,right=.98,bottom=.155,top=.78,hspace=.55,wspace=.34)
    for k,layer in enumerate(LAYERS):
        ax=fig.add_subplot(gs[k//4,k%4]); g=d[d.layer.eq(layer)].sort_values('band')
        ax.plot(g.band,g.mean_thickness_um,'o-',lw=2,color=COLORS[k],markersize=5)
        ax.fill_between(g.band,g.ci_low_um,g.ci_high_um,color=COLORS[k],alpha=.18)
        ax.set_title(layer,fontsize=12,pad=10)
        ax.set_xticks(range(7),BANDS,rotation=40,ha='right',fontsize=8)
        ax.set_ylabel('Thickness (µm)',fontsize=10); ax.grid(alpha=.16)
        ax.spines[['top','right']].set_visible(False)
    fig.text(.065,.073,'Distance is measured outward from the CNV edge; D is equivalent-area lesion diameter.',fontsize=11)
    fig.text(.065,.045,'Equal animal weighting; shaded areas = 95% animal-bootstrap intervals. Partial fields contribute available tissue.',fontsize=10,color='#475467')
    fig.text(.065,.021,'Experimental measurements. Unverified lesion matches, clipped diameters and prelaser observations do not enter these means.',fontsize=9,color='#475467')
    fig.savefig(OUT/'SUMMARY.png',dpi=150); plt.close(fig)

    fig,ax=plt.subplots(figsize=(13,7),facecolor='white')
    rng=np.random.default_rng(417)
    for k,layer in enumerate(LAYERS):
        values=cov[cov.layer.eq(layer)].available_percent.to_numpy()
        ax.scatter(values,k+rng.uniform(-.19,.19,len(values)),s=9,alpha=.18,color=COLORS[k],edgecolors='none')
        med=np.median(values)
        ax.plot([med,med],[k-.27,k+.27],color='#202a44',lw=3)
        ax.text(102,k,f'{med:.0f}%',va='center',fontsize=11,fontweight='bold')
    ax.set_yticks(range(8),LAYERS); ax.invert_yaxis(); ax.set_xlim(-1,113)
    ax.set_xticks(range(0,101,20)); ax.set_xlabel('Recorded scan grid with an available thickness measurement (%)',labelpad=12)
    ax.set_title('Segmentation was run on all 314 scans\nUsable thickness coverage varies within each scan and layer',loc='left',fontsize=18,pad=23)
    ax.text(102,-.65,'Median',fontsize=10)
    ax.grid(axis='x',alpha=.15); ax.spines[['top','right']].set_visible(False)
    fig.text(.055,.052,'Each dot is one scan; dark ticks show the median across scans. Denominator = the full recorded en-face grid.',fontsize=10)
    fig.text(.055,.022,'Blank tissue can reflect shadows, exclusions, unavailable endpoints or invalid geometry. This is coverage, not accuracy.',fontsize=10,color='#475467')
    fig.subplots_adjust(left=.23,right=.96,bottom=.16,top=.80)
    fig.savefig(OUT/'SEGMENTATION_COVERAGE.png',dpi=150); plt.close(fig)

    text='# Summary and segmentation coverage\n\n'
    text+='[Cohort summary](SUMMARY.png) · [Segmentation coverage](SEGMENTATION_COVERAGE.png) · [All figures](FIGURE_INDEX.md)\n\n'
    text+='All 314 scan acquisitions have segmentation outputs and frozen thickness maps. These are acquisitions, not 314 distinct retinas. Only 19 scans had manual CNV outlines, giving 62 outlined observations from nine animals. Seven animals enter the normalized post-D0 cohort means: TS328 has only prelaser outlines and TS250 has a clipped outline. Clipped measurements remain in the absolute-distance tables.\n\n'
    text+='The observed lesion maps deliberately display only the outlined lesion and its surrounding distance bands. White gaps inside that displayed region retain missing or excluded measurements. They do not by themselves show that a scan was never processed.\n\n'
    text+='**SUMMARY.png:** Eight layer means versus distance beyond the lesion edge, from `tables/cohort_distance_summary.csv` (changing, normalized). Repeats, visits, tracked lesions, eyes and animals are balanced hierarchically. Shading is the 95% animal-cluster bootstrap interval. These are experimental results; the final batch audit was waived.\n\n'
    text+='**SEGMENTATION_COVERAGE.png:** Every scan contributes one dot per layer. Finite measurement counts come from the frozen per-scan viewer-export metadata and are divided by the full recorded grid size. This describes available measurements, not segmentation accuracy or retinal tissue coverage alone.\n\n'
    text+='Fixed-region plots currently contain reference observations only; no cross-visit fixed-tissue trajectory was verified. The changing-outline time courses can show independently outlined visits.\n'
    (OUT/'SUMMARY.md').write_text(text,encoding='utf-8')
    for name in ['FIGURE_INDEX.md','START_HERE.md']:
        path=OUT/name; old=path.read_text(encoding='utf-8')
        marker='<!-- overview-links -->'
        if marker not in old:
            first,rest=old.split('\n',1)
            links=f'\n\n{marker}\n**Start here:** [Cohort summary](SUMMARY.png) · [Segmentation coverage](SEGMENTATION_COVERAGE.png) · [What was included](SUMMARY.md)\n'
            path.write_text(first+links+rest,encoding='utf-8')
    gallery=OUT/'FIGURE_GALLERY.html'; old=gallery.read_text(encoding='utf-8')
    if 'SUMMARY.png' not in old:
        old=old.replace('<main>','<main><article><a href="SUMMARY.png"><img src="SUMMARY.png" alt="Cohort summary"></a><h2>Start here: cohort summary</h2><a href="SUMMARY.md">Scope and sources</a></article><article><a href="SEGMENTATION_COVERAGE.png"><img src="SEGMENTATION_COVERAGE.png" alt="Measurement coverage"></a><h2>How much of each layer was measurable?</h2></article>')
        gallery.write_text(old,encoding='utf-8')
    proof=dict(passed=True,scope='Existing frozen results and metadata; no rerun of segmentation or batch audit',metadata=provenance,
        cohort_source=fp(OUT/'tables/cohort_distance_summary.csv'),coverage_summary=summary.reset_index().to_dict('records'))
    (OUT/'verification/overview_sources.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
    manifest=read(OUT/'reproducibility_manifest.json'); entries={v['path']:v for v in manifest['artifacts']}
    for name in ['SUMMARY.png','SEGMENTATION_COVERAGE.png','SUMMARY.md','FIGURE_INDEX.md','FIGURE_GALLERY.html','START_HERE.md','tables/segmentation_measurement_coverage.csv','tables/segmentation_coverage_summary.csv','verification/overview_sources.json','make_overview.py']:
        entry=fp(OUT/name); entries[entry['path']]=entry
    manifest['artifacts']=sorted(entries.values(),key=lambda x:x['path'])
    manifest['supplementary_overviews']=['SUMMARY.png','SEGMENTATION_COVERAGE.png']
    (OUT/'reproducibility_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    completed=read(OUT/'ANALYSIS_COMPLETE.json'); completed['manifest']=fp(OUT/'reproducibility_manifest.json')
    completed['supplementary_overviews']=2
    (OUT/'ANALYSIS_COMPLETE.json').write_text(json.dumps(completed,indent=2),encoding='utf-8')
    print(summary.to_string())

if __name__=='__main__': main()
