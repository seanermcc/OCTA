"""Isolated TS267/TS328 longitudinal inference, versioned exports and viewers.

Uses the released v1 weights and v2 implementation without changing either
release. Each subprocess binds v2's output scope before importing its stages.
"""
from pathlib import Path
import argparse
import csv
import json
import os
import subprocess
import sys
import shutil

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'code'))
OUT = ROOT / 'outputs/longitudinal_assessment'
V2 = ROOT / 'outputs/octa-seg/octa-seg_v2'
V1 = ROOT / 'outputs/octa-seg/octa-seg_v1'


def cache_copy(source, dest):
    """Some dataset drives do not implement hard links; copy atomically there."""
    dest = Path(dest)
    if dest.exists(): return
    try:
        os.link(source, dest)
    except OSError:
        tmp = dest.with_suffix(dest.suffix+'.tmp')
        shutil.copyfile(source, tmp)
        tmp.replace(dest)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, data):
    path = Path(path)
    assert path.resolve().is_relative_to(OUT.resolve())
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(data, indent=2, default=str), encoding='utf-8')
    tmp.replace(path)


def initialize(repeats='one'):
    from batch_segment import scan_id_for
    from stage_a.common import fingerprint, verify
    dependency_path = OUT/'pipeline_dependencies.json'
    if dependency_path.exists():
        for fp in read(dependency_path): verify(fp)
    else:
        dependencies = list((V2/'code/octa_seg_v2').glob('*.py'))
        dependencies += list((ROOT/'code/octa_seg_v1').glob('*.py'))
        dependencies += [ROOT/'code'/name for name in (
            'quality_pilot/prepare.py', 'eight_surface/segment.py', 'eight_surface/config.py',
            'cnv_review_v1/data.py', 'octa/volio.py', 'stage_a/geometry.py')]
        write(dependency_path, [fingerprint(p) for p in dependencies])
    if (OUT/'manifest.json').exists():
        m = read(OUT/'manifest.json')
        for fp in m['checkpoints'] + [m['calibration'], m['source_manifest']]:
            verify(fp)
        return m
    with (ROOT/'outputs/scan_index.csv').open(encoding='utf-8-sig') as f:
        rows = [r for r in csv.DictReader(f) if r['animal'] in ('TS267', 'TS328')]
    with (ROOT/'outputs/scan_quality_metrics.csv').open(encoding='utf-8-sig') as f:
        qc = {r['scan_id']: r for r in csv.DictReader(f)}
    groups = {}
    unavailable = []
    for r in rows:
        sid = scan_id_for(r)
        q = qc.get(sid, {})
        if r['has_volumes'] != 'True' or not q.get('source') or not Path(q['source']).exists():
            unavailable.append(dict(scan_id=sid, reason='No available processed volume/QC source', **r))
            continue
        groups.setdefault((r['animal'], r['session_date'], r['eye']), []).append((sid, r, q))
    selected, alternatives = [], []
    for key, members in sorted(groups.items()):
        members.sort(key=lambda x: (int(x[1]['scan_no']), x[1]['acq_time'], x[0]))
        for i, (sid, r, q) in enumerate(members):
            record = dict(scan_id=sid, animal=r['animal'], eye=r['eye'], session_date=r['session_date'],
                          day_label=r['day_label'], days_post_laser=r['days_post_laser'] or None,
                          day_basis='actual' if r['days_post_laser'] else 'nominal; actual day unavailable',
                          source=q['source'], scan_no=r['scan_no'], acq_time=r['acq_time'])
            (selected if repeats == 'all' or i == 0 else alternatives).append(record)
    m = dict(group='longitudinal_assessment', animals=['TS267', 'TS328'], repeats=repeats,
             selection='All repeats' if repeats == 'all' else 'Lowest acquisition number, then earliest time, per animal/eye/visit. No quality-ranking claim.',
             scans=[r['scan_id'] for r in selected], visits=selected, unselected_repeats=alternatives,
             unavailable=unavailable, checkpoints=[fingerprint(V1/'models/ALL_LABELLED'/n) for n in ('position.pt', 'states.pt')],
             calibration=fingerprint(V1/'calibration/deployment_vessels.json'),
             source_manifest=fingerprint(V2/'manifest.json'),
             claim='Experimental inference only; unchanged v1 weights and current v2 reporting policy. No longitudinal registration or validated change estimate.')
    write(OUT/'manifest.json', m)
    with (OUT/'visits.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, list(selected[0])); w.writeheader(); w.writerows(selected)
    return m


def bind(sid=None):
    m = initialize()
    sys.path.insert(0, str(V2/'code'))
    import octa_seg_v2.common as c
    c.OUT = OUT/'v2'; c.ROUND = c.OUT/'round_000'; c.ROOT = ROOT
    c.SCANS = [sid] if sid else m['scans']
    c.initialize = lambda: m
    return c


def metadata(sid):
    import numpy as np
    from stage_a.common import fingerprint
    out = OUT/'v2/round_000/volumes'/sid
    p = read(out/'prepared.json')
    with np.load(out/'geometry.npz') as g:
        n = dict(scan_id=sid, source=p['source'], n_bscans=512,
                 orientation_detected=bool(g['vitreous_high']), label_offset=int(g['label_offset']),
                 axis_order='B-scan,boundary,A-line; full canonical depth; vitreous 0',
                 position_checkpoint=initialize()['checkpoints'][0], state_checkpoint=initialize()['checkpoints'][1])
    write(out/'neural_complete.json', n)
    image = Path(p['images'])
    if not (out/'images.npy').exists():
        cache_copy(image, out/'images.npy')
    return out, p, n


def export_v1(sid):
    import numpy as np
    from octa_seg_v1.decisions import decide, estimate_context, thickness
    from octa_seg_v1.export import live_decisions
    from stage_a.common import fingerprint
    from eight_surface.config import SURFACE_NAMES, LAYER_DEFS, CASCADE_VERSION
    c = bind(sid)
    src, prep, neural = metadata(sid)
    out = OUT/'v1/volumes'/sid
    if (out/'complete.json').exists():
        return
    out.mkdir(parents=True, exist_ok=True)
    for name in ('geometry.npz', 'images.npy', 'alignment.npz'):
        cache_copy(src/name, out/name)
    g = c.npz(src/'geometry.npz'); a = c.npz(src/'alignment.npz')
    base = c.npz(src/'v1_matched_baseline.npz')
    d2 = c.npz(src/'measurements.npz')
    guards, provenance = live_decisions(read(V1/'data/manifest.json'), sid, g)
    rows = base['raw_position_branch']; prob = base['probabilities']
    cal = read(V1/'calibration/deployment_vessels.json')['thresholds']
    decisions = [decide(rows[b], prob[b], cal, g['vessel'][b], **guards.get(b, {})) for b in range(512)]
    rep, state, reason = [np.stack([d[k] for d in decisions]) for k in range(3)]
    assert np.array_equal(rep, base['reported_positions'], equal_nan=True)
    est, cr, records = estimate_context(rows, rep, state, reason, np.load(out/'images.npy', mmap_mode='r'),
                                       a['shifts'], a['scores'], offset=int(g['label_offset']))
    d = dict(reported_positions=rep, uncertain_estimates=est, state=state, reason=reason,
             context_reason=cr, probabilities=prob, entropy=d2['entropy'], raw_position_branch=rows,
             primary_thickness_um=thickness(rep, g['shadow']), shadow=g['shadow'], vessel=g['vessel'], cnv=g['cnv'],
             label_offset=g['label_offset'], surface_names=np.array(SURFACE_NAMES), validated=np.array(False),
             model_version=np.array('octa-seg_v1'), thickness_names=np.array([x[0] for x in LAYER_DEFS]+['INNER_RETINA']))
    np.savez_compressed(out/'measurements.npz', **d)
    provider = dict(d, surfaces=rep-int(g['label_offset']), uncertain_estimates=est-int(g['label_offset']),
                    confidence=np.full_like(rep, np.nan), scan_id=np.array([sid]),
                    cascade_version=np.array([CASCADE_VERSION]), source=np.array([prep['source']['path']]),
                    retina_band=g['retina_band'], bscan_index=np.arange(512), px_um=np.array([1.12]))
    packs = OUT/'v1/review_packs/automatic'; packs.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(packs/f'{sid}.npz', **provider)
    write(out/'prepared.json', dict(prep, images=str(out/'images.npy')))
    write(out/'neural_complete.json', neural)
    write(out/'human_overrides_provenance.json', provenance)
    write(out/'complete.json', dict(scan_id=sid, n_bscans=512, measurements=fingerprint(out/'measurements.npz')))


def configs():
    m = initialize()
    proposals = OUT/'v2/proposals'
    proposals.mkdir(parents=True, exist_ok=True)
    for sid in m['scans']:
        previous = ROOT/'outputs/eight_surface/vasculature_proposals'/f'{sid}_proposal.npz'
        if previous.exists(): cache_copy(previous, proposals/previous.name)
    for version in ('v1', 'v2'):
        home = OUT/version
        config = read(V1/'launch_config.json')
        packs = home/('review_packs/automatic' if version == 'v1' else 'round_000/review_packs')
        config.update(segmentations=str(packs), output=str(home/'reviewer'), initial_scan=m['scans'][0],
                      proposals=str(proposals), auto_sources=[dict(name=f'Longitudinal {version}', directory=str(packs))])
        config.pop('review_queue', None)
        write(home/'launch_config.json', config)
        volume_root = home/('volumes' if version == 'v1' else 'round_000/volumes')
        write(home/'thick/volumes.json', [str(volume_root/s) for s in m['scans']])


def verify_scan(sid):
    import numpy as np
    from stage_a.common import fingerprint
    from longitudinal_viewers import thickness_engine
    from octa_seg_v1.decisions import thickness
    checks = []
    for version in ('v1', 'v2'):
        home = OUT/version
        engine, volume_class = thickness_engine(version)
        directory = home/('volumes' if version == 'v1' else 'round_000/volumes')/sid
        v = volume_class(directory, read(home/'launch_config.json'))
        assert v.d['raw_position_branch'].shape == (512, 8, 512)
        assert v.metadata()['model_version'] == f'octa-seg_{version}'
        assert not np.isfinite(v.d['reported_positions'][v.d['state'] != 1]).any()
        assert not np.isfinite(v.d['uncertain_estimates'][v.d['state'] != 3]).any()
        np.testing.assert_equal(thickness(v.d['reported_positions'], v.g['shadow']), v.d['primary_thickness_um'])
        packs = home/('review_packs/automatic' if version == 'v1' else 'round_000/review_packs')
        with np.load(packs/f'{sid}.npz') as pack:
            np.testing.assert_equal(pack['surfaces'], v.d['reported_positions']-v.offset)
            np.testing.assert_equal(pack['bscan_index'], np.arange(512))
        if version == 'v1':
            from octa.volio import ProcessedVolume
            from eight_surface.segment import prepare_bscan
            with ProcessedVolume(v.neural['source']['path']) as source:
                band = source.read_volume(depth_slice=slice(*map(int, v.g['retina_band'])))
            for b in (0, 256, 511):
                np.testing.assert_allclose(prepare_bscan(band[b], bool(v.g['vitreous_high'])), v.images[b], atol=1e-5, rtol=0)
            reference_images = np.array(v.images[[0,256,511]])
            reference_positions = v.d['raw_position_branch'].copy()
            del band
        else:
            np.testing.assert_equal(v.images[[0,256,511]], reference_images)
            np.testing.assert_equal(v.d['raw_position_branch'], reference_positions)
        for mode in (0, 1):
            assert not np.isfinite(v.maps[mode][0][:, v.g['shadow']]).any()
            for b, x in ((0, 0), (256, 256), (511, 511)):
                for k, p in enumerate(v.point(b, x, mode)):
                    value = v.maps[mode][0][k, b, x]
                    assert (p['thickness_um'] is None and not np.isfinite(value)) or p['thickness_um'] == value
                    if p['thickness_um'] is not None:
                        assert np.isclose(value, (p['bottom_full_px']-p['top_full_px'])*1.12)
        checks.append(dict(version=version, scan_id=sid, shape=list(v.shape),
                           native_rows_verified=[0,256,511], shadow_nan=True, map_point_units_agree=True,
                           finite_fraction=float(np.isfinite(v.maps[0][0]).mean()),
                           measurements=fingerprint(directory/'measurements.npz')))
        del v
    write(OUT/'verification'/f'{sid}.json', checks)


def stage(action, sid):
    # Independent scan workers may share a group. Never mutate one scan at once.
    import msvcrt
    import time
    lock = OUT/'locks'/f'{sid}.lock'
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open('a+b') as f:
        if f.tell() == 0: f.write(b'0'); f.flush()
        while True:
            f.seek(0)
            try:
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError as exc:
                if exc.errno not in (13, 11): raise
                time.sleep(.2)
        try: _stage(action, sid)
        finally:
            f.seek(0); msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)


