"""Offline gallery; all display assets remain inside this release."""
import json
import numpy as np
from PIL import Image
from common import *

def overlay(path,mask,color):
    rgba=np.zeros((*mask.shape,4),np.uint8);rgba[mask,:3]=color;rgba[mask,3]=155
    Image.fromarray(rgba).save(path,optimize=True)

def assets_for_pair(sid,prefix,vessel,onh):
    paths={}
    for target,mask,color in [('vessel',vessel,(20,175,255)),('onh',onh,(38,235,127))]:
        path=HERE/'gallery_assets'/f'{sid}_{prefix}_{target}.png'
        if not path.exists():overlay(path,mask,color)
        paths[target]=path.relative_to(HERE).as_posix()
    return paths

def main():
    folder=HERE/'gallery_assets';folder.mkdir(exist_ok=True)
    inventory=read_json(HERE/'inventory.json');audit=read_json(HERE/'audit_manifest.json');protocol=read_json(HERE/'protocol.json')
    annotations={r['scan_id']:r for r in audit['annotations']};exclusions={r['scan_id']:r for r in read_json(HERE/'exclusions.json')}
    evaluated={r['scan_id']:r for r in read_json(HERE/'evaluation/per_scan_metrics.json')}
    settings=read_json(HERE/'final_settings.json')
    items=[]
    for i,row in enumerate(inventory):
        disk_check(700000)
        sid=row['scan_id'];original=folder/f'{sid}_original.jpg'
        if not original.exists():
            with np.load(row['projection_path'],allow_pickle=False) as z:gray=(normalized(z['structural_enface'])*255).round().astype(np.uint8)
            Image.fromarray(gray).save(original,quality=94,subsampling=0,optimize=True)
        with np.load(row['proposal_path'],allow_pickle=False) as z:
            frozen=assets_for_pair(sid,'v1',z['predicted_vasculature_mask'],z['human_onh_exclusion_mask'])
        r=read_json(HERE/'records'/f'{sid}.json')
        item=dict(scan_id=sid,animal=row['animal'],eye=row['eye'],session=row['session_date'],day=row['day_label'],days_post_laser=row['days_post_laser'],
                  original=original.relative_to(HERE).as_posix(),status=r['status'],frozen=frozen,
                  frozen_human_onh=row['frozen_human_onh_pixels']>0,model_training=sid in protocol['all_label_scans'],
                  animal_seen_in_training=row['animal'] in {x['animal'] for x in audit['annotations'] if x['vessel_eligible'] or x['onh_eligible']},
                  exclusion=exclusions.get(sid,{}).get('notes',''),source_volume=row['source_volume'],
                  prediction_file=r.get('prediction_file',''),final=None,human=None,held=None,fold_roles=[])
        if r['status']=='complete':
            with np.load(HERE/r['prediction_file'],allow_pickle=False) as z:item['final']=assets_for_pair(sid,'final',z['vessel_mask'],z['onh_mask'])
            item.update(vessel_pixels=r['vessel_pixels'],onh_pixels=r['onh_pixels'])
        if sid in annotations:
            a=annotations[sid]
            with np.load(HERE/a['supervision_file'],allow_pickle=False) as z:
                item['human']=assets_for_pair(sid,'human',z['human_vessel'],z['human_onh'])
                for j,target in enumerate(TARGETS):
                    p=folder/f'{sid}_support_{target}.png'
                    if not p.exists():
                        rgba=np.zeros((512,512,4),np.uint8)
                        rgba[z['positive'][j]]=[255,236,70,170];rgba[z['negative'][j]]=[242,115,45,170]
                        Image.fromarray(rgba).save(p,optimize=True)
                    item['human'][target+'_support']=p.relative_to(HERE).as_posix()
            item.update(vessel_reviewed=a['vessel_reviewed'],onh_reviewed=a['onh_reviewed'],onh_visibility=a['onh_visibility'],
                        vessel_eligible=a['vessel_eligible'],onh_eligible=a['onh_eligible'],vessel_scored_fraction=a['vessel_scored_fraction'],
                        onh_scored_fraction=a['onh_scored_fraction'],annotation_revision=a['revision'])
        if sid in evaluated:
            e=evaluated[sid]
            with np.load(HERE/e['prediction_file'],allow_pickle=False) as z:item['held']=assets_for_pair(sid,'held',z['vessel_mask'],z['onh_mask'])
            item.update(vessel_dice=e['vessel']['dice'],v1_dice=e['v1_vessel']['dice'],onh_dice=e['onh']['dice'],onh_false_detection=e['onh_false_detection'])
        for f in protocol['folds']:
            role='evaluation' if row['animal']==f['evaluation_animal'] else 'calibration' if row['animal']==f['calibration_animal'] else 'training' if row['animal'] in f['training_animals'] else 'unseen animal'
            item['fold_roles'].append(dict(model=f['name'],animal_role=role,scan_used=sid in sum(f['scans'].values(),[])))
        items.append(item)
        if (i+1)%50==0:progress('gallery',scans=i+1,total=314)
    write_json(HERE/'gallery_inventory.json',items)
    payload=dict(items=items,metrics=read_json(HERE/'metrics.json'),audit=audit['counts'],frozen_at=audit['frozen_at'],settings=settings)
    # External JS works on file:// too: no fetch dependency or local server required.
    (HERE/'gallery-data.js').write_text('window.RELEASE='+json.dumps(payload,ensure_ascii=False).replace('</','<\\/')+';\n',encoding='utf-8')
    template=(HERE/'gallery_template.html').read_text(encoding='utf-8')
    (HERE/'index.html').write_text(template,encoding='utf-8')
    progress('gallery_complete',scans=len(items),assets=len(list(folder.iterdir())))

if __name__=='__main__':main()
