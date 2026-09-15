"""Functional invariants and synthetic challenges, never real human-label writes."""
import unittest
from dataclasses import replace
from common import *
from algorithm import Parameters, run, fit_tiles, grow
from pilot import geometry_valid, evaluate


def scene():
    yy, xx = np.indices((512, 512))
    expected = 270 + .08*xx + .03*yy
    rng = np.random.default_rng(47)
    measured = expected + rng.normal(0, .5, expected.shape)
    image = 40 + rng.normal(0, .03, expected.shape)
    blank = np.zeros(expected.shape, bool)
    return yy, xx, expected, measured, image, blank


class FunctionalChecks(unittest.TestCase):
    def test_signed_native_units_and_background(self):
        yy, xx, expected, t, image, z = scene()
        t[250, 250] += 20
        m, d = run(t, z, z, z, z, image)
        self.assertTrue(d['sufficient'])
        self.assertEqual(m['deficit_percent'].shape, (512, 512))
        self.assertLess(m['deficit_percent'][250, 250], 0)
        self.assertLess(np.median(np.abs(m['background_um']-expected)), 1)
        self.assertEqual(int(m['core'].sum()), 0)
        refit = fit_tiles(t, m['background_regions'], Parameters())
        np.testing.assert_allclose(m['background_um'], refit[0], atol=4e-5)

    def test_missing_lesion_vessel_and_irregular_halo(self):
        yy, xx, expected, t, image, z = scene()
        lesion = ((xx-240)/38)**2 + ((yy-245)/30)**2 < 1
        halo = ((xx-240)/65)**2 + ((yy-245)/55)**2 < 1
        t[halo] *= .8
        t[lesion] = np.nan
        image[lesion] += 3
        vessel = abs(xx-360) < 5
        t[vessel] = np.nan; image[vessel] -= 3
        m, d = run(t, vessel, vessel, ~np.isfinite(t), z, image)
        self.assertTrue(d['sufficient'])
        self.assertGreater(int(np.sum(m['core'] & lesion)), 100)
        self.assertTrue(np.isnan(m['deficit_percent'][lesion]).all())
        self.assertFalse(m['footprint'][lesion].any())
        self.assertFalse(m['core'][vessel].any())
        self.assertLess(np.median(abs(m['background_um'][halo]-expected[halo])), 3)

    def test_insufficient_background_never_becomes_measurement(self):
        yy, xx, expected, t, image, z = scene()
        t[:] = np.nan
        m, d = run(t, z, z, ~np.isfinite(t), z, image)
        self.assertFalse(d['sufficient'])
        self.assertFalse(m['core'].any())
        self.assertTrue(np.isnan(m['deficit_percent']).all())
        self.assertFalse(m['background_supported'].any())

    def test_geometry_checks_all_boundaries_and_offset(self):
        rows = np.broadcast_to(np.arange(8)[None, :, None]*10.+500, (3, 8, 4)).copy()
        rows[1, 4, 2] = 495
        valid = geometry_valid(rows, 480, 140)
        self.assertTrue(valid[0].all())
        self.assertFalse(valid[1, 0, 2])
        self.assertFalse(valid[1, 4, 2])
        rows[2, 7, 3] = 700
        self.assertFalse(geometry_valid(rows, 480, 140)[2, 7, 3])
        self.assertAlmostEqual((570-500)*1.12, 78.4)

    def test_io_native_coordinates_and_write_isolation(self):
        values = np.full((512, 512), np.nan, np.float32)
        values[17, 381] = -12.5
        path = HERE/'verification/synthetic_roundtrip.npz'
        save_npz(path, signed=values, metadata=np.array('synthetic, not human labels'))
        got = npz(path)['signed']
        np.testing.assert_array_equal(values, got)
        self.assertEqual(float(got[17, 381]), -12.5)
        self.assertTrue(np.isnan(got[381, 17]))
        with self.assertRaises(ValueError):
            destination(ROOT/'outputs/cnv_labels/forbidden.npz')

    def test_unreviewed_is_not_negative(self):
        mask = np.zeros((100, 100), bool); mask[40:50, 40:50] = True
        z = np.zeros_like(mask)
        result = evaluate(dict(core=mask, footprint=mask, background_supported=~z), z, z, {'reviewed_cnv': False})
        self.assertIsNone(result['false_candidates_in_reviewed_normal'])
        self.assertEqual(result['reviewed_manual_components'], 0)

    def test_invalid_shape_and_nonpositive_input(self):
        _, _, _, t, image, z = scene()
        with self.assertRaises(ValueError):
            run(t, z[:, :-1], z, z, z, image)
        t[2, 2] = 0
        with self.assertRaises(ValueError):
            run(t, z, z, z, z, image)


def real_checks():
    results = []
    for visit in selected():
        path = HERE/'scans'/visit['scan_id']/'maps.npz'
        if not path.exists():
            continue
        a = npz(path)
        meta = json.loads(str(a['metadata_json']))
        assert meta['visit']['scan_id'] == visit['scan_id']
        assert meta['native_shape'] == [512, 512]
        assert np.isnan(a['automatic_thickness_um'][a['shadow']]).all()
        assert np.isnan(a['viewer_thickness_um'][a['shadow']]).all()
        assert np.isnan(a['deficit_percent'][~np.isfinite(a['automatic_thickness_um'])]).all()
        assert np.isnan(a['deficit_percent'][~a['background_supported']]).all()
        assert not a['footprint'][~np.isfinite(a['automatic_thickness_um'])].any()
        raw = npz(volume_path(visit['scan_id'])/'v1_matched_baseline.npz')['raw_position_branch']
        offset = meta['audit']['viewer_metadata']['crop_offset']
        for row, col in ((0, 511), (256, 117), (511, 0)):
            np.testing.assert_allclose(a['automatic_endpoints_crop_px'][row, :, col], raw[row, [0, 7], col]-offset)
            if np.isfinite(a['automatic_thickness_um'][row, col]):
                assert abs(float(a['automatic_thickness_um'][row, col]) - float((raw[row, 7, col]-raw[row, 0, col])*1.12)) < 1e-4
        expected = 100*(a['background_um']-a['automatic_thickness_um'])/a['background_um']
        ok = np.isfinite(a['deficit_percent'])
        np.testing.assert_allclose(a['deficit_percent'][ok], expected[ok], atol=1e-5)
        assert not meta['human_reviewed']
        for src, digest in meta['audit']['input_hashes'].items():
            assert sha(src) == digest, f'Input changed: {src}'
        for src, digest in meta['audit']['viewer_metadata']['correction_fingerprints'].items():
            assert sha(src) == digest, f'Human correction changed: {src}'
        for name, diagnostic in meta['diagnostics'].items():
            if not diagnostic['sufficient']:
                record = next(r for r in meta['sensitivity'] if r['variant'] == name)
                assert record['footprint_mm2'] is None
                assert np.isnan(a[name+'__deficit_percent']).all()
        p = npz(HERE/'proposals'/f"{visit['scan_id']}.npz")
        np.testing.assert_array_equal(p['proposal_mask'], a['core'] | a['footprint'])
        assert str(p['scan_id']) == visit['scan_id']
        assert not bool(p['human_reviewed'])
        results.append(dict(scan_id=visit['scan_id'], native_shape=True, units=True, missing_preserved=True,
                            input_hashes_unchanged=True, automatic_save_reload=True))
    write(HERE/'verification/native_checks.json', results)
    return results

if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(FunctionalChecks)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    checks = real_checks()
    write(HERE/'verification/tests.json', dict(tests=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                                             real_scans_checked=len(checks)))
    raise SystemExit(not result.wasSuccessful())
