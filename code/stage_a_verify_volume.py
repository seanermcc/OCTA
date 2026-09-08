"""Verify completed smoke volume geometry, masks, and resumable chunk identity."""
import json
from pathlib import Path
import numpy as np
from stage_a.common import DEFAULT,write_json,fingerprint
from stage_a.geometry import to_disk_rows

root=DEFAULT/"smoke_volume"
summary=json.loads((root/"inference.json").read_text())
assert summary["full_volume_complete"]
chunks=sorted(root.glob("b[0-9][0-9][0-9][0-9].npz"))
assert len(chunks)==512
before=[]
max_inverse_error=0.0
for path in chunks:
    with np.load(path,allow_pickle=False) as p:
        assert str(p["job_id"])==summary["job_id"]
        assert p["canonical_rows"].shape==(8,512)
        assert p["disk_rows"].shape==(8,512)
        restored=to_disk_rows(p["disk_rows"],int(p["native_shape"][2]),bool(p["vitreous_high"]))
        error=float(np.max(np.abs(restored-p["canonical_rows"])))
        assert error<1e-3  # Float32 coordinate storage, not a spatial resampling.
        max_inverse_error=max(max_inverse_error,error)
        assert np.isnan(p["retained_rows"][~p["retained"]]).all()
        assert not p["retained"][:,p["shadow"]|~p["scope"]].any()
        assert np.isnan(p["validated_thickness_um"]).all()
        assert not bool(p["validated"])
    before.append(fingerprint(path))
result=dict(checked_bscans=len(chunks),original_coordinate_inverse_max_error_px=max_inverse_error,
    withheld_rows_nan=True,scope_and_shadow_exclusions=True,validated_measurements_unavailable=True,
    chunk_fingerprints=before)
prior=DEFAULT/"volume_test_results.json"
if prior.exists():
    old=json.loads(prior.read_text())
    assert old["chunk_fingerprints"]==before
    result["resume_preserved_all_chunk_fingerprints"]=True
write_json(prior,result)
print({k:v for k,v in result.items() if k!="chunk_fingerprints"})
