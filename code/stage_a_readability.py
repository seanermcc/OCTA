"""Readability-aware withholding for the Stage A U-Net: display, audit, pilot.

Lives OUTSIDE the `stage_a` package on purpose. `stage_a.train.code_identity()`
hashes every module in that directory; adding code there would invalidate resume
for the already-trained `dev_seed20260908` checkpoints. Nothing here modifies a
label, a manifest, a partition, a checkpoint or an existing evaluation. It reads
the frozen derived targets, the frozen image caches and the prediction arrays a
`stage_a.evaluate` run already wrote. It refuses the test split everywhere.

Subcommands
-----------
display   Corrected review overlays. The default *measurement* view breaks every
          surface where the saved ``retained`` mask withholds it (NaN gap, never
          zero, never interpolated) and prints the per-column exclusion reason.
          ``--raw`` additionally writes the old unbroken-line diagnostic.
audit     Existing withholding mask vs. human evidence, train + dev-validation
          animals only. Keeps manual-unreadable / classical-shadow / CNV-scope /
          crossing / uncertainty as separate reasons and reports their overlap.
features  Per-A-line feature table (entropy from a checkpoint + local signal /
          contrast / continuity) plus per-column readability supervision, for
          train + dev-validation. Written once, reused by ``compare``.
compare   Existing mask vs. a simple entropy+signal candidate vs. a small learned
          readability model, at matched supported-tissue coverage.

Outputs default to outputs/stage_a/20260908_v3_readability/; --out selects a new root.
"""
import argparse
import json
from pathlib import Path

import numpy as np

from stage_a.common import DEFAULT, OUT, output_dir, write_json, write_csv, verify, fingerprint
from stage_a.partitions import validate_partition
from stage_a.geometry import PREPROCESS
from eight_surface.config import SURFACE_NAMES, LAYER_DEFS

# Mirrored from stage_a.inference (that module imports torch; this one stays
# torch-free so matplotlib's MKL and torch's libomp never load in one process).
REASONS = {"outside_scope": 1, "shadow": 2, "missing": 4, "crossing": 8, "uncertainty": 16}


def retained_thickness(rows, retained, px_um):
    out = {}
    for name, top, bottom in LAYER_DEFS:
        i, j = SURFACE_NAMES.index(top), SURFACE_NAMES.index(bottom)
        good = (retained[i] & retained[j] & np.isfinite(rows[i]) & np.isfinite(rows[j])
                & (rows[j] >= rows[i]))
        out[name] = np.where(good, (rows[j] - rows[i]) * px_um, np.nan).astype(np.float32)
    return out

V3 = OUT / "stage_a" / "20260908_v3_readability"

# Animals whose data this task may touch. Final-test animals are never listed.
TRAIN_ANIMALS = ["TS165", "TS241", "TS250", "TS267", "TS305"]
VAL_ANIMALS = ["TS169", "TS325", "TS336"]
CORRECTED_VAL_ANIMALS = ["TS169", "TS325"]  # TS336 is rejected-only

GROSS_UM = 25.0  # provisional reporting cutoff, not an acceptance threshold

# Target-side supervision reason bits (from stage_a.eligibility.supervision + audit).
SUP_BITS = {"not_corrected": 1, "unedited": 2, "not_visible": 4, "unreliable": 8,
            "displaced": 16, "image_excluded": 32, "outside_stage_a_scope": 64,
            "nonfinite_target": 128, "shadow": 256, "wrong_contract": 512,
            "outside_review_image": 1024}

REASON_LABEL = {1: "outside CNV scope", 2: "classical shadow", 4: "non-finite",
                8: "boundary crossing", 16: "entropy / uncertainty"}
REASON_COLOR = {1: "#8c6bb1", 2: "#3182bd", 4: "#636363", 8: "#e6550d", 16: "#d62728"}


# --------------------------------------------------------------------------- #
# Frozen split loading (torch-free; repeats Dataset's integrity checks).
# --------------------------------------------------------------------------- #
class FrozenSplit:
    def __init__(self, path, split):
        if split == "test":
            raise ValueError("Final-test animals are locked")
        self.path = Path(path)
        self.manifest = json.loads((self.path / "manifest.json").read_text())
        self.partitions = json.loads((self.path / "partitions.json").read_text())
        self.cache = json.loads((self.path / "cache_manifest.json").read_text())
        validate_partition(self.manifest, self.partitions)
        verify(self.partitions["manifest"])
        if (self.cache["dataset_id"] != self.manifest["dataset_id"]
                or self.cache["preprocessing"] != PREPROCESS):
            raise ValueError("Cache/dataset preprocessing identity mismatch")
        keys = set(self.partitions["keys"][split]) if split != "trainval" else set(
            self.partitions["keys"]["train"]) | set(self.partitions["keys"]["validation"])
        self.records = [r for r in self.manifest["records"] if r["key"] in keys]
        if not self.records:
            raise ValueError("Empty partition")
        for r in self.records:
            if r["key"] in self.cache["entries"]:
                verify(self.cache["entries"][r["key"]]["file"])
            verify(r["targets_fingerprint"])
        self.dataset_id = self.manifest["dataset_id"]
        self.partition_id = self.partitions["partition_id"]

    def cache_entry(self, key):
        return self.cache["entries"][key]


def load_npz(path):
    with np.load(path, allow_pickle=False) as d:
        return {k: d[k].copy() for k in d.files}


def contiguous_runs(mask):
    mask = np.asarray(mask, bool)
    bounds = np.diff(np.r_[False, mask, False].astype(np.int8))
    starts = np.flatnonzero(bounds == 1)
    ends = np.flatnonzero(bounds == -1) - 1
    return list(zip(starts.tolist(), ends.tolist()))


