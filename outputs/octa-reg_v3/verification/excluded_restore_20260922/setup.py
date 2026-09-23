from pathlib import Path
import hashlib,json,shutil
from octa_reg_v3 import review_server as server
ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
targets=[(ROOT/'outputs/octa-reg_v2/all_samples'/g,'v2') for g in ('TS241_OD','TS241_OS')]
targets += [(ROOT/'outputs/octa-reg_v3'/g,'v3') for g in ('TS241_OD','TS241_OS')]
targets += [(ROOT/'outputs/octa-reg_v3/local_TS241_OD_20260922/TS241_OD','v3')]
hashfile=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
records={}
for folder,version in targets:
    for name in ('human_review.json','montage.json','data.js'):
        p=folder/name
        if p.exists():records[str(p)]=hashfile(p)
    # Deploy only the viewer script, never a registration or review file.
    shutil.copyfile(ROOT/f'code/octa_reg_{version}/cohort_viewer.js',folder/'cohort_viewer.js')
(OUT/'unchanged_data_hashes.json').write_text(json.dumps(records,indent=2))
folder=OUT/'fixture/TS241_OS';folder.mkdir(parents=True,exist_ok=False)
source=ROOT/'outputs/octa-reg_v2/all_samples/TS241_OS'
for name in ('montage.json','data.js','index.html'):
    shutil.copyfile(source/name,folder/name)
shutil.copytree(source/'assets',folder/'assets')
shutil.copyfile(ROOT/'code/octa_reg_v2/cohort_viewer.js',folder/'cohort_viewer.js')
data=server.load(folder/'montage.json');review=server.load(source/'human_review.json')
body=server.current(folder,data)
body.update(fields=review['fields'],decisions=review['decisions'],onh_override=review['onh_override'],montage_confirmed=True)
sid=data['scans'][0]['scan_id']
body['fields'][sid]={'matrix_to_onh_pixels':body['fields'].get(sid,{}).get('matrix_to_onh_pixels',data['scans'][0]['matrix_to_onh_pixels']),'status':'draft'}
body['decisions'][sid]={'tier':'excluded','notes':'Test only: keep this note after restoring'}
server.save(folder,data,body)
(OUT/'fixture_initial_review.json').write_text(json.dumps(server.current(folder,data),indent=2))
assert all(hashfile(Path(p))==h for p,h in records.items())
print('Deployed TS241 scripts; original registration/review hashes unchanged. Fixture:',folder)
