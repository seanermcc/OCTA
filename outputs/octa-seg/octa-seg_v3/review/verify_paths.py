"""Bounded restore/import and relocated launcher checks; no real annotations written."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile

here=Path(__file__).resolve().parent
root=next(p for p in here.parents if (p/'PIPELINE.md').exists() and (p/'code/octa').exists())
folder=here/'verification'/('paths '+time.strftime('%Y%m%d_%H%M%S'))
folder.mkdir()
archive=Path(json.loads((here/'migration.json').read_text())['archive'])
manifest=json.loads((archive/'manifest.json').read_text())
restore=folder/'restored project'
with zipfile.ZipFile(archive/'snapshot.zip') as z:
    for entry in manifest['files']:
        assert hashlib.sha256(z.read(entry['archive_path'])).hexdigest()==entry['sha256']
        # Restore executable/runtime/document files, leaving actual label backups in their zip.
        if Path(entry['archive_path']).suffix in ('.py','.cmd','.md'):
            target=restore/entry['archive_path']; target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(z.read(entry['archive_path']))
env=os.environ.copy()
env['PYTHONPATH']=os.pathsep.join(str(restore/p) for p in ('outputs/octa-seg/octa-seg_v3/code','outputs/octa-seg/octa-seg_v2/code','code'))
env['PYTHONDONTWRITEBYTECODE']='1'
result=subprocess.run([sys.executable,'-c','import octa_seg_v3.gui; print(octa_seg_v3.gui.__file__)'],cwd=folder,env=env,capture_output=True,text=True,check=True)
assert str(restore) in result.stdout
relocated=folder/'relocated project with spaces'
review=relocated/'outputs/octa-seg/octa-seg_v3/review'
(relocated/'code/octa').mkdir(parents=True)
shutil.copy2(root/'PIPELINE.md',relocated/'PIPELINE.md')
shutil.copy2(root/'code/octa/labels.py',relocated/'code/octa/labels.py')
shutil.copytree(here/'code',review/'code',ignore=shutil.ignore_patterns('__pycache__'))
shutil.copy2(here/'launch.py',review/'launch.py')
result=subprocess.run([sys.executable,str(review/'launch.py'),'--check-paths'],cwd=folder,env=env,capture_output=True,text=True,check=True)
assert str(relocated) in result.stdout
output=dict(archive_hashes_verified=len(manifest['files']),restored_old_gui_imported=True,
    new_launcher_paths_with_spaces=True,arbitrary_working_directory=True,directory=str(folder))
(here/'verification/path_verification.json').write_text(json.dumps(output,indent=2))
print(json.dumps(output,indent=2))
