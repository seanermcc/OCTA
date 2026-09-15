"""Compact quantitative sensitivity tables and a review atlas for saved results."""
import csv
from common import *
from algorithm import run, VARIANTS
from pilot import report, figure


def csv_file(path, rows):
    if not rows:
        return
    with destination(path).open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, list(rows[0])); writer.writeheader(); writer.writerows(rows)

def finalize():
    rows, candidates, ranges = [], [], []
    for visit in selected():
        sid = visit['scan_id']; path = HERE/'scans'/sid/'maps.npz'
        if not path.exists():
            continue
        a = npz(path); meta = read(path.parent/'provenance.json')
        # Compatibility enrichment for runs begun before this overlay was added.
        if 'assisted__background_regions' not in a:
            assisted, _ = run(a['viewer_thickness_um'], a['vessel'], a['shadow'],
                              ~np.isfinite(a['viewer_thickness_um']), a['low_signal'], a['enface'])
            a['assisted__background_regions'] = assisted['background_regions']
            save_npz(path, **a)
        figure(sid, a, path.parent/'overview.png')
        local_rows = []
        for record in meta['sensitivity']:
            name = record['variant']
            sufficient = meta['diagnostics'][name]['sufficient']
            if not sufficient:
                for k in ('core_mm2', 'footprint_mm2', 'contour10_mm2', 'contour20_mm2', 'contour30_mm2'):
                    record[k] = None
            row = dict(scan_id=sid, **record)
            row['reference_sufficient'] = sufficient
            common = a['background_supported'] & a[name+'__background_supported']
            row['common_supported_fraction'] = float(common.mean())
            for t in (10, 20, 30):
                base = (a['deficit_percent'] >= t) & common
                other = (a[name+'__deficit_percent'] >= t) & common
                union = np.sum(base | other)
                row[f'contour{t}_jaccard_on_common_support'] = float(np.sum(base & other)/union) if union else None
            core_a = a['core'] & common; core_b = a[name+'__core'] & common
            row['candidate_core_jaccard_on_common_support'] = (float(np.sum(core_a & core_b)/np.sum(core_a | core_b))
                                           if np.any(core_a | core_b) else None)
            rows.append(row); local_rows.append(row)
        # Keep the embedded and sidecar provenance in agreement.
        a['metadata_json'] = np.array(json.dumps(meta))
        save_npz(path, **a)
        write(path.parent/'provenance.json', meta)
        available = [r['footprint_mm2'] for r in local_rows if r['footprint_mm2'] is not None]
        ranges.append(dict(scan_id=sid, default_footprint_mm2=meta['sensitivity'][0]['footprint_mm2'],
                           min_footprint_mm2=min(available) if available else None,
                           max_footprint_mm2=max(available) if available else None,
                           unavailable_reference_variants=sum(not r['reference_sufficient'] for r in local_rows),
                           min_reference_support=min(r['supported_fraction'] for r in local_rows),
                           max_reference_support=max(r['supported_fraction'] for r in local_rows)))
        for candidate in meta['candidates']:
            candidates.append(dict(scan_id=sid, **candidate))
    csv_file(HERE/'sensitivity.csv', rows)
    csv_file(HERE/'sensitivity_ranges.csv', ranges)
    csv_file(HERE/'candidates.csv', candidates)
    report()
    report_path = HERE/'START_HERE.md'
    text = report_path.read_text(encoding='utf-8')
    text = text.replace('or clustered automatic measurement loss next to', 'or clustered automatic trace/invalid-geometry loss (3-pixel connectivity) next to')
    text += '\n## Area stability and priority examples\n\n'
    text += 'Reference variants produce the following footprint ranges. These are within-scan sensitivity ranges, not longitudinal change or confidence intervals. `sensitivity.csv` also reports contour Jaccard agreement on common supported pixels; empty unions are unavailable, not perfect agreement. `candidates.csv` records native centers, areas, missing fractions and uncertain/clipped flags.\n\n'
    text += 'Variants with insufficient background have unavailable area (blank/null), never zero area, and are excluded from the range. Support still varies among the remaining fits. Manual-mask component counts include disconnected fragments; they are not independently confirmed lesion counts.\n\n'
    text += '| Scan | Default footprint mm² | Variant range mm² |\n|---|---:|---:|\n'
    for r in ranges:
        display = lambda v: 'unavailable' if v is None else f'{v:.4f}'
        text += f"| {r['scan_id']} | {display(r['default_footprint_mm2'])} | {display(r['min_footprint_mm2'])}–{display(r['max_footprint_mm2'])} |\n"
    text += '\nThe region editor groups disconnected proposal islands by nearest core solely for editing convenience. No foreground pixels are added, no border is claimed as truth, and the seeds remain Unclassified. Review files stay in `review/`; background exclusions create assisted estimates in `background_review/`. Existing annotations are comparison evidence only.\n\n'
    examples = [
        ('TS267_OD_2025-02-19_D0_s02_112013', 'D0 challenge: 2 candidates; nominal D0 alone does not certify unaffected tissue'),
        ('TS267_OD_2025-02-26_D7_s01_102519', 'D7 manual-location challenge: inspect misses and quantitative contours'),
        ('TS267_OD_2025-03-19_D28_s01_101503', 'D28 manual-location challenge: conservative core rule may fail'),
        ('TS267_OD_2025-04-16_D56_s01_100746', 'D56: 2 proposed cores; left lesion-like structural focus outside supported reference'),
        ('TS267_OS_2025-02-19_D0_s01_113115', 'D0 OS: zero candidates; not automatically a reviewed negative'),
    ]
    for sid, caption in examples:
        text += f'[{caption}](scans/{sid}/overview.png)\n\n'
    text += 'Validation results: `verification/tests.json`, `verification/native_checks.json`, and GUI captures in `verification/`. Scientific performance remains limited by sparse review and model training overlap.\n'
    destination(report_path).write_text(text, encoding='utf-8')
    atlas = ['<!doctype html><html><head><meta charset="utf-8"><title>octa-auto_cnv_v1 review atlas</title><style>body{font:18px system-ui;background:#151922;color:#eee;margin:35px;max-width:1500px}img{width:100%;border-radius:8px}a{color:#8dd6ff}section{margin:40px 0}p{max-width:1000px}</style></head><body><h1>octa-auto_cnv_v1</h1><p>TS267 experimental proposals and signed thinning. No visit registration; no independent detection claim. Missing measurements stay missing. Open the launcher for interactive native maps and proposal editing.</p>']
    for sid, caption in examples:
        atlas.append(f'<section><h2>{caption}</h2><p>{sid}</p><a href="scans/{sid}/overview.png"><img src="scans/{sid}/overview.png"></a></section>')
    atlas.append('</body></html>')
    destination(HERE/'REVIEW_ATLAS.html').write_text('\n'.join(atlas), encoding='utf-8')
    write(HERE/'implementation_manifest.json', {p.name: sha(p) for p in HERE.glob('*.py')})

if __name__ == '__main__':
    finalize()
