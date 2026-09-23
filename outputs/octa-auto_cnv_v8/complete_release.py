"""Finalize the release after recorded real-browser acceptance and screenshots."""
from common import *
from finalize import run as finalize

def run():
    assert read(HERE/'READY_FOR_BROWSER_QA.json')['complete']
    qa=read(HERE/'verification/browser_qa.json')
    assert qa['passed'] and qa['temporary_notes_cleared']
    assert qa['viewer_html_sha256']==sha(HERE/'viewer.html')
    assert read(HERE/'verification/viewer_checks.json')['passed']
    for fp in qa['screenshots']:verify(fp)
    finalize()
    with (HERE/'REPORT.md').open('a',encoding='utf8') as f:
        f.write('\nBrowser acceptance passed: reference and unlabeled cases, native rows 0/511, map-click navigation, independent overlays, full-depth display, suppression reasons, and separate note persistence/export. Screenshots are in screenshots/; verification/browser_qa.json records the checks. The temporary QA note was cleared.\n')
    write(HERE/'RELEASE_COMPLETE.json',dict(
        complete=True,release='octa-auto_cnv_v8',models=2,epochs_each=100,
        optimizer_steps_each=3200,comparison_cases=30,training_references=10,
        unlabeled_acquisitions=20,all_animals_have_training_exposure=True,
        report=fingerprint(HERE/'REPORT.md'),
        artifacts=fingerprint(HERE/'artifact_manifest.json'),
        source_manifest=fingerprint(HERE/'source_manifest.json'),
        browser_qa=fingerprint(HERE/'verification/browser_qa.json'),
        scope='Exploratory training and review only; no validated accuracy or unseen-animal claim; stop for human review.'))
    progress('V8 release complete; stop for human review',models=2,cases=30)

if __name__=='__main__':run()
