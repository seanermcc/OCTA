"""Validated native-grid providers. Context overlays never replace inference inputs."""
from pathlib import Path
import numpy as np
from .common import ROOT, OUT, read, fingerprint
from eight_surface.config import SURFACE_NAMES, SURFACE_DESCRIPTIONS, LAYER_DEFS, CASCADE_VERSION
from cnv_review_v1.data import load_enface
from eight_surface import cnv_labels as CL
from eight_surface.vasculature_proposals import has_saved_vessel_work

ANATOMY = dict(id=CASCADE_VERSION, boundaries=[dict(name=n, definition=SURFACE_DESCRIPTIONS[n]) for n in SURFACE_NAMES],
               thickness=[list(row) for row in LAYER_DEFS + [('INNER_RETINA', 'ILM', 'IPL_INL')]])


def validate_anatomy(value):
    if value != ANATOMY:
        raise ValueError('Boundary definitions/order/thickness endpoints differ from tree-shrew 5-8surf-pr. No index mapping is allowed.')


def manifests():
    # Publishers opt into a precise contract; unrelated output schemas are never guessed.
    locations = set((ROOT / 'outputs').glob('*/review_provider.json'))
    locations.update((ROOT / 'outputs/octa-seg').glob('*/review_provider.json'))
    locations.update((OUT / 'providers').glob('*/review_provider.json'))
    return sorted(locations)


def completed_manifest(path):
    path = Path(path)
    marker = path.parent / 'REVIEW_PROVIDER_COMPLETE.json'
    if not marker.exists(): return None
    sealed = read(marker)
    if sealed.get('manifest_sha256') != fingerprint(path):
        raise ValueError(f'Provider is incomplete or changed after sealing: {path}')
    m = read(path)
    if m.get('format') != 'octa-review-provider-1' or m.get('status') != 'complete':
        raise ValueError(f'Unknown/incomplete review provider: {path}')
    if not m.get('version') or not m.get('checkpoint_identity') or not isinstance(m.get('scans'), list):
        raise ValueError('Provider requires version, checkpoint identity and scan records')
    return m


def validate_grid(spec, volume):
    if (spec.get('scan_id') != volume.scan.scan_id or
        Path(spec.get('source_volume', '')).resolve() != volume.scan.source_volume.resolve() or
        spec.get('shape') != [volume.images.shape[0], volume.images.shape[2]] or
        spec.get('axis_order') != 'B-scan,A-line' or spec.get('orientation') != 'native-enface;vitreous-at-depth-zero' or
        spec.get('crop_offset') != int(volume.data['label_offset']) or
        spec.get('retina_band') != list(volume.scan.retina_band) or
        not np.allclose(spec.get('spacing_um', [0, 0, 0]), [1460 / volume.images.shape[0], 1460 / volume.images.shape[2], volume.scan.px_um])):
        raise ValueError('Provider scan/source/grid/orientation/crop/spacing mismatch; no transpose or shift was attempted')


def surface_entries():
    result = []
    for path in manifests():
        # A malformed optional context publication must not prevent layer browsing.
        try:
            kind = read(path).get('kind')
        except (ValueError, OSError):
            continue
        if kind != 'surfaces':
            continue
        m = completed_manifest(path)
        if m is None or m.get('kind') != 'surfaces': continue
        validate_anatomy(m.get('anatomy'))
        if m.get('adapter') != 'octa-measurements-cache-1':
            raise ValueError('Unsupported surface adapter: ' + str(path))
        for spec in m['scans']:
            directory = (path.parent / spec['directory']).resolve()
            for name in ('prepared.json', 'geometry.npz', 'measurements.npz'):
                if fingerprint(directory / name) != spec.get('sha256', {}).get(name):
                    raise ValueError(f'Incomplete surface provider artifact: {directory / name}')
            result.append(dict(scan_id=spec['scan_id'], directory=str(directory), provider_manifest=str(path),
                               provider_version=m['version'], provider_geometry=spec))
    return result