def longest_run(mask):
    runs = contiguous_runs(mask)
    return max((b - a + 1 for a, b in runs), default=0)


def runs_str(mask):
    return ", ".join(f"{a}-{b}" for a, b in contiguous_runs(mask)) or "(none)"


# --------------------------------------------------------------------------- #
# display
# --------------------------------------------------------------------------- #
def _prepare_overlay_inputs(rec, split_obj, evaldir):
    key = rec["key"]
    pred = load_npz(Path(evaldir) / f"{key}.npz")
    tgt = load_npz(rec["targets"])
    entry = split_obj.cache_entry(key)
    cache = load_npz(entry["file"]["path"])
    offset = int(entry["label_offset"])
    image = cache["x"][0]
    vhi = bool(cache["vitreous_high"])
    return pred, tgt, image, vhi, offset


def _draw_overlay(path, image, vhi, offset, pred, tgt, title, mode, px_um=1.12):
    """mode='measurement' breaks lines at ~retained; mode='raw' draws them whole."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    ns = len(SURFACE_NAMES)
    native_depth = image.shape[0]
    disk = image[::-1] if vhi else image
    to_disk = (lambda r: native_depth - 1 - np.asarray(r, float)) if vhi else (lambda r: np.asarray(r, float).copy())
    W = disk.shape[1]
    x = np.arange(W)

    rows = pred["rows"]
    retained = pred["retained"].astype(bool)
    entropy = pred.get("entropy", np.zeros_like(rows))
    valid = tgt["valid"].astype(bool)
    truth = tgt["rows_label"]
    reason_bits = pred["reason_bits"].astype(np.uint16)

    fig, ax = plt.subplots(3, 1, figsize=(12, 9), height_ratios=[5, 1.1, 1.4],
                           constrained_layout=True)
    ax[0].imshow(disk, cmap="gray", aspect="auto", vmin=-0.1, vmax=1.1,
                 extent=[0, W, disk.shape[0], 0])
    colours = plt.cm.turbo(np.linspace(.05, .95, ns))
    shown = []
    for k, name in enumerate(SURFACE_NAMES):
        line = to_disk(rows[k] + offset)
        if mode == "measurement":
            line = np.where(retained[k], line, np.nan)
        ax[0].plot(x, line, color=colours[k], lw=1.1, label=name)
        t = np.where(valid[k], to_disk(truth[k] + offset), np.nan)
        ax[0].plot(x, t, color=colours[k], lw=2.3, ls=":", alpha=.85)
        shown += [line, t]
    stacked = np.concatenate([s[np.isfinite(s)] for s in shown]) if shown else np.array([0.])
    if stacked.size:
        ax[0].set_ylim(min(disk.shape[0], stacked.max() + 60), max(0, stacked.min() - 60))
    tag = "MEASUREMENT VIEW - gaps = withheld from measurement" if mode == "measurement" \
        else "RAW DIAGNOSTIC - every predicted column drawn, NOT the measurement view"
    ax[0].set_title(f"{tag}\n{title}", fontsize=8)
    ax[0].set_ylabel("original disk depth (px)")
    ax[0].legend(fontsize=6, ncol=ns, loc="lower center", framealpha=.35)

    # --- exclusion-reason tracks -------------------------------------------- #
    model_reasons = [1, 2, 8, 16, 4]
    # human-marked unreadable and CNV-scope come from the frozen target arrays,
    # shown as reference context (not part of the model's own retained mask).
    t_bits = tgt["reason_bits"].astype(np.uint16)
    human_unreadable = ((t_bits & SUP_BITS["image_excluded"]) != 0).any(0)
    cnv_scope_out = ~tgt["scope"].astype(bool)
    tracks = []
    for bit in model_reasons:
        col = ((reason_bits & bit) != 0).any(0)
        if col.any():
            tracks.append((REASON_LABEL[bit], REASON_COLOR[bit], col))
    if human_unreadable.any():
        tracks.append(("human-marked unreadable (ref)", "#000000", human_unreadable))
    if cnv_scope_out.any():
        tracks.append(("CNV footprint+buffer (ref)", "#7570b3", cnv_scope_out))
    ax[1].set_xlim(0, W)
    ax[1].set_ylim(0, max(1, len(tracks)))
    ax[1].set_yticks([])
    for i, (lbl, colr, col) in enumerate(tracks):
        y = len(tracks) - 1 - i
        for a, b in contiguous_runs(col):
            ax[1].axvspan(a, b + 1, ymin=y / max(1, len(tracks)), ymax=(y + 1) / max(1, len(tracks)),
                          color=colr, alpha=.55 if not lbl.endswith("(ref)") else .3,
                          hatch=None if not lbl.endswith("(ref)") else "//")
        ax[1].text(2, y + .5, lbl, va="center", ha="left", fontsize=6.5)
    ax[1].set_title("per-A-line exclusion reasons (union over surfaces); solid = model retained mask, hatched = frozen human/scope reference", fontsize=6.5)

    # --- thickness with NaN gaps, from the retained rows only -------------- #
    bands = retained_thickness(rows, retained, px_um)
    for (name, top, bot), colr in zip(LAYER_DEFS, plt.cm.tab10(np.linspace(0, 1, len(LAYER_DEFS)))):
        ax[2].plot(x, bands[name], color=colr, lw=.9, label=name)
    ax[2].set_xlim(0, W)
    ax[2].set_ylabel("retained\nthickness (um)")
    ax[2].set_xlabel("A-line (original column order) | solid = prediction, dotted = human target where eligible")
    ax[2].legend(fontsize=5.5, ncol=len(LAYER_DEFS), loc="upper center", framealpha=.35)

    fig.savefig(path, dpi=125)
    plt.close(fig)


def cmd_display(args):
    split_obj = FrozenSplit(args.data, args.split)
    out = output_dir(args.out / "review" / args.split)
    evaldir = Path(args.eval)
    recs = [r for r in split_obj.records if (Path(evaldir) / f"{r['key']}.npz").exists()]
    if args.keys:
        want = set(args.keys)
        recs = [r for r in recs if r["key"] in want]
    index = []
    for r in recs:
        pred, tgt, image, vhi, offset = _prepare_overlay_inputs(r, split_obj, evaldir)
        if not tgt["valid"].any() and not args.include_ineligible:
            continue
        retained = pred["retained"].astype(bool)
        valid = tgt["valid"].astype(bool)
        title = (f"{r['key']} | {r['animal']} QC={r['qc_group']} | {r['scope_status']} | "
                 f"verdict={r['verdict']} | retained {int(retained.sum())}/{retained.size} "
                 f"boundary-cols | EXPERIMENTAL, not validated")
        m_path = out / f"{r['key']}__measurement.png"
        _draw_overlay(m_path, image, vhi, offset, pred, tgt, title, "measurement", r["px_um"])
        row = dict(key=r["key"], animal=r["animal"], qc_group=r["qc_group"],
                   scope_status=r["scope_status"], verdict=r["verdict"],
                   n_eligible_cols=int(valid.sum()),
                   retained_frac_of_eligible=float((retained & valid).sum() / max(1, valid.sum())),
                   shadow_cols=runs_str(((pred["reason_bits"] & REASONS["shadow"]) != 0).any(0)),
                   crossing_cols=runs_str(((pred["reason_bits"] & REASONS["crossing"]) != 0).any(0)),
                   human_unreadable_cols=runs_str(((tgt["reason_bits"] & SUP_BITS["image_excluded"]) != 0).any(0)),
                   measurement_png=m_path.name)
        if args.raw:
            rraw = out / f"{r['key']}__raw_diagnostic.png"
            _draw_overlay(rraw, image, vhi, offset, pred, tgt, title, "raw", r["px_um"])
            row["raw_png"] = rraw.name
        index.append(row)
    write_csv(out / "display_index.csv", index)
    write_json(out / "display_meta.json", dict(
        dataset_id=split_obj.dataset_id, partition_id=split_obj.partition_id, split=args.split,
        eval_dir=str(evaldir), n_overlays=len(index),
        default_view="measurement (surface lines broken at ~retained; withheld thickness stays NaN)",
        raw_view="separate *_raw_diagnostic.png when --raw is passed",
        note="No threshold added; retained mask and predictions are the frozen stage_a.evaluate arrays. "
             "Excluded thickness is NaN, never zero or interpolated.",
        experimental=True, validated=False))
    print(f"{len(index)} measurement overlays -> {out}")


# --------------------------------------------------------------------------- #
# audit  -- existing withholding vs. human evidence (train + dev-validation)
# --------------------------------------------------------------------------- #
SHADOW_BIT = SUP_BITS["shadow"]          # 256
MANUAL_BIT = SUP_BITS["image_excluded"]  # 32


def _supervision_categories(t_bits):
    """Per-(surface,column) readability categories from the frozen target bits.

    human_positive : a human edited + saw + trusted this boundary here (shadow
                     may still be set -> that is the 'withheld despite support'
                     case).  reason_bits with only the shadow bit tolerated.
    human_negative : column-level manual 'image unusable' mark (region_excluded).
    otherwise        unknown (unreviewed / unedited / not-visible / displaced /
                     unreliable / out-of-scope / rejected verdict).
    """
    t_bits = np.asarray(t_bits, np.uint16)
    human_positive = (t_bits & ~np.uint16(SHADOW_BIT)) == 0
    human_negative = (t_bits & MANUAL_BIT) != 0
    return human_positive, human_negative


def _agg_rows(records, split_name, evaldir, gross_um):
    per = []
    for r in records:
        ev = Path(evaldir) / f"{r['key']}.npz"
        if not ev.exists():
            continue
        pred = load_npz(ev)
        tgt = load_npz(r["targets"])
        t_bits = tgt["reason_bits"].astype(np.uint16)
        retained = pred["retained"].astype(bool)
        rows = pred["rows"].astype(float)
        truth = tgt["rows_label"].astype(float)
        pos, neg = _supervision_categories(t_bits)
        col_manual = ((t_bits & MANUAL_BIT) != 0).any(0)
        col_shadow = tgt["shadow"].astype(bool)
        col_scope_out = ~tgt["scope"].astype(bool)
        col_cross = ((pred["reason_bits"].astype(np.uint16) & REASONS["crossing"]) != 0).any(0)
        err = (rows - truth) * r["px_um"]
        for k, sname in enumerate(SURFACE_NAMES):
            pk, nk, rk = pos[k], neg[k], retained[k]
            support_ret = pk & rk & np.isfinite(rows[k])          # scored tissue
            ae = np.abs(err[k][support_ret])
            gross = support_ret & (np.abs(err[k]) > gross_um)
            per.append(dict(
                split=split_name, key=r["key"], scan_id=r["scan_id"], bscan=r["bscan"],
                animal=r["animal"], surface=sname, qc_group=r["qc_group"],
                biological_group=r["biological_group"], scope_status=r["scope_status"],
                verdict=r["verdict"],
                n_cols=int(rows.shape[1]),
                n_human_positive=int(pk.sum()),
                n_human_negative=int(nk.sum()),
                # leakage: explicitly-unreadable columns the mask still measures
                unreadable_measured=int((nk & rk & np.isfinite(rows[k])).sum()),
                # over-withholding: human-supported columns the mask drops
                supported_withheld=int((pk & ~rk).sum()),
                supported_withheld_shadow_only=int((pk & ~rk & col_shadow & ~col_manual & ~col_scope_out).sum()),
                supported_total=int(pk.sum()),
                # retained-tissue error on human-supported columns
                scored=int(support_ret.sum()),
                median_abs_um=float(np.median(ae)) if ae.size else None,
                p95_abs_um=float(np.quantile(ae, .95)) if ae.size else None,
                mean_signed_um=float(err[k][support_ret].mean()) if ae.size else None,
                gross_frac=float(gross.sum() / support_ret.sum()) if support_ret.sum() else None,
                longest_gross_run=int(longest_run(gross)),
                # whole-image rejection behaviour
                rejected_bscan=r["verdict"] == "rejected",
                retained_cols_on_rejected=int(rk.sum()) if r["verdict"] == "rejected" else None,
            ))
        # column-level overlap of the five reasons (surface-independent ones)
        per[-1]  # keep lint quiet
    return per


def _overlap(records, split_name, evaldir):
    rows = []
    for r in records:
        ev = Path(evaldir) / f"{r['key']}.npz"
        if not ev.exists():
            continue
        pred = load_npz(ev)
        tgt = load_npz(r["targets"])
        t_bits = tgt["reason_bits"].astype(np.uint16)
        manual = ((t_bits & MANUAL_BIT) != 0).any(0)
        shadow = tgt["shadow"].astype(bool)
        scope_out = ~tgt["scope"].astype(bool)
        cross = ((pred["reason_bits"].astype(np.uint16) & REASONS["crossing"]) != 0).any(0)
        unc = ((pred["reason_bits"].astype(np.uint16) & REASONS["uncertainty"]) != 0).any(0)
        names = dict(manual_unreadable=manual, classical_shadow=shadow,
                     cnv_scope_out=scope_out, boundary_crossing=cross, uncertainty=unc)
        rows.append(dict(split=split_name, key=r["key"], animal=r["animal"],
                         verdict=r["verdict"], n_cols=int(len(manual)),
                         **{f"n_{k}": int(v.sum()) for k, v in names.items()},
                         **{f"n_{a}_AND_{b}": int((names[a] & names[b]).sum())
                            for i, a in enumerate(names) for b in list(names)[i + 1:]},
                         manual_covered_by_shadow=int((manual & shadow).sum()),
                         manual_not_covered_by_anything=int(
                             (manual & ~shadow & ~scope_out & ~cross).sum())))
    return rows


def _summarise(per, by):
    keys = sorted({tuple(p[b] for b in by) for p in per})
    out = []
    for kv in keys:
        grp = [p for p in per if tuple(p[b] for b in by) == kv]
        hp = sum(p["n_human_positive"] for p in grp)
        hn = sum(p["n_human_negative"] for p in grp)
        scored = sum(p["scored"] for p in grp)
        aes = [p["median_abs_um"] for p in grp if p["median_abs_um"] is not None]
        p95s = [p["p95_abs_um"] for p in grp if p["p95_abs_um"] is not None]
        signed = [p["mean_signed_um"] for p in grp if p["mean_signed_um"] is not None]
        rej = [p for p in grp if p["rejected_bscan"]]
        row = dict(zip(by, kv))
        row.update(
            n_bscan_surface=len(grp),
            human_positive_cols=hp, human_negative_cols=hn,
            unreadable_measured_cols=sum(p["unreadable_measured"] for p in grp),
            unreadable_measured_frac=(sum(p["unreadable_measured"] for p in grp) / hn) if hn else None,
            supported_withheld_cols=sum(p["supported_withheld"] for p in grp),
            supported_withheld_frac=(sum(p["supported_withheld"] for p in grp) / hp) if hp else None,
            supported_withheld_shadow_only_cols=sum(p["supported_withheld_shadow_only"] for p in grp),
            scored_cols=scored,
            retained_coverage_of_supported=(scored / hp) if hp else None,
            median_abs_um=float(np.median(aes)) if aes else None,
            p95_abs_um_of_bscan_p95=float(np.median(p95s)) if p95s else None,
            worst_p95_abs_um=float(np.max(p95s)) if p95s else None,
            mean_signed_um=float(np.mean(signed)) if signed else None,
            max_longest_gross_run=max((p["longest_gross_run"] for p in grp), default=0),
            rejected_bscan_surface_rows=len(rej),
            mean_retained_cols_on_rejected=(float(np.mean([p["retained_cols_on_rejected"] for p in rej]))
                                            if rej else None),
        )
        out.append(row)
    return out


def cmd_audit(args):
    tr = FrozenSplit(args.data, "train")
    va = FrozenSplit(args.data, "validation")
    tr_recs = [r for r in tr.records if r["animal"] in TRAIN_ANIMALS]
    va_recs = [r for r in va.records if r["animal"] in VAL_ANIMALS]
    out = output_dir(args.out / "audit")

    per = _agg_rows(tr_recs, "train", args.eval_train, args.gross_um) \
        + _agg_rows(va_recs, "validation", args.eval_val, args.gross_um)
    write_csv(out / "per_bscan_surface.csv", per)

    overlap = _overlap(tr_recs, "train", args.eval_train) \
        + _overlap(va_recs, "validation", args.eval_val)
    write_csv(out / "reason_overlap_per_bscan.csv", overlap)

    for by, fname in [(("surface",), "by_surface.csv"),
                      (("animal",), "by_animal.csv"),
                      (("qc_group",), "by_qc_group.csv"),
                      (("biological_group",), "by_biology.csv"),
                      (("scope_status",), "by_scope_status.csv"),
                      (("animal", "surface"), "by_animal_surface.csv"),
                      (("split",), "by_split.csv")]:
        write_csv(out / fname, _summarise(per, by))

    # headline pooled numbers + reason overlap totals
    pooled = _summarise(per, ("split",))
    all_pooled = _summarise([{**p, "_": "all"} for p in per], ("_",))[0]
    ov_tot = {k: int(sum(o[k] for o in overlap)) for k in overlap[0] if k.startswith("n_") or k.startswith("manual_")}
    rej_rows = [p for p in per if p["rejected_bscan"]]
    summary = dict(
        dataset_id=tr.dataset_id, partition_id=tr.partition_id,
        animals=dict(train=sorted({r["animal"] for r in tr_recs}),
                     validation=sorted({r["animal"] for r in va_recs})),
        gross_um=args.gross_um,
        eval_train=str(args.eval_train), eval_val=str(args.eval_val),
        headline=dict(
            unreadable_tissue_still_measured=dict(
                cols=all_pooled["unreadable_measured_cols"],
                of_manual_unreadable_cols=all_pooled["human_negative_cols"],
                fraction=all_pooled["unreadable_measured_frac"]),
            supported_readable_tissue_withheld=dict(
                cols=all_pooled["supported_withheld_cols"],
                of_human_positive_cols=all_pooled["human_positive_cols"],
                fraction=all_pooled["supported_withheld_frac"],
                shadow_only_cols=all_pooled["supported_withheld_shadow_only_cols"]),
            retained_tissue_error=dict(
                median_abs_um=all_pooled["median_abs_um"],
                worst_bscan_p95_um=all_pooled["worst_p95_abs_um"],
                mean_signed_um=all_pooled["mean_signed_um"],
                max_contiguous_gross_run_cols=all_pooled["max_longest_gross_run"]),
            rejected_bscans=dict(
                n_bscan_surface_rows=len(rej_rows),
                mean_retained_cols_of_512=float(np.mean([p["retained_cols_on_rejected"] for p in rej_rows]))
                if rej_rows else None,
                note="Whole-B-scan human rejection; the existing mask still emits this many columns per surface."),
        ),
        reason_overlap_totals=ov_tot,
        by_split=pooled,
        caveats=[
            "Absence of a manual exclusion is not proof of readability; unknown columns are neither positive nor negative evidence.",
            "Classical shadow / stored_auto scope masks are comparators, not human truth.",
            "human_positive tolerates the shadow bit so 'withheld despite support' is measurable; it excludes unreliable/displaced/not-visible.",
            "Only TS169 and TS325 carry corrected validation evidence; TS336 is rejected-only.",
            "The entropy/uncertainty reason is inactive here (no threshold applied at inference).",
        ],
        experimental=True, validated=False)
    write_json(out / "audit_summary.json", summary)
    print(json.dumps(summary["headline"], indent=2))
    print(json.dumps(ov_tot, indent=2))
    print(f"audit -> {out}")


# --------------------------------------------------------------------------- #
# features  -- per-A-line signal/contrast/continuity + checkpoint entropy
# --------------------------------------------------------------------------- #
FEATURE_NAMES = [
    "band_mean", "band_p25", "band_p75", "band_std", "band_grad_p90",
    "band_lowsig_frac", "vit_median", "vit_std", "cnr", "col_energy_z",
    "neigh_corr", "band_dynrange", "entropy_min", "entropy_mean", "entropy_max",
    "entropy_std",
]


def _column_features(image, band_lo, band_hi):
    """image: canonical (vitreous-low) native-depth [D, W], float. Band in canon px."""
    D, W = image.shape
    band_lo = max(0, int(band_lo)); band_hi = min(D, int(band_hi))
    band = image[band_lo:band_hi]                       # [Hb, W]
    vit = image[:max(1, band_lo - 4)]                   # vitreous slab above the band
    q25, q75 = np.percentile(band, [25, 75], axis=0)
    bmean = band.mean(0); bstd = band.std(0)
    g = np.abs(np.diff(band, axis=0))
    grad_p90 = np.percentile(g, 90, axis=0) if g.shape[0] else np.zeros(W)
    lowsig = (band < (np.median(vit) + 2 * (np.median(np.abs(vit - np.median(vit))) + 1e-6))).mean(0)
    vmed = np.full(W, float(np.median(vit))); vstd = np.full(W, float(vit.std()) + 1e-6)
    cnr = (q75 - vmed) / vstd
    energy = band.clip(0).sum(0)
    med, mad = np.median(energy), np.median(np.abs(energy - np.median(energy))) + 1e-6
    col_energy_z = (energy - med) / (1.4826 * mad)
    bn = (band - bmean) / (bstd + 1e-6)
    nc = np.full(W, np.nan)
    nc[1:-1] = 0.5 * ((bn[:, 1:-1] * bn[:, :-2]).mean(0) + (bn[:, 1:-1] * bn[:, 2:]).mean(0))
    nc[0], nc[-1] = nc[1], nc[-2]
    dyn = q75 - q25
    return np.stack([bmean, q25, q75, bstd, grad_p90, lowsig, vmed, vstd, cnr,
                     col_energy_z, nc, dyn], 1)                 # [W, 12]


def cmd_features(args):
    out = output_dir(args.out / "features")
    evaldirs = {"train": Path(args.eval_train), "validation": Path(args.eval_val)}
    splits = {"train": FrozenSplit(args.data, "train"), "validation": FrozenSplit(args.data, "validation")}
    feats, ent, ret, hp, hn, ae, val = [], [], [], [], [], [], []
    key_idx, animal, split_col, bscan_col = [], [], [], []
    keys = []
    for sname, so in splits.items():
        allow = TRAIN_ANIMALS if sname == "train" else VAL_ANIMALS
        recs = [r for r in so.records if r["animal"] in allow and r["key"] in so.cache["entries"]]
        m = so.manifest
        for r in recs:
            ev = evaldirs[sname] / f"{r['key']}.npz"
            if not ev.exists():
                continue
            entry = so.cache_entry(r["key"])
            cache = load_npz(entry["file"]["path"])
            tgt = load_npz(r["targets"])
            pred = load_npz(ev)
            x = cache["x"]                                  # [1, D, W]
            offset = int(entry["label_offset"])
            band = m["sources"][r["scan_id"]]["label_band"]
            bh = band[1] - band[0]
            rows = pred["rows"].astype(float)              # label coords, matches targets
            e = pred["entropy"].astype(float)             # [8, W]
            cf = _column_features(x[0], offset, offset + bh)          # [W, 12]
            colfeat = np.concatenate(
                [cf, np.stack([e.min(0), e.mean(0), e.max(0), e.std(0)], 1)], 1)  # [W,16]
            t_bits = tgt["reason_bits"].astype(np.uint16)
            pos, neg = _supervision_categories(t_bits)
            truth = tgt["rows_label"].astype(float)
            err = (rows - truth) * r["px_um"]
            W = x.shape[2]
            feats.append(colfeat); ent.append(e.T)
            ret.append(pred["retained"].astype(bool).T)
            hp.append(pos.T); hn.append(neg[0])   # manual mark is column-level (identical across surfaces)
            ae.append(np.abs(err).T); val.append(tgt["valid"].astype(bool).T)
            keys.append(r["key"])
            key_idx += [len(keys) - 1] * W
            animal += [r["animal"]] * W
            split_col += [sname] * W
            bscan_col += [r["bscan"]] * W
    np.savez_compressed(
        out / "columns.npz",
        features=np.concatenate(feats).astype(np.float32),
        feature_names=np.array(FEATURE_NAMES),
        entropy=np.concatenate(ent).astype(np.float32),
        existing_retained=np.concatenate(ret),
        human_positive=np.concatenate(hp),
        human_negative=np.concatenate(hn),
        abs_err_um=np.concatenate(ae).astype(np.float32),
        valid=np.concatenate(val),
        key_idx=np.array(key_idx, np.int32),
        animal=np.array(animal), split=np.array(split_col),
        bscan=np.array(bscan_col, np.int32),
        keys=np.array(keys), surface_names=np.array(SURFACE_NAMES))
    write_json(out / "features_meta.json", dict(
        dataset_id=splits["train"].dataset_id, partition_id=splits["train"].partition_id,
        eval_train=str(args.eval_train), eval_val=str(args.eval_val), preprocessing=PREPROCESS,
        feature_names=FEATURE_NAMES, n_columns=len(key_idx), n_bscans=len(keys),
        train_animals=sorted({a for a, s in zip(animal, split_col) if s == "train"}),
        validation_animals=sorted({a for a, s in zip(animal, split_col) if s == "validation"}),
        note="Per-A-line features + per-surface entropy from the frozen best.pt. "
             "human_positive tolerates the shadow bit; human_negative is the manual "
             "region_excluded mark. Unknown columns are neither.",
        experimental=True, validated=False))
    print(f"features: {len(key_idx)} columns from {len(keys)} B-scans -> {out}")


# --------------------------------------------------------------------------- #
# compare  -- existing mask vs. simple entropy+signal vs. learned pilot
# --------------------------------------------------------------------------- #
def _logreg(X, y, w, l2=1.0, iters=400, lr=0.5):
    """Plain full-batch gradient-descent logistic regression (no sklearn)."""
    n, d = X.shape
    beta = np.zeros(d + 1)
    Xb = np.c_[np.ones(n), X]
    w = w / w.mean()
    for _ in range(iters):
        p = 1.0 / (1.0 + np.exp(-Xb @ beta))
        g = Xb.T @ (w * (p - y)) / n + l2 * np.r_[0, beta[1:]] / n
        beta -= lr * g
    return beta


def _predict_logreg(beta, X):
    return 1.0 / (1.0 + np.exp(-(np.c_[np.ones(len(X)), X] @ beta)))


def _runs_in_groups(fail, group):
    """longest contiguous True run of `fail`, not crossing a change in `group`."""
    best = cur = 0
    for i in range(len(fail)):
        if fail[i] and (i == 0 or group[i] == group[i - 1]):
            cur += 1
        elif fail[i]:
            cur = 1
        else:
            cur = 0
        best = max(best, cur)
    return best


def _method_metrics(reject_col, D, thr_desc):
    """reject_col: bool[N] per-A-line rejection. Layered on existing per-surface mask."""
    ret = D["existing_retained"] & ~reject_col[:, None]        # [N,8]
    valid = D["valid"]; hn = D["human_negative"]; ae = D["abs_err_um"]
    readable = valid.all(1)                                     # unambiguous readable columns
    # supported coverage: among valid (surface,col), fraction still measured
    cov = float((valid & ret).sum() / valid.sum())
    cov_readable = float((~reject_col[readable]).mean()) if readable.any() else None
    # leakage: among manually-unreadable columns, mean fraction of surfaces still measured
    leak = float(ret[hn].mean()) if hn.any() else None
    scored = valid & ret & np.isfinite(ae)
    a = ae[scored]
    fail = valid & ret & (ae > GROSS_UM)
    # contiguous gross run over (key,surface) order
    grp = D["key_idx"]
    longest = 0
    for k in range(8):
        longest = max(longest, _runs_in_groups(fail[:, k], grp))
    return dict(threshold=thr_desc, supported_coverage=cov, readable_col_coverage=cov_readable,
               unreadable_leakage=leak,
               retained_median_abs_um=float(np.median(a)) if a.size else None,
               retained_p95_abs_um=float(np.quantile(a, .95)) if a.size else None,
               retained_gross_frac=float((a > GROSS_UM).mean()) if a.size else None,
               retained_max_contiguous_gross_cols=int(longest),
               n_scored=int(scored.sum()))


def cmd_compare(args):
    out = output_dir(args.out / "compare")
    features = args.features or args.out / "features" / "columns.npz"
    D = load_npz(features)
    names = list(D["feature_names"].astype(str))
    fi = {n: i for i, n in enumerate(names)}
    split = D["split"].astype(str)
    tr = split == "train"; va = split == "validation"
    F = D["features"].astype(float)
    F = np.where(np.isfinite(F), F, 0.0)
    mu, sd = F[tr].mean(0), F[tr].std(0) + 1e-9
    Z = (F - mu) / sd

    readable = D["valid"].all(1)
    hn = D["human_negative"].astype(bool)
    label_known = readable | hn
    y = hn.astype(float)

    # ---- Method B: simple entropy + signal/contrast, standardized on train ---
    score_b = (Z[:, fi["entropy_mean"]] + Z[:, fi["entropy_max"]]
               - Z[:, fi["cnr"]] + Z[:, fi["band_lowsig_frac"]])
    # ---- Method C: learned logistic regression on all features (train only) --
    m = tr & label_known
    w = np.where(y[m] == 1, 1.0 / max(1, y[m].sum()), 1.0 / max(1, (1 - y[m]).sum()))
    beta = _logreg(Z[m], y[m], w, l2=2.0)
    score_c = _predict_logreg(beta, Z)
    coef = dict(zip(["bias"] + names, beta.round(4).tolist()))

    def sub(mask):
        return {k: (D[k][mask] if D[k].ndim == 1 else D[k][mask]) for k in
                ("existing_retained", "valid", "human_negative", "abs_err_um", "key_idx")}

    Dva = sub(va)
    Dtr = sub(tr)

    # threshold chosen on TRAIN to hit a target readable-column coverage,
    # then applied unchanged to VALIDATION (honest cross-animal number).
    targets = [1.00, 0.99, 0.98, 0.96, 0.94, 0.92, 0.90, 0.85, 0.80]
    curves = {"existing": [], "simple_entropy_signal": [], "learned_logreg": []}
    rows = []
    for scr_name, scr in [("simple_entropy_signal", score_b), ("learned_logreg", score_c)]:
        s_tr, s_va = scr[tr], scr[va]
        rd_tr = readable[tr]
        for t in targets:
            thr = np.quantile(s_tr[rd_tr], t) if rd_tr.any() else np.inf
            rej_tr = s_tr > thr
            rej_va = s_va > thr
            mtr = _method_metrics(rej_tr, Dtr, f"train q{t:.2f}={thr:.3f}")
            mva = _method_metrics(rej_va, Dva, f"applied thr={thr:.3f} (train q{t:.2f})")
            curves[scr_name].append(dict(target=t, **{f"val_{k}": v for k, v in mva.items()},
                                         **{f"train_{k}": v for k, v in mtr.items()}))
            rows.append(dict(method=scr_name, split="validation", target_coverage=t, **mva))
            rows.append(dict(method=scr_name, split="train", target_coverage=t, **mtr))
    base_va = _method_metrics(np.zeros(va.sum(), bool), Dva, "none (existing mask only)")
    base_tr = _method_metrics(np.zeros(tr.sum(), bool), Dtr, "none (existing mask only)")
    curves["existing"] = [dict(target=1.0, **{f"val_{k}": v for k, v in base_va.items()},
                               **{f"train_{k}": v for k, v in base_tr.items()})]
    rows.append(dict(method="existing", split="validation", target_coverage=1.0, **base_va))
    rows.append(dict(method="existing", split="train", target_coverage=1.0, **base_tr))
    write_csv(out / "coverage_error_curves.csv", rows)

    # ---- matched-coverage table: for each method, val metrics at the train
    #      threshold whose *validation* readable coverage is closest to each level
    matched = []
    for level in [0.98, 0.95, 0.90, 0.85]:
        entry = dict(matched_supported_coverage_level=level)
        entry["existing_val"] = base_va
        for scr_name in ("simple_entropy_signal", "learned_logreg"):
            cand = curves[scr_name]
            best = min(cand, key=lambda c: abs((c["val_readable_col_coverage"] or 0) - level))
            entry[scr_name + "_val"] = {k[4:]: v for k, v in best.items() if k.startswith("val_")}
        matched.append(entry)
    write_json(out / "matched_coverage.json", matched)

    # ---- whole-B-scan rejection (separate question) -------------------------
    key_idx = D["key_idx"]; keys = D["keys"].astype(str)
    verdict_by_key = _verdict_lookup(args.data)
    bscan_rows = []
    for scr_name, scr in [("simple_entropy_signal", score_b), ("learned_logreg", score_c),
                          ("entropy_max_only", Z[:, fi["entropy_max"]]),
                          ("cnr_deficit_only", -Z[:, fi["cnr"]])]:
        for sp, mask in [("train", tr), ("validation", va)]:
            ks = np.unique(key_idx[mask])
            bs_score = np.array([scr[mask][key_idx[mask] == k].mean() for k in ks])
            rej = np.array([verdict_by_key[keys[k]] == "rejected" for k in ks])
            bscan_rows.append(dict(method=scr_name, split=sp, n_bscans=len(ks),
                                   n_rejected=int(rej.sum()),
                                   auroc_score_predicts_rejected=_auroc(bs_score, rej)))
    write_csv(out / "whole_bscan_rejection.csv", bscan_rows)

    _plot_curves(out / "coverage_error.png", rows, base_va)

    write_json(out / "compare_meta.json", dict(
        dataset_id=json.loads((Path(args.data) / "manifest.json").read_text())["dataset_id"],
        features=str(features), gross_um=GROSS_UM,
        readable_label="valid on all 8 surfaces (drawn, visible, in-scope, unshadowed)",
        unreadable_label="manual region_excluded column",
        method_A="existing reason-coded retained mask (scope/shadow/crossing/missing), no readability layer",
        method_B="standardized entropy_mean+entropy_max - cnr + band_lowsig_frac; threshold by train readable-coverage quantile",
        method_C=f"L2 logistic regression on 16 features, class-balanced, trained on {int(m.sum())} labelled train columns",
        learned_coefficients=coef,
        thresholds="selected on TRAIN readable columns, applied unchanged to VALIDATION",
        disclosure="Only TS169 and TS325 carry corrected validation evidence (2 animals). "
                   "This cannot establish independent calibration; treat as exploratory.",
        experimental=True, validated=False))
    print(json.dumps(matched, indent=2, default=str)[:3000])
    print(json.dumps(bscan_rows, indent=2))
    print(f"compare -> {out}")


def _plot_curves(path, rows, base):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    va = [r for r in rows if r["split"] == "validation" and r["method"] != "existing"]
    fig, ax = plt.subplots(1, 3, figsize=(14, 4.4), constrained_layout=True)
    for method, col in [("simple_entropy_signal", "#1f77b4"), ("learned_logreg", "#d62728")]:
        pts = sorted((r for r in va if r["method"] == method), key=lambda r: r["readable_col_coverage"] or 0)
        cov = [r["readable_col_coverage"] for r in pts]
        ax[0].plot(cov, [r["unreadable_leakage"] for r in pts], "o-", color=col, label=method)
        ax[1].plot(cov, [r["retained_p95_abs_um"] for r in pts], "o-", color=col, label=method)
        ax[2].plot(cov, [r["retained_max_contiguous_gross_cols"] for r in pts], "o-", color=col, label=method)
    for i, key, ttl in [(0, "unreadable_leakage", "leakage into manual-unreadable tissue"),
                        (1, "retained_p95_abs_um", "retained p95 abs error (um)"),
                        (2, "retained_max_contiguous_gross_cols", "worst contiguous gross run (cols)")]:
        ax[i].axhline(base[key], ls="--", color="k", lw=1, label="existing mask")
        ax[i].set_xlabel("readable-column coverage (validation)")
        ax[i].set_title(ttl, fontsize=9)
        ax[i].invert_xaxis()
        ax[i].legend(fontsize=7)
    fig.suptitle("Readability withholding on 2 validation animals (TS169, TS325) - EXPERIMENTAL, not calibrated", fontsize=9)
    fig.savefig(path, dpi=130)
    plt.close(fig)


def _verdict_lookup(data):
    m = json.loads((Path(data) / "manifest.json").read_text())
    return {r["key"]: r["verdict"] for r in m["records"]}


def _auroc(score, positive):
    score = np.asarray(score, float); positive = np.asarray(positive, bool)
    n1, n0 = int(positive.sum()), int((~positive).sum())
    if not n1 or not n0:
        return None
    order = np.argsort(score, kind="mergesort")
    ranks = np.empty(len(score)); ranks[order] = np.arange(1, len(score) + 1)
    return float((ranks[positive].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


# --------------------------------------------------------------------------- #
def build_parser():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("display", help="corrected review overlays (measurement view with gaps)")
    d.add_argument("--data", type=Path, default=DEFAULT)
    d.add_argument("--split", choices=["train", "validation", "trainval"], default="validation")
    d.add_argument("--eval", required=True, help="a stage_a.evaluate output directory")
    d.add_argument("--keys", nargs="*", help="restrict to these decision keys")
    d.add_argument("--raw", action="store_true", help="also write *_raw_diagnostic.png")
    d.add_argument("--include-ineligible", action="store_true")
    d.set_defaults(func=cmd_display)

    a = sub.add_parser("audit", help="existing withholding vs. human evidence")
    a.add_argument("--data", type=Path, default=DEFAULT)
    a.add_argument("--eval-train", required=True, help="stage_a.evaluate --split train --predictor model dir")
    a.add_argument("--eval-val", required=True, help="stage_a.evaluate --split validation --predictor model dir")
    a.add_argument("--gross-um", type=float, default=GROSS_UM)
    a.set_defaults(func=cmd_audit)

    f = sub.add_parser("features", help="per-A-line feature + readability-label table")
    f.add_argument("--data", type=Path, default=DEFAULT)
    f.add_argument("--eval-train", required=True)
    f.add_argument("--eval-val", required=True)
    f.set_defaults(func=cmd_features)

    c = sub.add_parser("compare", help="existing mask vs simple candidate vs learned pilot")
    c.add_argument("--data", type=Path, default=DEFAULT)
    c.add_argument("--features", type=Path)
    c.add_argument("--seed", type=int, default=20260908)
    c.set_defaults(func=cmd_compare)
    for command in (d, a, f, c):
        command.add_argument("--out", type=Path, default=V3, help="output root (features/compare/review/audit go below it)")
    return p


if __name__ == "__main__":
    a = build_parser().parse_args()
    a.func(a)
