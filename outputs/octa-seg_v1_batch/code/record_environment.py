from batch import *
import platform,importlib.metadata
packages={}
for name in ['numpy','scipy','torch','h5py','scikit-image','matplotlib','PySide6']:
    try:packages[name]=importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:packages[name]=None
from stage_a.geometry import PREPROCESS
write(OUT/'environment.json',dict(python=sys.version,executable=sys.executable,platform=platform.platform(),conda_environment=os.environ.get('CONDA_DEFAULT_ENV'),conda_prefix=os.environ.get('CONDA_PREFIX'),packages=packages,preprocessing=PREPROCESS))
write(OUT/'processing_provenance.json',dict(guard_manifest=fingerprint(V1/'data/manifest.json'),base_review_config=fingerprint(V1/'launch_config.json'),scripts=[fingerprint(p) for p in sorted((OUT/'code').glob('*.py'))],command_files=[fingerprint(p) for p in sorted(OUT.glob('*.cmd'))],note='Run-specific scripts were finalized while early scans ran; initial QC is upgraded to schema 2. Checkpoints, shared processing dependencies and thresholds are unchanged.'))
