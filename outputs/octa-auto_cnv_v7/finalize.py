"""Seal software verification evidence; never represents human review completion."""
from common import *
from review_store import progress
from loader import context_overlays

def run():
    tests=read(HERE/'verification/contract_tests.json');real=read(HERE/'verification/real_gui.json');preserve=read(HERE/'verification/preservation_result.json')
    assert tests['successful'] and real['passed'] and preserve['passed']
    q=read(HERE/'queue/queue.json')['acquisitions'];p=progress(q)
    assert not p['errors']
    # Validate the final context identity guards against both referenced and unreviewed acquisitions.
    for sid in (q[0]['scan_id'],'TS267_OD_2025-03-05_D14_s01_104048'):
        a=next(a for a in q if a['scan_id']==sid)
        context_overlays(a,'prediction');context_overlays(a,'historical')
    atomic(HERE/'verification/final_context_checks.json',dict(passed=True,at=now(),checks=['native shape','native source manifest','scan identity','axis order','prediction full SHA256','checkpoint identity','historical source full SHA256']))
    cold=read(HERE/'verification/real_gui_cold.json')
    lines=['# Software verification — v7','',f'Verified {now()}. This record means application verification, **not** completion of 30 human reviews. No model was trained.',
        '',f'**{tests["tests"]} contract tests passed**, plus real Qt tests on four animals and an actual Windows launcher capture. V7 human labels: **{p["positive"]} positive / {p["negative"]} no-CNV**.',
        '', '## Evidence','',
        '- `verification/contract_tests.txt` / `.json`: deterministic queue, strict day handling including missing numeric values, native run bounds, duplicate acquisitions, visit cycling/exhaustion, full reserve, empty/unresolved regions, whole-field background, explicit absence/conflicts, ignored overlaps, edit invalidation, undo/redo, stale writers and simulated atomic save failure. Thirty-two synthetic confirmed acquisitions test the target and continuation beyond it; multiple regions/revisions do not inflate counts.',
        '- `verification/real_gui.json`: real native providers; actual Qt mouse painting/closed-loop fill, erase, Keep/Unsure/Remove, save/reopen, absence/add/undo, first/last rows and columns, disconnected intervals, multiple states, zoom preservation, optional context visibility and stable cursor. Synthetic gestures are stored only in `verification/gui/`.',
        '- `verification/launcher.png`: captured from the actual `OPEN_OCTA_AUTO_CNV_V7.cmd` using the native Windows Qt platform. The process exited successfully. Normal launch uses the same path without `--capture`.',
        '- `verification/final_context_checks.json`: final optional-overlay guards validate the native identity/grid, original prediction hash and checkpoint identity, and historical hashes.',
        '', '| Acquisition | Final verified load (s) | B-scan array | Projection error (dB) |','|---|---:|---|---:|']
    for r in real['acquisitions']:lines.append(f'| {r["scan_id"]} | {r["load_seconds"]} | {r["shape"]} | {r["max_projection_error_db"]} |')
    lines+=['', 'All four structural B-scan volume projections reproduced the frozen structural en-face values exactly. Canonical orientation/crop and source hashes were checked. TS267 D14 has historical review evidence; TS169, TS241 and the tested TS336 acquisition were unreviewed in the inventoried footprint sources.',
        f'The initial TS336 recovery took {next(r["load_seconds"] for r in cold["acquisitions"] if r["scan_id"].startswith("TS336"))} s. It read the processed volume once, freshly detected orientation, called prepare_bscan, reproduced the v6 native-array hash, and wrote a v7-only cache. Subsequent cached loading is shown above. There are ten such newer providers; only needed acquisitions are recovered. Other cold loads depend on disk/cache state and prefetch contention.',
        '', '## Screenshot review','',
        'An initial offscreen capture displayed missing-font boxes. Loading the Segoe UI font file explicitly corrected it. Final screenshots were inspected for readable controls, optical alignment, region colors and translucent B-scan intervals. The two synthetic images visibly identify themselves as software tests; they are not biological annotations.',
        '', '![Native launcher](verification/launcher.png)', '', '![Real TS267 historical-review acquisition](verification/real_TS267.png)',
        '', '![Synthetic multiple intervals on a real structural scan](verification/synthetic_multiple_intervals.png)',
        '', '## Preservation and storage','',
        f'{preserve["files"]} scoped legacy files ({preserve["bytes"]:,} bytes) had identical full-file SHA-256 before/after real GUI use. Scope: v1–v6 code/guides/launchers, v6 checkpoints, original CNV files, current/historical region records, and six-model predictions/provenance for the four tested acquisitions. See preservation_before.json and preservation_result.json. This does not claim fresh full hashes of all 1,944 predictions or all giant processed volumes.',
        'The fresh queue inventory sampled every one of the 332 processed files, checked source identities against validated providers and retained the prior full hashes for eight duplicate copies with current stat/sample checks. Zero new unindexed acquisitions were found. Existing v6 whole-cohort validation is provenance, not a new v7 full-cohort inference or native-load test.',
        'Opening real cases and toggling references created zero human annotation files. Browsing/session logs remain separate from decisions. Every synthetic test is confined to verification storage and excluded from real progress.',
        '', '## Limits and handoff','',
        'Real loading was exercised on four animals, not every acquisition. All queue candidates have available provenance-linked sources/providers, but a future missing/changed input produces a recoverable load error, never a negative label. Synthetic testing verifies software semantics, not biological segmentation accuracy. Optional thickness views and automatic reference copying are deliberately absent. Review quality and actual model benefit require the next human collection/training round.',
        'Start with START_HERE.md; use MODEL_AND_LABEL_HISTORY.md and TRAINING_PLAN.md for the next dataset freeze. No upstream code, model, original labels, RAW data or MATLAB code was altered.']
    destination(HERE/'VERIFICATION.md').write_text('\n'.join(lines),encoding='utf-8')
    artifacts=[p for p in HERE.glob('*') if p.is_file() and p.suffix in ('.py','.cmd','.md')]+list((HERE/'queue').glob('*'))
    atomic(HERE/'verification/artifact_manifest.json',[fingerprint(path) for path in sorted(artifacts)])
    atomic(HERE/'RELEASE_COMPLETE.json',dict(schema='v7-software-release-1',at=now(),software_verified=True,
        meaning='Software/queue verification only; NOT 30 human reviews completed',trained_model=False,
        eligible_acquisitions=len(q),eligible_animals=len({a['animal'] for a in q}),confirmed_positive_images=p['positive'],
        confirmed_no_cnv_images=progress(q)['negative'],contract_tests=tests['tests'],real_animals_tested=4,
        launcher='OPEN_OCTA_AUTO_CNV_V7.cmd',preservation_scope=preserve['scope'],
        queue_sha256=sha(HERE/'queue/queue.json'),artifact_manifest=fingerprint(HERE/'verification/artifact_manifest.json')))
    print('Software verified. Real human progress:',progress(q)['positive'],progress(q)['negative'])

if __name__=='__main__':run()
