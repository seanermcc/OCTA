"""Build a separate, offline v1/manual/v2 gallery from read-only release inputs."""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import shutil

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def scalar(z, key):
    return z[key].reshape(-1)[0].item()


def rename_model(text):
    for before, after in [
        ('Frozen v1 / new model', 'v1 / v2'),
        ('Original / v1 / new model', 'Original / v1 / v2'),
        ('New model only', 'v2 only'), ('Frozen v1 only', 'v1 only'),
        ('Final model · all eligible labels', 'v2 · all eligible labels'),
        ('Frozen v1 · green is human ONH', 'v1 · green is human ONH'),
        ('Used in final model training', 'Used in v2 training'),
        ('Same animal as final training', 'Same animal as v2 training'),
        ('Animal absent from final training', 'Animal absent from v2 training'),
        ('Final-model prediction', 'v2 prediction'),
        ('Final prediction arrays', 'v2 prediction arrays'),
    ]:
        text = text.replace(before, after)
    return text


def build(release, destination):
    release = release.resolve()
    destination = destination.resolve()
    if release == destination:
        raise ValueError('Build in a separate staging folder, then publish the verified files.')
    destination.mkdir(parents=True, exist_ok=True)
    raw = (release/'gallery-data.js').read_text(encoding='utf-8')
    payload = json.loads(raw.removeprefix('window.RELEASE=').strip().removesuffix(';'))
    items = payload['items']
    by_id = {i['scan_id']: i for i in items}
    assert len(by_id) == len(items) == 314
    labels = release.parent/'octo-vessel_onh_v1/labels'
    queue_path = release.parent/'octo-vessel_onh_v1/review_queue.json'
    queue = read(queue_path)
    assert queue['format'] == 'octa-vessel-gallery-flags-v1'
    queue_flags = {}
    for r in queue['scans']:
        assert r['scan_id'] in by_id
        assert type(r['vessel_issue']) is bool and type(r['onh_present']) is bool
        queue_flags[r['scan_id']] = dict(vessel_issue=r['vessel_issue'], onh_issue=r['onh_present'])
    shutil.copytree(release/'gallery_assets', destination/'gallery_assets', dirs_exist_ok=True)
    for name in ['gallery-data.js', 'START_HERE.md', 'metrics.json', 'protocol.json', 'exclusions.json']:
        shutil.copy2(release/name, destination/name)
    manual_dir = destination/'manual_gallery_assets'
    manual_dir.mkdir(exist_ok=True)
    provenance = []
    for item in items:
        item['manual'] = None
    for p in sorted(labels.glob('*_cnv.npz')):
        before_hash = sha(p)
        with np.load(p, allow_pickle=False) as z:
            sid = str(scalar(z, 'scan_id'))
            assert sid in by_id, sid
            item = by_id[sid]
            assert str(scalar(z, 'source_volume')) == item['source_volume'], sid
            assert tuple(z['native_shape']) == (512, 512), sid
            reviewed = z['reviewed_targets'].astype(bool)
            assert any(reviewed[1:]) or z['vasculature_brush_touched'].any() or z['onh_brush_touched'].any(), sid
            layers = {}
            for target, key, color in [('vessel', 'vasculature_mask', (20,175,255)), ('onh', 'onh_mask', (38,235,127))]:
                mask = z[key]
                assert mask.shape == (512,512) and mask.dtype == bool, (sid,key)
                rgba = np.zeros((512,512,4), np.uint8)
                rgba[mask,:3] = color
                rgba[mask,3] = 155
                path = manual_dir/f'{sid}_{target}.png'
                Image.fromarray(rgba).save(path, optimize=True)
                # Verify displayed mask coordinates and coverage against the source.
                assert np.array_equal(np.asarray(Image.open(path))[:,:,3] > 0, mask)
                layers[target] = path.relative_to(destination).as_posix()
            item['manual'] = layers
            item['manual_vessel_reviewed'] = bool(reviewed[1])
            item['manual_onh_reviewed'] = bool(reviewed[2])
            item['manual_onh_visibility'] = str(scalar(z, 'onh_visibility'))
            item['manual_revision'] = int(scalar(z, 'revision'))
            item['manual_notes'] = str(scalar(z, 'notes'))
            item['manual_labelled_at'] = str(scalar(z, 'labelled_at'))
        assert sha(p) == before_hash
        provenance.append(dict(scan_id=sid, path=str(p), sha256=before_hash, revision=item['manual_revision']))
    for item in items:
        item['queue_flags'] = queue_flags.get(item['scan_id'], {})
        item['comparison_group'] = 0 if item['manual'] else 1 if any(item['queue_flags'].values()) else 2
    items.sort(key=lambda item:item['comparison_group'])
    counts = {name:sum(i['comparison_group'] == group for i in items)
              for group,name in enumerate(['manual','flagged_without_manual','remaining'])}
    payload['comparison'] = dict(created_at=datetime.datetime.now().astimezone().isoformat(),
                                 counts=counts, queue_sha256=sha(queue_path), queue_source=str(queue_path))
    (destination/'manual-gallery-data.js').write_text('window.RELEASE='+json.dumps(payload,ensure_ascii=False).replace('</','<\\/')+';\n', encoding='utf-8')
    (destination/'v1_manual_v2.html').write_text((HERE/'manual_gallery_template.html').read_text(encoding='utf-8'), encoding='utf-8')
    original_index = release/'index_original_20260915.html.bak'
    if not original_index.exists():
        original_index = release/'index.html'
    shutil.copy2(original_index, destination/'index_original_20260915.html.bak')
    archived = rename_model(original_index.read_text(encoding='utf-8'))
    archived = archived.replace('<h1>Major vessels + ONH</h1>', '<h1>Major vessels + ONH · archived comparison</h1>')
    (destination/'index_archived_20260915.html').write_text(archived, encoding='utf-8')
    (destination/'index.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><title>Major vessels + ONH · v1 / manual / v2</title><meta http-equiv="refresh" content="0;url=v1_manual_v2.html"><p><a href="v1_manual_v2.html">Open v1 / manual / v2 comparison</a></p><p><a href="index_archived_20260915.html">Archived v1 / v2 comparison</a></p></html>\n', encoding='utf-8')
    (destination/'OPEN_GALLERY.cmd').write_text('@echo off\nstart "" "%~dp0v1_manual_v2.html"\n', encoding='utf-8')
    (destination/'manual_gallery_manifest.json').write_text(json.dumps(dict(
        **payload['comparison'], original_index_sha256=sha(original_index),
        release=str(release), total=len(items), annotations=provenance,
        panel_order=['v1','manual','v2'], unlabelled_panel_order=['v1','v2'],
        labels_unchanged=True),indent=2), encoding='utf-8')
    # Check every image link, including alternate held-out and frozen-human views.
    for item in items:
        assert (destination/item['original']).is_file()
        for mode in ['frozen','final','held','human','manual']:
            for path in (item.get(mode) or {}).values():
                assert (destination/path).is_file(), path
    print(json.dumps(dict(total=len(items), **counts, output=str(destination/'v1_manual_v2.html')), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    build(args.release, args.destination)
