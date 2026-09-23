"""Seal the review handoff after array, code, figure and prior-artifact checks."""
import json
from pathlib import Path
import re
from stage_a.common import OUT, fingerprint, verify, write_json

RUN=OUT/'stage_a/20260908_v6_conservative_decoder'


def run():
    software=json.loads((RUN/'software_verification.json').read_text())
    integrity=json.loads((RUN/'integrity_complete.json').read_text())
    assert software['tests']==41 and software['failures']==0 and software['measurement_files_checked']==114
    assert not integrity['human_labels_written'] and not integrity['locked_contents_read'] and not integrity['old_roots_added_files']
    measurements=json.loads((RUN/'measurement_fingerprints.json').read_text())
    for fp in measurements: verify(fp)
    links=0
    for name in ['RUN_REPORT.md','ANNOTATION_NEXT_STEP.md']:
        for target in re.findall(r'\]\(([^)]+)\)',(RUN/name).read_text(encoding='utf-8')):
            assert Path(target).is_absolute() and Path(target).exists(),target
            links+=1
    plan=json.loads((RUN/'plan.json').read_text()); checkpoints=[]
    for stage in plan['stages']:
        d=RUN/stage['name']; checkpoint=json.loads((d/'checkpoint.json').read_text())
        for fp in [checkpoint['configuration'],checkpoint['result'],*checkpoint['source_snapshot']]: verify(fp)
        assert (d/'visual_review.json').exists()
        assert not json.loads((d/'decision.json').read_text())['all_pass']
        checkpoints.append(fingerprint(d/'checkpoint.json'))
    artifacts=[p for p in RUN.rglob('*') if p.is_file() and p.suffix in {'.png','.csv','.md','.json'}
        and not any(part in {'mpl','checks','source_snapshot'} for part in p.parts)
        and p.name not in {'artifact_fingerprints.json','completion.json'}]
    write_json(RUN/'artifact_fingerprints.json',[fingerprint(p) for p in artifacts])
    write_json(RUN/'completion.json',dict(experiment_complete=True,decoder_checkpoints=checkpoints,
        review_recommendation='c2_tighter_signal',production_promotion=False,
        remaining_failure='D98 ILM columns [232,251), 19 retained gross errors in C2/C3; stricter gating loses useful tissue',
        next='Human local visibility and exact-stroke-provenance pilot; 24 suggestions, 9 images, no labels written',
        measured_files_sealed=len(measurements),review_document_links_verified=links,
        figures_sealed=sum(p.suffix=='.png' for p in artifacts),
        source_files=[fingerprint(p) for p in Path(__file__).parent.glob('*') if p.is_file()],
        original_artifacts_unchanged=integrity['prior_artifacts_metadata_unchanged'],tests_passed=software['tests']))


if __name__=='__main__': run()