def _stage(action, sid):
    c = bind(sid)
    if action == 'prepare':
        from octa_seg_v2.prepare import run
        run()
    elif action == 'infer':
        if not (c.ROUND/'volumes'/sid/'neural_complete.json').exists():
            from octa_seg_v2.infer import run
            run()
        metadata(sid)
    elif action == 'export':
        from octa_seg_v2.export import run
        run()
        from stage_a.common import fingerprint
        out, _, _ = metadata(sid)
        write(out/'human_overrides_provenance.json', read(out/'human_guard_provenance.json'))
        write(out/'complete.json', dict(scan_id=sid, n_bscans=512, measurements=fingerprint(out/'measurements.npz')))
        export_v1(sid)
    elif action == 'verify':
        proof = OUT/'verification'/f'{sid}.json'
        if proof.exists():
            # Completed automatic exports are immutable for this group. A changed
            # measurement must not silently inherit its previous verification.
            from stage_a.common import verify
            checks = read(proof)
            if {r['version'] for r in checks} == {'v1', 'v2'}:
                for r in checks: verify(r['measurements'])
                return
        verify_scan(sid)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['init', 'status', 'run', 'prepare', 'infer', 'export', 'verify', 'thick', 'review'])
    p.add_argument('--scan'); p.add_argument('--version', choices=['v1', 'v2'], default='v2')
    p.add_argument('--repeats', choices=['one', 'all'])
    a = p.parse_args(); m = initialize(a.repeats or 'one')
    if a.repeats and m['repeats'] != a.repeats:
        p.error('The saved selection is fixed. Create a separately named assessment to change its repeat policy.')
    if a.action == 'init':
        configs(); print(json.dumps(m, indent=2)); return
    if a.action == 'status':
        ready = [s for s in m['scans'] if (OUT/'verification'/f'{s}.json').exists()]
        print(json.dumps(dict(group=m['group'], ready=len(ready), total=len(m['scans']),
                              remaining=[s for s in m['scans'] if s not in ready]), indent=2))
        return
    if a.action in ('thick', 'review'):
        from longitudinal_viewers import launch
        return launch(a.action, a.version, a.scan)
    if a.action == 'run':
        configs()
        for i, sid in enumerate(m['scans']):
            if a.scan and sid != a.scan: continue
            for action in ('prepare', 'infer', 'export', 'verify'):
                write(OUT/'status.json', dict(status='running', scan=sid, number=i+1, total=len(m['scans']), stage=action))
                print(f'[{i+1}/{len(m["scans"])}] {action}: {sid}', flush=True)
                try:
                    subprocess.run([sys.executable, __file__, action, '--scan', sid], check=True)
                except subprocess.CalledProcessError as exc:
                    write(OUT/'status.json', dict(status='failed', scan=sid, stage=action, exit_code=exc.returncode,
                                                  resume='LONGITUDINAL_ASSESSMENT.cmd run'))
                    raise
        if not a.scan:
            write(OUT/'COMPLETE.json', dict(scans=m['scans'], versions=['v1', 'v2'], bscans_per_volume=512))
            write(OUT/'status.json', dict(status='complete', scans=len(m['scans']), exports=2*len(m['scans'])))
    else:
        if not a.scan or a.scan not in m['scans']: p.error('--scan must be in the longitudinal manifest')
        stage(a.action, a.scan)


if __name__ == '__main__':
    main()
