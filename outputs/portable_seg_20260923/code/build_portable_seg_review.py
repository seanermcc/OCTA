"""Build a cache-only review copy. Copies human records byte-for-byte; never creates labels."""
import argparse
import hashlib
import importlib.metadata as metadata
import json
import shutil
import sys
import time
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / 'outputs/octa-seg/octa-seg_v3/review'
sys.dont_write_bytecode = True
sys.path[:0] = [str(REVIEW/'code'), str(REVIEW.parent.parent/'octa-seg_v2/code'), str(ROOT/'code')]
from octa_seg_v3.common import read, fingerprint
from octa_seg_v3.data import load_volume, local_path
from octa_seg_v3.saved import index
from octa_seg_v3.feedback import resolve, training_targets
from octa_seg_v3.providers import context_overlays
from octa_seg_v3.portable import key


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--destination', type=Path, required=True)
    args=parser.parse_args()
    dest=args.destination.resolve()
    if dest.exists() and any(dest.iterdir()):
        raise RuntimeError('Destination must be empty; existing work will not be overwritten')
    dest.mkdir(parents=True, exist_ok=True)
    rows=index('lead', include_tags=True)
    selected=[r for r in rows if r['status']=='Confirmed']
    sids=sorted({r['scan_id'] for r in selected})
    manifest=dict(format='octa-portable-cache-1',created_at=time.strftime('%Y-%m-%d %H:%M:%S'),
        selection='All acquisitions with at least one currently confirmed lead B-scan; sharing flags do not filter selection',
        scans={},aliases={},files={},confirmed_cases=[],copied_human_files={},reviewer='lead',
        overlays='Frozen default context snapshot at export; no external overlay refresh')

    def add_file(source, relative=None):
        source=Path(source)
        relative=relative or source.relative_to(ROOT).as_posix()
        target=dest/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        before=fingerprint(source)
        shutil.copy2(source,target)
        if fingerprint(target)!=before or fingerprint(source)!=before:
            raise RuntimeError('Source changed during copying: '+str(source))
        manifest['files'][relative]=dict(sha256=before,bytes=target.stat().st_size)
        return relative

    # Repository code is small; include its imports, preserving the project layout.
    for base in (ROOT/'code', REVIEW/'code', REVIEW.parent.parent/'octa-seg_v2/code'):
        for p in base.rglob('*.py'):
            add_file(p)
    for p in (ROOT/'PIPELINE.md',ROOT/'AGENTS.md',REVIEW/'launch.py'):
        add_file(p)
    for p in REVIEW.glob('*.md'):
        add_file(p)
    calibration=ROOT/'outputs/octa-seg/octa-seg_v1/calibration/deployment_vessels.json'
    cal_rel=add_file(calibration)
    roles=ROOT/'outputs/octa-seg/octa-seg_v2/round_000/review_queue.json'
    if roles.exists(): add_file(roles)

    for sid in sids:
        scan_rows=[r for r in rows if r['scan_id']==sid]
        confirmed=[r for r in selected if r['scan_id']==sid]
        providers={local_path(r['source']['provider']).resolve() for r in scan_rows}
        if len(providers)!=1:
            raise RuntimeError('Multiple frozen providers need explicit packaging: '+sid)
        provider=providers.pop()
        print('Preparing',sid,flush=True)
        volume=load_volume(dict(scan_id=sid,directory=str(provider)),image_budget=0)
        prep=read(provider/'prepared.json')
        directory=provider.relative_to(ROOT).as_posix()
        required=[cal_rel]
        for name in ('prepared.json','measurements.npz','geometry.npz'):
            required.append(add_file(provider/name))
        image=local_path(prep['images'])
        image_rel=add_file(image)
        required.append(image_rel)
        for value in [str(provider),*(r['source']['provider'] for r in scan_rows)]:
            manifest['aliases'][key(value)]=directory
        manifest['aliases'][key(prep['images'])]=image_rel
        for r in scan_rows:
            manifest['aliases'][key(r['source']['image_path'])]=image_rel

        proposal=ROOT/'outputs/octa-seg/octa-seg_v2/proposals'
        if not (proposal/f'{sid}_proposal.npz').exists(): proposal=ROOT/'outputs/octa-seg_v1_batch/proposals'
        overlays=context_overlays(volume,proposal)
        if overlays[4].get('errors'):
            raise RuntimeError('Cannot silently package unavailable context: '+str(overlays[4]['errors']))
        context=f'portable_context/{sid}.npz'
        (dest/'portable_context').mkdir(exist_ok=True)
        np.savez_compressed(dest/context,**dict(zip(('cnv','vessel','onh','edge'),overlays[:4])))
        context_meta=f'portable_context/{sid}.json'
        meta=dict(overlays[4],portable_snapshot=True,snapshot_at=manifest['created_at'])
        meta['status']='Portable snapshot '+manifest['created_at']+' · '+meta.get('status','')
        (dest/context_meta).write_text(json.dumps(meta,indent=2),encoding='utf-8')
        for rel in (context,context_meta):
            manifest['files'][rel]=dict(sha256=fingerprint(dest/rel),bytes=(dest/rel).stat().st_size)
        manifest['scans'][sid]=dict(directory=directory,required_files=required,context=context,
            context_metadata=context_meta,source_identity=str(volume.scan.source_volume),
            source_fingerprint=prep['source'],model_id=volume.model_id,image_shape=list(volume.images.shape),
            confirmed_bscans=[r['bscan'] for r in confirmed])
        for r in confirmed:
            record=read(r['path'])
            if record['model_id']!=volume.model_id: raise RuntimeError('Frozen model differs: '+r['path'])
            state=resolve(record['events'][:record['cursor']],volume.data['raw_position_branch'][r['bscan']],
                          int(volume.data['label_offset']),volume.images.shape[1])
            if state['review_status']!='Confirmed': raise RuntimeError('Confirmation is stale: '+r['path'])
            # Checks confirmation identity against the original journal; no new label is produced.
            training_targets(record,volume.data['raw_position_branch'][r['bscan']],int(volume.data['label_offset']),
                volume.images.shape[1],volume.data['shadow'][r['bscan']],vessel=overlays[1][r['bscan']])
            manifest['confirmed_cases'].append(dict(scan_id=sid,bscan=r['bscan'],path=Path(r['path']).relative_to(ROOT).as_posix()))
        del volume

    # Preserve complete selected-case journals, history, labels and context exposure.
    for base in (REVIEW/'reviewers/lead', REVIEW.parent/'reviewers/lead'):
        for p in base.rglob('*'):
            if p.is_file() and p.suffix in ('.json','.npz') and any(p.name.startswith(sid) for sid in sids):
                rel=add_file(p)
                manifest['copied_human_files'][rel]=manifest['files'][rel]['sha256']

    review_rel=REVIEW.relative_to(ROOT).as_posix()
    first=manifest['confirmed_cases'][0]
    (dest/'OPEN_REVIEWER.cmd').write_text('@echo off\nsetlocal\ncall "%~dp0ACTIVATE_OCTA.cmd"\nif errorlevel 1 (pause & exit /b 1)\nset "PYTHONDONTWRITEBYTECODE=1"\npython "%~dp0'+review_rel.replace('/','\\')+'\\launch.py" --reviewer lead %*\nif errorlevel 1 pause\n',encoding='utf-8')
    (dest/'ACTIVATE_OCTA.cmd').write_text('''@echo off
if defined CONDA_PREFIX if exist "%CONDA_PREFIX%\\python.exe" for %%I in ("%CONDA_PREFIX%") do if /I "%%~nxI"=="octa" exit /b 0
if defined OCTA_CONDA_ACTIVATE if exist "%OCTA_CONDA_ACTIVATE%" (call "%OCTA_CONDA_ACTIVATE%" octa & exit /b)
for %%P in ("%USERPROFILE%\\miniconda3\\Scripts\\activate.bat" "%USERPROFILE%\\anaconda3\\Scripts\\activate.bat" "%LOCALAPPDATA%\\miniconda3\\Scripts\\activate.bat" "%ProgramData%\\miniconda3\\Scripts\\activate.bat" "%ProgramData%\\anaconda3\\Scripts\\activate.bat" "D:\\Anaconda\\Scripts\\activate.bat") do if exist "%%~P" (call "%%~P" octa & exit /b)
echo Activate your octa conda environment, then run OPEN_REVIEWER.cmd again.
echo For a new computer, read START_HERE.md for setup.
exit /b 1
''',encoding='utf-8')
    # Session is navigation state, not a label.
    session=dest/review_rel/'reviewers/lead/session.json'
    session.parent.mkdir(parents=True,exist_ok=True)
    session.write_text(json.dumps(dict(reviewer_id='lead',scan_id=first['scan_id'],bscan=first['bscan'])),encoding='utf-8')
    deps=('numpy','scipy','h5py','matplotlib','pandas','scikit-image','PySide6')
    (dest/'requirements-reviewer.txt').write_text('\n'.join(f'{n}=={metadata.version(n)}' for n in deps)+'\n',encoding='utf-8')
    (dest/'START_HERE.md').write_text(f'''# Portable octa-seg_v3 reviewer

Double-click **OPEN_REVIEWER.cmd**. This is your **lead** continuation copy.
Contains {len(sids)} acquisitions / {len(selected)} confirmed B-scans, plus other saved work in these acquisitions.
All cached B-scans remain available. Original human journals and labels are copied unchanged.
No RAW or processed MAT source files are required. Keep this entire folder together when moving it.
Predictions, cache geometry and calibration are hash-checked. Source paths in records identify provenance only.
CNV/vessel/ONH overlays are frozen at {manifest['created_at']}; Refresh reloads that snapshot.
Experimental ONH proposals are not included. This package is not a live link to the home data.

## On a new Windows computer

Install Miniconda if needed. In its prompt, run:

```
conda create -n octa python=3.11 pip
conda activate octa
cd /d "H:\\octa\\For_Segmentation"
python -m pip install -r requirements-reviewer.txt
OPEN_REVIEWER.cmd
```

Use the actual folder path if the drive letter differs. Installing dependencies needs internet once.
The Python environment is not bundled. If Anaconda is in an unusual location, activate octa first,
or set OCTA_CONDA_ACTIVATE to its Scripts\\activate.bat path.

## Saving and returning work

Work saves locally under `{review_rel}/reviewers/lead/`.
Close the reviewer before copying. Return that entire folder, including journals/history and surface_labels.
Do not edit the same lead case on home and portable copies concurrently or blindly overwrite a newer copy.
This package includes your answers: prepare a separate annotation-free assignment before giving it to a coworker.
The nine sharing flags remain unchanged; inclusion here does not flag additional cases for colleagues.

## Validation

See PORTABLE_VALIDATION.json and PORTABLE_CACHE.json for executed checks and the exact inventory.
''',encoding='utf-8')
    manifest['bytes_at_build']=sum(p.stat().st_size for p in dest.rglob('*') if p.is_file())
    (dest/'PORTABLE_CACHE.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps(dict(destination=str(dest),confirmed=len(selected),volumes=len(sids),GB=manifest['bytes_at_build']/1e9)),flush=True)

if __name__=='__main__': main()
