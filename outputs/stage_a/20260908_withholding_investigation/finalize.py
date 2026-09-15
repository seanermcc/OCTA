"""Final provenance check and clean summary figure; writes only here."""
import json
import importlib.metadata
from investigate import OUT,V2,fstat,package_hash
from stage_a.common import write_json,verify,fingerprint

before=json.loads((OUT/'integrity_before.json').read_text())
after=fstat()
assert before['files']==after, 'Frozen dataset files changed'
assert before['package_hashes']==package_hash(), 'Stage A package changed'
for fp in json.loads((OUT/'input_fingerprints.json').read_text()):
    verify(fp)
env=json.loads((V2/'environment_after.json').read_text())
names=['numpy','scipy','h5py','matplotlib','pandas','scikit-image']
versions={name:importlib.metadata.version(name) for name in names}
assert all(env['packages'][name]==version for name,version in versions.items())
summary=dict(frozen_files_size_mtime_unchanged=True,
    prediction_features_checkpoint_fingerprints_unchanged=True,
    training_package_content_unchanged=True,scientific_versions_unchanged=True,
    scientific_versions=versions,repeatability_data_read=False,
    final_test_arrays_read=False,labels_manifest_count=160,packs_manifest_count=32,
    footprints_manifest_count=28,full_label_integrity_reverified=False,
    helper_snapshot=fingerprint(OUT/'readability_helpers_snapshot.py'),
    no_inference_change_adopted=True)
write_json(OUT/'integrity_final.json',summary)

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
rows=json.loads((OUT/'candidate_metrics.json').read_text())
labels={'existing':'Existing mask','whole_crossing':'Whole column',
    'inversion_span':'Inversion span','whole_crossing_count_ge4':'Four flags',
    'whole_crossing_count_ge6':'Six flags','simple_q0.94':'Score q0.94',
    'simple_q0.96':'Score q0.96'}
colors=dict(zip(labels,['#333333','#d55e00','#0072b2','#009e73','#9467bd','#cc79a7','#e69f00']))
fig,axs=plt.subplots(1,2,figsize=(11.5,4.8),layout='constrained')
for ax,split in zip(axs,['train','validation']):
    for row in rows:
        method=row['method']
        if row['group']!='split' or row['value']!=split or method not in labels: continue
        x=row['supported_coverage']*100;y=row['unreadable_leakage']*100
        ax.scatter(x,y,s=45,color=colors[method])
        dx,dy=5,7
        if method=='whole_crossing_count_ge4': dy=-16
        if method=='whole_crossing_count_ge6': dx,dy=-48,-14
        if method=='existing': dx,dy=-65,6
        ax.annotate(labels[method],(x,y),xytext=(dx,dy),textcoords='offset points',fontsize=8)
    ax.margins(x=.15,y=.15)
    ax.set(xlabel='Human-supported boundary measurements retained (%)',
           ylabel='Manually unreadable measurements retained (%)',title=split.title())
    ax.grid(alpha=.2)
fig.suptitle('Frozen-model withholding: benefit and coverage cost\nExperimental; two corrected validation animals',fontsize=12)
fig.savefig(OUT/'coverage_tradeoff.png',dpi=150)
plt.close(fig)
print(json.dumps(summary,indent=2))
