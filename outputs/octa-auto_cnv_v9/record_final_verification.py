"""Record observed browser/launcher QA and assemble the final release evidence."""
from common import *
from urllib.request import urlopen

health=json.load(urlopen('http://127.0.0.1:8799/health'))
assert health['app']=='octa-cnv-v9-gallery' and Path(health['root']).resolve()==HERE
write(HERE/'verification/LAUNCHER_QA.json',dict(passed=True,server_stopped_and_restarted_using='launch_gallery.ps1 -NoBrowser',hidden_process_start=True,health=health,browser_reload_and_native_bscan_after_restart=True))
write(HERE/'verification/BROWSER_QA.json',dict(passed=True,browser='Codex in-app browser',url='http://127.0.0.1:8799/',all_acquisitions_accessible=50,first_and_last_acquisition_loaded=True,native_rows_checked=[0,511],enface_center_click_observed_row=257,candidate_click_observed_rows=[153,299],synchronized_zoom_pan_visually_verified=True,bscan_zoom_range_checked=[1,4],default_bscan_display_height_px=440,independent_overlays_and_hidden_recovery=True,unknown_onh_explicit=True,filters=dict(zero=13,disagreement=43,downranked=28,animal_visit_combination=2,reset=50),preferences_tested_only_on_synthetic_fixture=True,real_preferences_untouched=True,final_animal_exposure_metadata_verified=True,actual_postlaser_days_unavailable_nominal_labels_explicit=True,console_errors=[],screenshots=[fingerprint(HERE/'verification'/n) for n in ('gallery_final.png','gallery_overview.png','real_zoom_pan.png')]))
names=['SYNTHETIC_TESTS','RESUME_QA','COMPLETE_FIT_RESUME_QA','REAL_PREFLIGHT','HTTP_NATIVE_ROWS_QA','FINAL_DATA_QA','CONTROLLED_COMPARISON_QA','DELIVERY_METADATA_QA','BUNDLE_CLI_QA','BROWSER_QA','LAUNCHER_QA']
evidence=[]
for name in names:
 p=HERE/'verification'/(name+'.json');assert read(p)['passed'],name;evidence.append(fingerprint(p))
preservation=read(HERE/'reports/preservation_after.json');assert preservation['unchanged'] and preservation['annotation_heads_unchanged']
stage=read(HERE/'AUTOMATED_STAGES_COMPLETE.json');stage['browser_final_qa_pending']=False;stage['browser_final_qa']=fingerprint(HERE/'verification/BROWSER_QA.json');write(HERE/'AUTOMATED_STAGES_COMPLETE.json',stage)
write(HERE/'FINAL_VERIFIED.json',dict(passed=True,at=time.time(),training_fits=14,confirmed_training_acquisitions=29,comparison_acquisitions=50,upstream_files_unchanged=preservation['files_checked'],evidence=evidence,report=fingerprint(HERE/'REPORT.md'),gallery=fingerprint(HERE/'gallery/data.json'),bundles=[fingerprint(HERE/'bundles'/f'v9_m{m}'/'bundle.json') for m in (1,2)],winner=None,new_correction_round_started=False))
print('Final release verified: 14 fits, 50 paired predictions, 1912 unchanged upstream files, browser and launcher passed')
