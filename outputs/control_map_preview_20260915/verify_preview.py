"""Check delivered tables against saved native maps and enforce missing-data rules."""
from pathlib import Path
import json
import os
if os.name == "nt" and os.environ.get("CONDA_PREFIX"):
    _dll = os.add_dll_directory(str(Path(os.environ["CONDA_PREFIX"]) / "Library/bin"))
import numpy as np
import pandas as pd

out = Path(__file__).resolve().parent
status = json.loads((out/"run_status.json").read_text())
assert status["status"] == "preview_complete"
summary = pd.read_csv(out/"tables/local_summaries.csv")
selection = json.loads((out/"selection.json").read_text())["scans"]
checks = 0
for sid in selection:
    rows = summary[summary.scan_id == sid]
    assert len(rows) == 16, (sid, "All eight layers and both policies must be retained")
    with np.load(out/"maps"/(sid+"_preview.npz"), allow_pickle=False) as z:
        assert not np.isfinite(z["thickness"][:, z["shadow"].astype(bool)]).any()
        assert not (z["eligible_B"] & ~z["eligible_A"]).any()
        for version in ("A", "B"):
            for k,row in enumerate(rows[rows.version == version].itertuples()):
                values = z["thickness"][k][z["eligible_"+version]]
                values = values[np.isfinite(values)]
                assert len(values) == row.n
                if len(values):
                    assert np.isclose(values.mean(), row.mean_um, atol=1e-5)
                else:
                    assert pd.isna(row.mean_um)
                checks += 1
        if not rows.localized.any():
            assert np.isnan(z["onh_distance_um"]).all()
assert len(list((out/"fig").glob("*.png"))) == 10
assert (out/"index.html").is_file()
result = dict(passed=True, scans=len(selection), layer_policy_numeric_checks=checks,
    figures=10, checks=["Table counts and means match native arrays", "Shadow NaNs retained",
    "B is a subset of A", "Unresolved ONH coordinates withheld", "All eight layers retained"],
    scope="Output consistency, not anatomical accuracy")
(out/"verification.json").write_text(json.dumps(result, indent=2))
print(json.dumps(result))