def context_signature(sid):
    paths = list(manifests())
    paths += [p.parent / 'REVIEW_PROVIDER_COMPLETE.json' for p in paths]
    paths += [ROOT / 'outputs/cnv_labels' / f'{sid}_cnv.npz',
              ROOT / 'outputs/octo-vessel_onh_v2/records' / f'{sid}.json',
              ROOT / 'outputs/octo-vessel_onh_v2/FINAL_VERIFIED.json']
    paths += list((ROOT / 'outputs/cnv_labels').glob(f'{sid}*'))
    paths += [ROOT / f'outputs/octa-auto_cnv_{v}/review/regions/{sid}_regions.json' for v in ('v3', 'v4', 'v5')]
    return tuple((str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in paths if p.exists())


def learned_onh(volume, root=None):
    root = Path(root or ROOT / 'outputs/octo-vessel_onh_v2')
    complete = root / 'FINAL_VERIFIED.json'
    path = root / 'records' / f'{volume.scan.scan_id}.json'
    if not complete.exists() or not path.exists(): return None
    if read(complete).get('status') != 'complete': return None
    rec = read(path)
    if rec.get('status') != 'complete': return None
    identity = rec['identity']
    if (identity['native_shape'] != list(volume.scan.native_shape) or identity['axis_order'] != 'B-scan,A-line'
            or Path(identity['source_volume']).resolve() != volume.scan.source_volume.resolve()
            or identity['retina_band'] != list(volume.scan.retina_band)):
        raise ValueError('Automatic ONH source/native geometry does not match this volume')
    pp = (root / rec['prediction_file']).resolve()
    if not pp.is_relative_to(root.resolve()) or fingerprint(pp) != rec['prediction_sha256']:
        raise ValueError('Automatic ONH prediction is incomplete or changed')
    with np.load(pp, allow_pickle=False) as z:
        if (str(z['scan_id'].reshape(-1)[0]) != volume.scan.scan_id or
                str(z['model_sha256'].reshape(-1)[0]) != identity['model_sha256'] or
                z['onh_mask'].shape != volume.scan.native_shape):
            raise ValueError('Automatic ONH payload identity/grid mismatch')
        mask = np.asarray(z['onh_mask'], bool)
    return mask, dict(path=str(pp), sha256=rec['prediction_sha256'], version=root.name,
                      model_id=identity['model_sha256'], status='experimental automatic ONH; not a human judgment')


def saved_cnv(volume):
    for version in ('v5', 'v4', 'v3'):
        path = ROOT / f'outputs/octa-auto_cnv_{version}/review/regions/{volume.scan.scan_id}_regions.json'
        if not path.exists(): continue
        rec = read(path)
        if (rec.get('format') != '1-cnv-region-review' or rec['scan_id'] != volume.scan.scan_id or
            rec['native_shape'] != list(volume.scan.native_shape) or rec['axis_order'] != 'B-scan,A-line' or
            Path(rec['source_volume']).resolve() != volume.scan.source_volume.resolve()):
            raise ValueError('Saved CNV region review has incompatible geometry/source')
        mask = np.zeros(volume.scan.native_shape, bool)
        for region in rec['regions']:
            # Preserve drafts/uncertain regions as saved context, with their origin stated.
            if region.get('decision') in ('removed', 'rejected', 'remove') or region.get('deleted', False): continue
            for row, lo, hi in region['runs']:
                if not (0 <= row < mask.shape[0] and 0 <= lo < hi <= mask.shape[1]):
                    raise ValueError('Saved CNV interval outside native geometry')
                mask[row, lo:hi] = True
        return mask, dict(path=str(path), sha256=fingerprint(path), status=f'saved CNV {version} context (includes drafts/uncertainty)',
                          revision=rec['revision'])
    return None


def context_overlays(volume, proposal_dir, experimental_onh=False):
    scan = volume.scan
    original = load_enface(scan, ROOT / 'outputs/cnv_labels', proposal_dir)
    cnv, vessel, onh, edge = [a.copy() for a in original[:4]]
    provenance = dict(vessel=original[4])
    human = CL.load_label(original[5]) if original[5] else None
    protected = dict(cnv=bool(human and (human['reviewed_targets'][0] or human['cnv_mask'].any())),
        vessel=has_saved_vessel_work(human),
        onh=bool(human and (human['reviewed_targets'][2] or human['onh_mask'].any() or human['onh_edge_mask'].any())))
    # New ONH workflow stores explicit assessment/uncertainty fields not returned by old CL loader.
    if original[5]:
        with np.load(original[5], allow_pickle=False) as z:
            if 'onh_visibility' in z.files:
                protected['onh'] |= str(z['onh_visibility'].reshape(-1)[0]) not in ('', 'Not assessed')
            for key in ('onh_brush_touched', 'onh_uncertain_mask', 'onh_region_excluded'):
                if key in z.files: protected['onh'] |= bool(z[key].any())
        provenance['human_masks'] = dict(path=original[5], sha256=fingerprint(original[5]), protected=protected.copy())
    current_cnv = saved_cnv(volume)
    if current_cnv:
        cnv, provenance['cnv'] = current_cnv
        protected['cnv'] = True
    masks = dict(cnv=cnv, vessel=vessel, onh=onh)
    errors = []
    for path in manifests():
        try:
            manifest = completed_manifest(path)
            if manifest is None or manifest.get('kind') != 'context': continue
            for spec in manifest['scans']:
                if spec['scan_id'] != scan.scan_id: continue
                validate_grid(spec, volume)
                payload = (path.parent / spec['file']).resolve()
                if not payload.is_relative_to(path.parent.resolve()) or fingerprint(payload) != spec['sha256']:
                    raise ValueError('Context payload incomplete/changed: ' + str(payload))
                with np.load(payload, allow_pickle=False) as arrays:
                    pending = {}
                    for definition in manifest['masks']:
                        name = definition['name']
                        if name not in masks or definition['definition'] != {'cnv': 'CNV enface footprint', 'vessel': 'major vessel enface footprint', 'onh': 'optic nerve head enface footprint'}[name]:
                            raise ValueError('Unknown context mask definition')
                        a = arrays[definition['array']]
                        if a.shape != scan.native_shape or a.dtype != np.bool_:
                            raise ValueError('Context masks must be boolean on the exact native grid')
                        if not protected[name]:
                            pending[name] = a.copy()
                    for name, a in pending.items():
                        masks[name] = a
                        provenance[name] = dict(path=str(path), version=manifest['version'], checkpoint=manifest['checkpoint_identity'], sha256=spec['sha256'])
        except (ValueError, KeyError, OSError) as exc:
            errors.append(str(exc))
    if experimental_onh and not protected['onh']:
        try:
            proposal = learned_onh(volume)
            if proposal: masks['onh'], provenance['onh'] = proposal
        except (ValueError, KeyError, OSError) as exc:
            errors.append(str(exc))
    status = ' · '.join(f'{key}: {value.get("version", value.get("status", "saved human masks"))}' for key, value in provenance.items())
    if errors: status += ' · Context rejected: ' + '; '.join(errors)
    return masks['cnv'], masks['vessel'], masks['onh'], edge, dict(status=status, sources=provenance, errors=errors), original[5]
