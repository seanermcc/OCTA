"""Build navigation and a coverage report after the scientific run completes."""
from pathlib import Path
from collections import Counter
import html
import json
import hashlib
import pandas as pd

OUT = Path(__file__).resolve().parent

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(8*1024*1024), b''):
            h.update(b)
    return h.hexdigest()

def main():
    proof = read(OUT/'ANALYSIS_COMPLETE.json')
    assert proof['passed']
    figures = read(OUT/'figure_manifest.json')
    frozen = read(OUT/'frozen_inputs.json')
    inventory = read(OUT/'inventory.json')
    regs = read(OUT/'registration/registrations.json')
    d = pd.read_csv(OUT/'tables/lesion_visit_layer_band.csv')
    sources = read(OUT/'provenance/annotations.json')
    checked = {}
    for fp in sources:
        if fp['path'] not in checked:
            assert sha(fp['path']) == fp['sha256'], fp['path']
            checked[fp['path']] = True
    assert len(frozen['scans']) == 314
    assert len(d) == read(OUT/'measurement_complete.json')['rows']
    for e in figures:
        assert (OUT/e['file']).exists()
        assert sha(OUT/e['table']) == e['table_sha256']
    alignment = dict(Counter(r['alignment']['state'] for r in regs.values()))
    observations = d[['scan_id','lesion_id','region_definition']].drop_duplicates()
    metadata=[read(OUT/'thickness'/f'{sid}.json') for sid in frozen['scans']]
    assert all(m.get('exact_viewer_array_match') for m in metadata)
    animal_summary=pd.read_csv(OUT/'tables/animal_distance_summary.csv')
    normalized_animals=sorted(animal_summary[animal_summary.distance_basis.eq('normalized')].animal.unique().tolist())
    report = dict(passed=True, figures=len(figures), frozen_scans=len(frozen['scans']),
        analyzed_scans=int(d.scan_id.nunique()), measurement_rows=len(d),
        manually_annotated_scans=inventory['coverage']['scans_with_masks'],
        manual_footprints=inventory['coverage']['lesions'],
        animals=inventory['coverage']['animals'], registration_states=alignment,
        post_d0_summary_animals=sorted(animal_summary.animal.unique().tolist()),
        normalized_post_d0_summary_animals=normalized_animals,
        exact_viewer_array_checks=len(metadata),
        finite_measurement_rows_by_layer=d[d.mean_thickness_um.notna()].groupby('layer').size().to_dict(),
        source_annotation_files_unchanged=len(checked), final_batch_audit_performed=False,
        measured_observations_by_definition=observations.groupby('region_definition').size().to_dict())
    (OUT/'verification/full_run_results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    note = (
        f"Completed analysis: {len(figures)} figures; 314 frozen scan inputs; "
        f"{inventory['coverage']['lesions']} manual footprints in "
        f"{inventory['coverage']['scans_with_masks']} scans from "
        f"{len(inventory['coverage']['animals'])} animals.\n\n"
        f"The normalized post-D0 cohort plots include {len(normalized_animals)} animals. "
        "Clipped outlines remain in absolute-distance tables; prelaser outlines remain separate.\n\n"
        "The final batch audit was skipped as requested. Thickness measurements remain experimental. "
        "Only scans with existing manual outlines contribute changing-footprint measurements. "
        "Unverified cross-scan matches are excluded from tracked summaries; fixed-tissue plots currently "
        "contain reference observations and do not establish longitudinal tissue change. "
        "Changing-footprint visit means can describe independently outlined visits. "
        "Missing measurements remain blank."
    )
    index = '# CNV analysis figures\n\n' + note + '\n\n'
    index += '[Open the image gallery](<' + (OUT/'FIGURE_GALLERY.html').as_posix() + '>)\n\n'
    cards = []
    for e in figures:
        label = Path(e['file']).stem.replace('_',' ')
        absolute = (OUT/e['file']).as_posix()
        index += f"- [{label}](<{absolute}>)\n"
        cards.append(f'<article><a href="{html.escape(e["file"])}"><img loading="lazy" src="{html.escape(e["file"])}" alt="{html.escape(label)}"></a><h2>{html.escape(label)}</h2><p>{html.escape(e["caption"])}</p><a href="{html.escape(e["table"])}">Numerical table</a></article>')
    (OUT/'FIGURE_INDEX.md').write_text(index,encoding='utf-8')
    gallery = '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CNV analysis v1 figures</title><style>body{font:16px/1.5 system-ui;margin:30px auto;max-width:1600px;padding:0 24px;color:#213047;background:#f5f7fa}header{max-width:1050px}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(450px,1fr));gap:24px}article{background:white;padding:18px;border-radius:12px;box-shadow:0 2px 10px #0001}img{width:100%;height:auto}h2{font-size:16px;overflow-wrap:anywhere}p{font-size:14px}a{color:#1658a4}@media(max-width:520px){main{display:block}article{margin-bottom:24px}}</style><header><h1>CNV analysis v1</h1><p>' + html.escape(note).replace('\n\n','</p><p>') + '</p><p>Click any figure to open its full-resolution image. <a href="FIGURE_CAPTIONS.md">All captions</a></p></header><main>' + ''.join(cards) + '</main></html>'
    (OUT/'FIGURE_GALLERY.html').write_text(gallery,encoding='utf-8')
    guide=OUT/'START_HERE.md'; text=guide.read_text(encoding='utf-8')
    marker='## Completed results\n\n'
    if marker not in text:
        text=text.replace('## Analysis contract',marker+note+'\n\n[Figure index](FIGURE_INDEX.md) · [Image gallery](FIGURE_GALLERY.html) · [Captions](FIGURE_CAPTIONS.md)\n\n## Analysis contract')
        guide.write_text(text,encoding='utf-8')
    manifest_path=OUT/'reproducibility_manifest.json'
    manifest=read(manifest_path)
    def fingerprint(path):
        return dict(path=str(path),sha256=sha(path),bytes=path.stat().st_size)
    artifacts={e['path']:e for e in manifest['artifacts']}
    for name in ['verification/full_run_results.json','FIGURE_INDEX.md','FIGURE_GALLERY.html','START_HERE.md','finalize_results.py']:
        fp=fingerprint(OUT/name); artifacts[fp['path']]=fp
    manifest['artifacts']=sorted(artifacts.values(),key=lambda e:e['path'])
    manifest_path.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    proof['manifest']=fingerprint(manifest_path)
    (OUT/'ANALYSIS_COMPLETE.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))

if __name__ == '__main__':
    main()
