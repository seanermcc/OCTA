"""Verify the completed selection and write its concise handoff report."""
import numpy as np
from longitudinal_assessment import OUT, initialize, read, write
from stage_a.common import fingerprint, verify


def main():
    m = initialize()
    proofs = []
    for sid in m['scans']:
        result = read(OUT/'verification'/f'{sid}.json')
        assert {r['version'] for r in result} == {'v1', 'v2'}
        for r in result:
            verify(r['measurements'])
            assert r['shape'] == [512,512] and r['native_rows_verified'] == [0,256,511]
        one = OUT/'v1/volumes'/sid; two = OUT/'v2/round_000/volumes'/sid
        for folder in (one, two):
            assert read(folder/'complete.json')['scan_id'] == sid
        with np.load(one/'measurements.npz') as a, np.load(two/'measurements.npz') as b:
            np.testing.assert_equal(a['raw_position_branch'], b['raw_position_branch'])
            np.testing.assert_equal(a['probabilities'], b['probabilities'])
        np.testing.assert_equal(np.load(one/'images.npy', mmap_mode='r')[[0,256,511]],
                                np.load(two/'images.npy', mmap_mode='r')[[0,256,511]])
        proofs.extend(result)
    write(OUT/'verification/summary.json', dict(volumes=len(m['scans']), version_exports=len(proofs),
          native_bscans_per_version=512*len(m['scans']), source_images_checked=True,
          paired_neural_outputs_identical=True, shadow_nan=True, map_point_units_agree=True,
          original_ten_volume_manifest_unchanged=True, manifest=fingerprint(OUT/'manifest.json')))
    lines = ['# Longitudinal assessment — completed', '',
             f"All {len(m['scans'])} selected full acquisitions are exported in v1 and v2 "
             f"({len(proofs)} versioned volumes, {512*len(m['scans']):,} native B-scans per version).", '',
             'Use octa-thick_long_v1.cmd / octa-thick_long_v2.cmd in outputs/octa-thick_v1 for thickness review, '
             'or OPEN_LONGITUDINAL_SEG_v1.cmd / v2.cmd for segmentation review.', '',
             '| Animal | Eye | Date | Nominal visit | v1 / v2 |', '|---|---|---|---|---|']
    for r in m['visits']:
        lines.append(f"| {r['animal']} | {r['eye']} | {r['session_date']} | {r['day_label']} | Ready / Ready |")
    lines += ['', 'Verification covered all exports in the octa-thick engine, native image rows '
              '0/256/511, version-matched neural predictions, provider coordinates, shadow NaNs, '
              'and point/map units. Both segmentation viewers and both thickness versions '
              'were rendered read-only on a completed volume.', '',
              'TS267 OS D56 has no processed source volume. Missing visits were not synthesized. '
              'Actual laser-day offsets are unavailable in the index; labels remain nominal. '
              'These are experimental automatic segmentations awaiting human review, '
              'not validated longitudinal change measurements. See START_HERE.md for scope and limitations.']
    (OUT/'RUN_REPORT.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print(f"Verified {len(proofs)} exports; longitudinal assessment ready.")


if __name__ == '__main__': main()
