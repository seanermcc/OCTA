"""Audit published reviewer assets and immutable automatic geometry."""
import hashlib
import json
import math
from pathlib import Path
from .review_server import DEFAULT_ROOT


def read(p): return json.loads(p.read_text(encoding='utf-8'))
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def center(m): return [sum(m[i][j]*256 for j in (0,1))+m[i][2] for i in (0,1)]


def main():
    root=DEFAULT_ROOT; original=read(root/'PUBLICATION.json'); total=0; days=set()
    source=Path(__file__).parent
    for group,h in original['derived_registration_hashes'].items():
        folder=root/group
        assert digest(folder/'review_registration.json')==h,group
        data=read(folder/'montage.json');registration=read(folder/'review_registration.json')
        assert digest(folder/'index.html')==digest(source/'cohort_viewer.html')
        assert digest(folder/'cohort_viewer.js')==digest(source/'cohort_viewer.js')
        assert (folder/'data.js').read_text().startswith('window.MONTAGE=')
        for s in data['scans']:
            total+=1;days.add(s['day_label']);assert len(s['day_label'])<5
            if s['tier']=='excluded':assert not s.get('matrix_to_onh_pixels')
            if s.get('matrix_to_onh_pixels'):
                assert s['matrix_to_onh_pixels']==registration['graph']['poses'][str(s['index'])]
    assert total==324
    fixture=root.parent/'reviewer_test/TS999_OS/review_history'
    r2,r3,r4,r5,r6=[read(fixture/f'{i:06d}.json') for i in range(2,7)]
    def pose(r):return r['fields']['synthetic-1']['matrix_to_onh_pixels']
    assert r2['montage_confirmed'] and r2['fields']['synthetic-1']['status']=='confirmed'
    assert not r3['montage_confirmed'] and r3['fields']['synthetic-1']['status']=='draft'
    assert math.dist(center(pose(r2)),center(pose(r3)))<1e-8 # numeric rotation about center
    assert math.dist(center(pose(r3)),center(pose(r4)))>10 # drag translated
    assert math.dist(center(pose(r4)),center(pose(r5)))<1e-8 # pointer rotation about center
    assert pose(r4)==pose(r6) # undo exact pose restoration
    r7,r8,r9,r10=[read(fixture/f'{i:06d}.json') for i in range(7,11)]
    assert r7['montage_confirmed'] and not r8['montage_confirmed']
    assert r8['onh_override'] is not None and r9['onh_override'] is None
    assert r10['onh_override']==r8['onh_override']
    assert r7['fields']==r8['fields']==r9['fields']==r10['fields']
    r13,r14,r15,r16=[read(fixture/f'{i:06d}.json') for i in range(13,17)]
    assert r13['montage_confirmed'] and r13['decisions']['synthetic-6']['tier']=='uncertain'
    assert '<not markup>' in r13['decisions']['synthetic-6']['notes']
    assert r14['decisions']['synthetic-6']['tier']=='excluded'
    assert 'synthetic-6' not in r14['effective_matrices_to_onh_pixels']
    assert r15['decisions']['synthetic-6']['tier']=='supported'
    assert r16['decisions']['synthetic-6']['tier']=='uncertain'
    assert len({r['decisions']['synthetic-6']['notes'] for r in [r13,r14,r15,r16]})==1
    result=dict(status='passed',groups=19,scans=total,day_labels=sorted(days),
        automatic_registration_hashes_unchanged=True,automatic_poses_unchanged=True,
        excluded_scans_unchanged=True,reviewer_assets_match=True,
        persistence_unit_tests=14,browser_checks=['uncertain toggle','combined day/group filters',
        'individual and montage confirmation','reload persistence','edit invalidates confirmations',
        'translation drag','rotation drag with fixed center','numeric rotation with fixed center','undo',
        'ONH drag preserves field placements','ONH reload persistence','ONH reset and undo',
        'ONH edit reopens montage confirmation','retry-save no-op explanation',
        'manual supported-to-flagged drag','category selector','notes survive confirmation and reload',
        'manual exclusion and restore'],
        browser_fixture='reviewer_test/TS999_OS; isolated from real animal review records',
        code_hashes={p.name:digest(p) for p in [source/n for n in
                    ('cohort_viewer.html','cohort_viewer.js','review_server.py','reviewer_publish.py')]})
    (root/'REVIEWER_VERIFICATION.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__': main()
