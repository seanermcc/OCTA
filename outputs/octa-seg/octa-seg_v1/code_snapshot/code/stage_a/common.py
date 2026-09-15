"""Fingerprinting and output helpers. All generated artifacts stay under outputs."""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs"
DEFAULT = OUT / "stage_a" / "20260908_v2"


def output_dir(path):
    path = Path(path).resolve()
    if not path.is_relative_to(OUT / "stage_a"):
        raise ValueError("Generated outputs must be inside outputs/stage_a")
    path.mkdir(parents=True, exist_ok=True)
    return path


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()


def fingerprint(path, sampled=False):
    path = Path(path).resolve()
    st = path.stat()
    h = hashlib.sha256()
    with path.open("rb") as f:
        if sampled:
            for offset in sorted({0, max(0, st.st_size // 2 - 524288),
                                  max(0, st.st_size - 1048576)}):
                f.seek(offset)
                h.update(f.read(1048576))
        else:
            for block in iter(lambda: f.read(1048576), b""):
                h.update(block)
    if path.stat().st_mtime_ns != st.st_mtime_ns:
        raise RuntimeError(f"Source changed during read: {path}")
    return dict(path=str(path), bytes=st.st_size, mtime_ns=st.st_mtime_ns,
                sha256=h.hexdigest(), hash_scope="three_1MiB_samples" if sampled else "full_file")


def verify(fp):
    actual = fingerprint(fp["path"], fp["hash_scope"] != "full_file")
    if actual != fp:
        raise RuntimeError(f"Fingerprint changed: {fp['path']}; create a new dataset version")


def write_json(path, obj):
    path = Path(path)
    output_dir(path.parent)
    content = json.dumps(obj, indent=2, allow_nan=False)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return  # Verification/resume must not change frozen file fingerprints.
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(content, encoding="utf-8")
    temp.replace(path)


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows):
    rows = list(rows)
    output_dir(Path(path).parent)
    with Path(path).open("w", encoding="utf-8", newline="") as f:
        if rows:
            w = csv.DictWriter(f, list(rows[0]))
            w.writeheader()
            w.writerows(rows)
