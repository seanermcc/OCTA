#!/usr/bin/env python3
"""
Preparing B-scans for human review, and refitting priors from what the human
drew.

    conda activate octa

    python review_surfaces.py pack --npz ../outputs/segment_v2/<scan>.npz --n 12
    python review_surfaces.py pack --all ../outputs/segment_v2 --n 6
    python review_surfaces.py pack --sample ../outputs/samples/slab_TS165_WT.npz
    python label_gui.py ../outputs/review          # correct them (Qt window)
    python review_surfaces.py refit --labels ../outputs/labels

Correction itself lives in `label_gui.py`. There used to be a second editor in
this file built on matplotlib; it is gone rather than kept as a fallback,
because two editors writing labels means two label formats to keep in step, and
the one that gets used less is the one that silently drifts.

Why a "pack" step exists
------------------------
This dataset's HDF5 chunks span the whole B-scan axis, so pulling out a single
B-scan decompresses the same chunks as reading the entire 4 GiB volume -- a
per-B-scan read loop measured ~1,500x slower than one bulk read (78 min vs
13 s). An interactive tool that fetched B-scans on demand would be unusable.
So `pack` does one bulk read, keeps the handful of B-scans a human will
actually look at, and writes them as a ~3 MB file that opens instantly and can
be copied to another machine.

Which B-scans get packed
------------------------
Not a uniform sample. The point of human effort is to fix what the automatic
pipeline gets wrong, so B-scans are ranked by how badly they need review:

  * surfaces the image did not support (low `local_confidence`)
  * layer thicknesses outside the published plausible range
  * high shadow fraction
  * surfaces that disagree with their own neighbours along the slow axis

and the worst `--n` are taken, plus a few median-ranked ones as controls. A
correction set drawn only from failures would teach a refit that the retina
looks like its own worst cases, so the controls are not optional.

The four components are combined by rank within the scan rather than by adding
the raw numbers. Added raw, they barely discriminated: on the first pack built
this way the ten selected B-scans scored 0.63 to 0.83, with the controls at
0.63 and the worst at 0.83 -- a spread far too narrow to claim the "worst" ones
were meaningfully worse. Each component saturates in its own range and they are
not on a common scale, so the sum was dominated by whichever happened to have
the widest spread. Ranking first puts them on the only scale they share.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from octa import labels as L                                       # noqa: E402
from octa import reference as ref                                  # noqa: E402
from octa.segment import (SURFACE_NAMES, LAYER_DEFS,               # noqa: E402
                          CASCADE_VERSION, RETIRED_SURFACES,
                          detect_orientation, prepare_bscan,
                          RELATIVE_PRIORS, INNER_SURFACES)
from octa.volume import segment_volume, thickness_maps             # noqa: E402

PX_UM = 1.12
DEFAULT_REVIEW_DIR = Path("../outputs/review")
DEFAULT_LABEL_DIR = Path("../outputs/labels")
CONF_FLOOR = 0.5


# ==========================================================================
# ranking
# ==========================================================================

def _rank01(x: np.ndarray) -> np.ndarray:
    """Rank-normalise to [0, 1]; all-equal input maps to 0.5 throughout."""
    x = np.asarray(x, dtype=float)
    if x.size <= 1 or np.allclose(x, x.flat[0]):
        return np.full(x.shape, 0.5)
    order = np.argsort(np.argsort(x))
    return order / (x.size - 1.0)


def _slow_axis_roughness(surfaces: np.ndarray, k: int = 5) -> np.ndarray:
    """
    How far each B-scan's surfaces sit from their own slow-axis neighbours.

    The retina changes smoothly from one B-scan to the next, so a surface that
    departs from its neighbours is either a real localised feature -- which a
    CNV lesion is -- or a segmentation failure. Either way it is worth a human
    looking at, which is all this score claims.

    Deliberately a *median* over neighbours and a median over A-lines: a mean
    would let one wild A-line speak for the whole B-scan.
    """
    n_b = surfaces.shape[0]
    if n_b < 3:
        return np.zeros(n_b)
    half = max(1, k // 2)
    out = np.zeros(n_b)
    for b in range(n_b):
        lo, hi = max(0, b - half), min(n_b, b + half + 1)
        idx = [j for j in range(lo, hi) if j != b]
        if not idx:
            continue
        neigh = np.median(surfaces[idx], axis=0)
        with np.errstate(invalid="ignore"):
            d = np.abs(surfaces[b] - neigh)
        out[b] = float(np.nanmedian(d))
    return out


def _spread_pick(score: np.ndarray, n: int, min_sep: int,
                 exclude=None) -> np.ndarray:
    """
    Take the `n` highest-scoring B-scans, but never two within `min_sep` of
    each other.

    Without this the selection collapses onto a single bad region: the score is
    built from quantities that vary smoothly along the slow axis, so a scan
    with one bad patch produces a contiguous run of near-identical worst
    B-scans. Labelling eight neighbouring B-scans costs eight times as much as
    labelling one and teaches almost the same thing, which is the opposite of
    what a correction set is for.

    Greedy, not optimal, and it does not need to be -- the goal is coverage,
    not a maximum.
    """
    n_b = score.size
    taken: list[int] = []
    blocked = np.zeros(n_b, dtype=bool)
    if exclude is not None:
        for j in np.atleast_1d(exclude):
            blocked[max(0, j - min_sep):min(n_b, j + min_sep + 1)] = True
    for j in np.argsort(-score):
        if len(taken) >= n:
            break
        if blocked[j]:
            continue
        taken.append(int(j))
        blocked[max(0, j - min_sep):min(n_b, j + min_sep + 1)] = True
    # If min_sep was too aggressive for the volume, fall back to filling the
    # remainder by score rather than silently returning fewer B-scans.
    if len(taken) < n:
        for j in np.argsort(-score):
            if len(taken) >= n:
                break
            if int(j) not in taken and (exclude is None
                                        or int(j) not in set(np.atleast_1d(exclude).tolist())):
                taken.append(int(j))
    return np.array(sorted(taken), dtype=int)


def _suspect_score(surfaces, conf, shadow, px_um):
    """
    Per-B-scan "needs a human" score, and the components behind it.

    Four independent things can be wrong with a B-scan and they do not
    substitute for one another, so each is measured separately and they are
    combined by rank. Higher = worse.
    """
    n_b = surfaces.shape[0]
    tm = thickness_maps(surfaces, shadow, px_um=px_um, mask_shadow=True)

    unsupported = np.mean(conf < CONF_FLOOR, axis=(1, 2))          # [n_b]
    shadow_frac = shadow.mean(axis=1)
    roughness = _slow_axis_roughness(surfaces)

    implausible = np.zeros(n_b)
    n_checked = 0
    for name, _, _ in LAYER_DEFS:
        if name not in tm or name not in ref.TREE_SHREW:
            continue
        lo, hi = ref.plausible_range(name)
        t = tm[name]
        with np.errstate(invalid="ignore"):
            bad = (t < lo) | (t > hi)
        implausible += np.nanmean(np.where(np.isfinite(t), bad, np.nan), axis=1)
        n_checked += 1
    if n_checked:
        implausible /= n_checked

    parts = {"unsupported": unsupported, "implausible": implausible,
             "shadow_frac": shadow_frac, "roughness": roughness}
    score = np.mean([_rank01(v) for v in parts.values()], axis=0)
    return score, parts


# ==========================================================================
# pack
# ==========================================================================

def _align_surfaces(names, surfaces, conf):
    """
    Reduce a stored result to the surfaces the current cascade defines.

    A file carrying extra, retired surfaces is a superset and can be used on
    the shared ones. A file *missing* a current surface predates the
    reference-based priors, and its inner-retina labels are wrong by one
    landmark all the way down -- there is nothing to salvage from it.
    """
    names = [str(n) for n in names]
    if names == list(SURFACE_NAMES):
        return names, surfaces, conf, []
    missing = [n for n in SURFACE_NAMES if n not in names]
    if missing:
        raise ValueError(
            f"missing {', '.join(missing)}, which the current cascade defines; "
            f"this output predates the reference-based priors. "
            f"Re-run: python batch_segment.py --overwrite")
    extra = [n for n in names if n not in SURFACE_NAMES]
    keep = [names.index(n) for n in SURFACE_NAMES]
    return list(SURFACE_NAMES), surfaces[:, keep, :], conf[:, keep, :], extra


def _pack_one(src_kind: str, path: Path, args, out_dir: Path) -> int:
    if src_kind == "sample":
        d = np.load(path)
        slab = d["slab"][::args.stride]
        vhi = detect_orientation(d["profile"])
        scan_id = path.stem
        print(f"segmenting {slab.shape[0]} B-scans from {path.name} ...")
        surfaces, conf, shadow, _notes = segment_volume(
            slab, vhi, bscan_avg=3, refine=True, smooth_bscans=5,
            px_um=PX_UM, attract=0.05, progress=True)
        imgs = np.stack([prepare_bscan(b, vhi) for b in slab])
        bscan_index = np.arange(0, d["slab"].shape[0], args.stride)
        extra = []
    else:
        # A batch output carries surfaces but not pixels, so the volume has to
        # be re-read. One bulk read, as above.
        from octa.volio import ProcessedVolume, find_retina_band
        seg = np.load(path, allow_pickle=False)
        names = [str(x) for x in seg["surface_names"]]
        surfaces = seg["surfaces"].astype(np.float32)
        shadow = seg["shadow"]
        conf = (seg["confidence"].astype(np.float32) if "confidence" in seg.files
                else np.full(surfaces.shape, np.nan, dtype=np.float32))
        names, surfaces, conf, extra = _align_surfaces(names, surfaces, conf)
        scan_id = str(seg["scan_id"][0])
        vpath = Path(str(seg["source"][0]))
        if not vpath.exists():
            print(f"  source volume not found: {vpath}")
            return 1
        print(f"  bulk-reading {vpath.name} (one read -- see module docstring) ...")
        with ProcessedVolume(vpath) as v:
            full = v.read_volume(channel="struct")
            profile = full.mean(axis=(0, 1))
            lo, hi, _ = find_retina_band(profile)
            vhi = detect_orientation(profile)
            band = full[:, :, lo:hi]
        imgs = np.stack([prepare_bscan(b, vhi) for b in band])
        bscan_index = np.arange(imgs.shape[0])

        if getattr(args, "fresh", False):
            # The stored surfaces reflect whatever RELATIVE_PRIORS/cascade
            # version wrote this file, which may predate the running
            # segment.py. Re-segment from the pixels already bulk-read above
            # instead of trusting the stale surfaces -- one extra pass over
            # already-in-memory data, no second volume read. This is the only
            # way to pack a scan against a settings change without first
            # re-running the whole batch on it.
            print(f"  --fresh: re-segmenting with current settings "
                  f"(cascade_version={CASCADE_VERSION}) rather than trusting "
                  f"the stored surfaces ...")
            surfaces, conf, shadow, notes = segment_volume(
                band, vhi, bscan_avg=3, refine=True, smooth_bscans=5,
                px_um=PX_UM, attract=0.05, progress=True)
            if notes:
                print(f"    {len(notes)} note(s) from the cascade, first few:")
                for n in notes[:5]:
                    print(f"      {n}")
        elif np.all(np.isnan(conf)):
            print("  NOTE: this output predates confidence being stored, so "
                  "B-scans are ranked without the support term.")
            conf = np.full(surfaces.shape, CONF_FLOOR, dtype=np.float32)

    if extra:
        unknown = set(extra) - set(RETIRED_SURFACES)
        print(f"  dropping retired surfaces: {', '.join(extra)}"
              + (f"  WARNING: {', '.join(sorted(unknown))} are not known "
                 f"retired surfaces" if unknown else ""))

    score, parts = _suspect_score(surfaces, conf, shadow, PX_UM)
    worst = _spread_pick(score, args.n, args.min_sep)
    # Controls: without them a refit learns the retina from its own failures.
    n_ctrl = max(2, args.n // 4)
    mid = _spread_pick(-np.abs(score - np.median(score)), n_ctrl, args.min_sep,
                       exclude=worst)
    pick = np.unique(np.concatenate([worst, mid]))

    out = out_dir / f"{scan_id}_pack.npz"
    np.savez_compressed(
        out,
        images=imgs[pick].astype(np.float32),
        surfaces=surfaces[pick].astype(np.float32),
        confidence=conf[pick].astype(np.float16),
        shadow=shadow[pick].astype(bool),
        picked=pick.astype(np.int32),
        bscan_index=bscan_index[pick].astype(np.int32),
        is_control=np.isin(pick, mid),
        suspect_score=score[pick].astype(np.float32),
        surface_names=np.array(SURFACE_NAMES),
        cascade_version=np.array([CASCADE_VERSION]),
        scan_id=np.array([scan_id]),
        px_um=np.array([PX_UM], dtype=np.float32),
    )
    print(f"  packed {pick.size} B-scans ({worst.size} worst + "
          f"{pick.size - worst.size} control) -> {out.name} "
          f"({out.stat().st_size / 1024**2:.1f} MB)")
    print(f"    {'bscan':>7s} {'score':>6s} {'unsup':>6s} {'implaus':>8s} "
          f"{'shadow':>7s} {'rough':>6s}  role")
    for i in sorted(pick, key=lambda j: -score[j]):
        role = "control" if i in mid else "suspect"
        print(f"    {bscan_index[i]:7d} {score[i]:6.2f} "
              f"{parts['unsupported'][i]:6.2f} {parts['implausible'][i]:8.2f} "
              f"{parts['shadow_frac'][i]:7.2f} {parts['roughness'][i]:6.2f}  {role}")
    print(f"    score spread over the whole scan: "
          f"{score.min():.2f} to {score.max():.2f}; selected "
          f"{score[pick].min():.2f} to {score[pick].max():.2f}")
    return 0


def cmd_pack(args) -> int:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    jobs: list[tuple[str, Path]] = []
    if args.sample:
        jobs.append(("sample", Path(args.sample)))
    elif args.npz:
        jobs.append(("npz", Path(args.npz)))
    else:
        d = Path(args.all)
        found = sorted(d.glob("*.npz")) if d.is_dir() else []
        if not found:
            print(f"no .npz found in {d}")
            return 1
        jobs = [("npz", f) for f in found]

    rc = 0
    for k, (kind, p) in enumerate(jobs, 1):
        print(f"\n[{k}/{len(jobs)}] {p.name}")
        try:
            rc |= _pack_one(kind, p, args, out_dir)
        except Exception as e:                                    # noqa: BLE001
            print(f"  FAILED: {e}")
            rc = 1
    print(f"\nnext: python label_gui.py {out_dir}")
    return rc


# ==========================================================================
# refit
# ==========================================================================

def cmd_refit(args) -> int:
    recs = L.load_labels(args.labels)
    if not recs:
        print(f"no label files in {args.labels}; run `pack` then `label_gui.py`")
        return 1

    rows, n_rejected, n_control, n_stale, n_accepted_skipped = [], 0, 0, 0, 0
    for r in recs:
        if r["verdict"] == "rejected":
            n_rejected += 1
            continue
        if r["verdict"] != "corrected":
            # "accepted" means nobody drew anything -- surfaces == auto. Only
            # `corrected` files involve a human actually looking closely
            # enough to redraw something. Pooling accepted files in here
            # silently launders the automatic output into evidence for
            # itself, exactly the failure `surface_edited` gating already
            # guards against one level down -- and it is not hypothetical:
            # the first real batch had 14 accepted files at a median 0s
            # review time (see the accepted-time warning below) diluting 10
            # genuine corrections. If those files' surfaces are ever actually
            # verified by a slower second pass, re-run refit afterward; until
            # then they carry no information here.
            n_accepted_skipped += int(r["verdict"] == "accepted")
            continue
        if r["surface_names"] != list(SURFACE_NAMES):
            n_stale += 1
            continue
        n_control += int(bool(r.get("is_control", False)))
        idx = {n: k for k, n in enumerate(r["surface_names"])}
        surf = r["surfaces"]
        ilm, rpe = surf[idx["ILM"]], surf[idx["RPE"]]
        span = rpe - ilm
        # A collapsed span means a bad A-line; a human-marked region means the
        # image itself was judged unusable there, for every surface at once --
        # neither is evidence, whatever value happens to be stored there.
        # (load_label defaults region_excluded to all-False for older labels.)
        good = (span > 40) & (~r["region_excluded"])
        if good.sum() < 20:
            continue
        row = {"file": r["path"].name, "verdict": r["verdict"],
               "edited": {n: bool(r["surface_edited"][idx[n]])
                          for n in r["surface_names"]},
               "visible": {n: bool(r["surface_visible"][idx[n]])
                           for n in r["surface_names"]}}
        for n in INNER_SURFACES:
            # Same principle, one level down: within a file where SOME
            # surface was corrected, a DIFFERENT surface that nobody touched
            # is still just the automatic output. Pool a surface's position
            # only from rows that actually edited that surface, not every row
            # that happened to have a "corrected" verdict.
            if n in idx and row["edited"][n]:
                row[n] = float(np.median(((surf[idx[n]] - ilm) / span)[good]))
        rows.append(row)

    if not rows:
        print(f"{len(recs)} label file(s) found but none usable "
              f"({n_rejected} rejected, {n_accepted_skipped} accepted (not "
              f"evidence -- nothing was drawn), {n_stale} from another "
              f"cascade version)")
        return 1

    print(f"{len(rows)} usable 'corrected' label file(s), {n_control} of "
          f"them control B-scans\n"
          f"not used as evidence: {n_rejected} rejected, "
          f"{n_accepted_skipped} accepted (surfaces == auto, nothing drawn), "
          f"{n_stale} from another cascade version\n")
    print(f"  {'surface':10s} {'published':>10s} {'human':>10s} {'delta':>8s} "
          f"{'n edited':>9s} {'n unseen':>9s}  note")
    print("  " + "-" * 78)

    refit = {}
    for n in INNER_SURFACES:
        vals = np.array([r[n] for r in rows if n in r], dtype=float)
        if vals.size == 0:
            continue
        n_ed = sum(1 for r in rows if r["edited"].get(n))
        n_unseen = sum(1 for r in rows if not r["visible"].get(n, True))
        pub = RELATIVE_PRIORS.get(n, float("nan"))
        med = float(np.median(vals))
        refit[n] = med
        # A surface nobody corrected carries no human information: its "human"
        # value is the automatic output fed back, and refitting on it would
        # launder the prior into evidence for itself.
        note = "" if n_ed else "NOT CORRECTED - value is the automatic one"
        if n_ed and n_ed < args.min_edits:
            note = f"only {n_ed} correction(s), below --min-edits"
        if n_unseen and n_unseen >= 0.5 * len(rows):
            note = (note + "; " if note else "") + \
                   f"invisible in {n_unseen}/{len(rows)} B-scans"
        print(f"  {n:10s} {pub:10.3f} {med:10.3f} {med - pub:+8.3f} "
              f"{n_ed:9d} {n_unseen:9d}  {note}")

    trusted = {n: v for n, v in refit.items()
               if sum(1 for r in rows if r["edited"].get(n)) >= args.min_edits}

    # Cost of the review, which is the number that decides whether a learned
    # model is reachable at all. Measured, not estimated -- but measured
    # *separately* by verdict, and deliberately not blended into one median.
    #
    # A quick accept and a rushed accept produce an identical timer reading:
    # both are "a few seconds, nothing drawn". The only way to tell them apart
    # is whether the surfaces were actually looked at, which the timer cannot
    # know. Blending accepted and corrected times together lets a handful of
    # rushed accepts drag the median down by an order of magnitude and makes
    # the projection for a larger batch look far cheaper than it is -- this
    # happened on the first real run of this tool (median collapsed to ~1s).
    # Reporting them apart at least keeps that failure visible instead of
    # averaging over it.
    def _secs(verdict):
        s = [r["seconds_active"] for r in recs if r["verdict"] == verdict
             and np.isfinite(r["seconds_active"]) and r["seconds_active"] > 0]
        return s

    corrected_s, accepted_s = _secs("corrected"), _secs("accepted")
    print()
    if corrected_s:
        print(f"time on 'corrected' B-scans (actual drawing): "
              f"median {np.median(corrected_s):.0f}s, "
              f"range {min(corrected_s):.0f}-{max(corrected_s):.0f}s, "
              f"n={len(corrected_s)}")
        print(f"  100 B-scans this hard: "
              f"{np.median(corrected_s) * 100 / 3600:.1f} h")
    else:
        print("no 'corrected' B-scans with a usable timer reading yet")
    if accepted_s:
        print(f"time on 'accepted' B-scans (should be a real look, not a "
              f"reflex click): median {np.median(accepted_s):.0f}s, "
              f"n={len(accepted_s)}")
        if np.median(accepted_s) < 5:
            print("  WARNING: median under 5s suggests some of these were "
                  "clicked through, not reviewed.\n"
                  "  refit already excludes 'accepted' files from its "
                  "position estimate for exactly this reason,\n"
                  "  but anything else that treats 'accepted' as verified "
                  "ground truth won't -- worth a\n"
                  "  slower second pass before relying on them elsewhere.")
    n_acc = sum(1 for r in recs if r["verdict"] == "accepted")
    print(f"\nverdicts: {n_acc} accepted, "
          f"{sum(1 for r in recs if r['verdict'] == 'corrected')} corrected, "
          f"{n_rejected} rejected")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "generated": _dt.datetime.now().isoformat(timespec="seconds"),
        "cascade_version": CASCADE_VERSION,
        "n_labels": len(rows), "n_rejected": n_rejected, "n_stale": n_stale,
        "min_edits": args.min_edits,
        "published_priors": RELATIVE_PRIORS,
        "refit_all": refit,
        "refit_trusted": trusted,
        "median_seconds_corrected": (float(np.median(corrected_s))
                                     if corrected_s else None),
        "median_seconds_accepted": (float(np.median(accepted_s))
                                    if accepted_s else None),
        "note": ("refit_trusted contains only surfaces corrected by a human at "
                 "least --min-edits times. Surfaces in refit_all but not in "
                 "refit_trusted are the automatic output echoed back and must "
                 "not be used as priors."),
    }, indent=2), encoding="utf-8")
    print(f"\nwrote {out}")
    print(f"  {len(trusted)}/{len(refit)} surface(s) have enough human "
          f"corrections to be trusted as priors")
    if trusted:
        print("\nTo use these, set RELATIVE_PRIORS in octa/segment.py from "
              "refit_trusted.\nThis is deliberately a manual step: replacing a "
              "published prior with a\nlocally fitted one is a decision worth "
              "making on purpose.")
    return 0


def cmd_edit(args) -> int:
    print("Correction moved to its own Qt application:\n\n"
          f"    python label_gui.py {args.pack}\n\n"
          "It draws freehand, marks unsupported A-lines, records whether each "
          "surface was\nvisible at all, and times the review so the cost of "
          "labelling is measured\nrather than guessed.")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("pack", help="build review packs from segmented scans")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--sample", help="a development sample .npz")
    g.add_argument("--npz", help="one batch output")
    g.add_argument("--all", help="a directory of batch outputs")
    p.add_argument("--n", type=int, default=12, help="worst N B-scans (default 12)")
    p.add_argument("--min-sep", type=int, default=15,
                   help="minimum B-scan separation between picks (default 15), "
                        "so a single bad region cannot fill the whole pack")
    p.add_argument("--stride", type=int, default=4)
    p.add_argument("--out-dir", default=str(DEFAULT_REVIEW_DIR))
    p.add_argument("--fresh", action="store_true",
                   help="(--npz/--all only) re-segment from the volume with "
                        "the CURRENT octa.segment settings instead of "
                        "trusting the file's stored surfaces. Use this after "
                        "a RELATIVE_PRIORS/CASCADE_VERSION change, to pack "
                        "against up-to-date output without first re-running "
                        "the whole batch on that scan.")
    p.set_defaults(func=cmd_pack)

    p = sub.add_parser("edit", help="(moved to label_gui.py)")
    p.add_argument("pack", nargs="?", default=str(DEFAULT_REVIEW_DIR))
    p.set_defaults(func=cmd_edit)

    p = sub.add_parser("refit", help="re-estimate priors from human labels")
    p.add_argument("--labels", default=str(DEFAULT_LABEL_DIR))
    p.add_argument("--out", default="../outputs/priors_refit.json")
    p.add_argument("--min-edits", type=int, default=5,
                   help="corrections needed before a surface's refit is trusted")
    p.set_defaults(func=cmd_refit)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
