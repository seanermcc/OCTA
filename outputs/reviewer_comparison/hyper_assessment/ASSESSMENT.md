# Hyperreflective-dot annotation agreement

Assessment of the September 29, 2026 comparison snapshot. This is agreement
between saved human brush masks, not detection accuracy or a biological dot count.
The 78 source journal/provider hashes still match the snapshot. Source annotations
were not changed. Native coordinates are compared without registration or dilation.

## Overall assessment

The reviewers often identify the same clusters, but their exact painted masks
are not interchangeable. Differences include footprint size, which isolated
spots are included, and whether broad bright patches near the lower retinal band
are included. There is also a substantial difference in how Hyper_Ref paint relates
to the separately marked CNV spans. This limits interpretation of unmatched pixels
as missed detections.

Nine exact B-scans from three animals have both reviews, all with confirmed
lesion reviews. Eight have paint from both people; one has neither. The empty pair
has undefined Dice and is not counted as perfect agreement. The other saved slices
are not matched: lead has paint on 17/29 saved slices and Shichu on 21/27, but these
unequal selections cannot establish a difference in dot prevalence or sensitivity.

| Measure | All saved paint, 8 nonempty pairs | Shared usable CNV spans, 7 nonempty pairs |
|---|---:|---:|
| Lead painted pixels | 10,190 | 6,338 |
| Shichu painted pixels | 11,105 | 7,185 |
| Exact overlap pixels | 5,492 | 3,971 |
| Dice | 0.516 | 0.587 |
| Intersection over union | 0.348 | 0.416 |
| Fraction of lead paint also painted by Shichu | 53.9% | 62.7% |
| Fraction of Shichu paint also painted by lead | 49.5% | 55.3% |

Dice = twice the overlap divided by the sum of painted areas; 1 means identical
paint and 0 means no overlap. Intersection over union divides overlap by all
pixels painted by either reviewer. The mean of the eight individual nonempty
B-scan Dice values is 0.533; the pooled value above weights painted pixels.
No background-dominated pixel accuracy is reported.

Shichu's total painted area is 9.0% larger, and is larger in 6/8 nonempty pairs.
This does not mean she found 9% more dots. Brush width, merged patches, and dot
selection all affect painted area.

As a separate proximity diagnostic, 67.8% of lead paint is within approximately
5 microns of Shichu paint, and 75.5% of Shichu paint is within that distance of lead
paint. These use nearest-painted-pixel distance, with 1.12 microns/depth pixel and
an approximate lateral scale of 1460/512 microns/pixel. They are not dot-matching
rates. The remaining separation supports differences in selected structures,
beyond small footprint or placement differences.

## Per-slice results

All day/session labels below identify the stored scans; B-scan indices are zero-based.

| Scan | B-scan | Lead pixels | Shichu pixels | Raw Dice | Shared usable CNV Dice |
|---|---:|---:|---:|---:|---:|
| TS241 D42 s03 | 244 | 527 | 1,074 | 0.611 | 0.676 |
| TS241 D42 s05 | 219 | 598 | 641 | 0.644 | 0.633 |
| TS247 D21 s03 | 325 | 1,464 | 699 | 0.404 | 0.484 |
| TS247 D21 s05 | 346 | 1,059 | 1,224 | 0.552 | 0.565 |
| TS247 D35 s01 | 282 | 2,299 | 1,386 | 0.346 | 0.424 |
| TS250 D24 s02 | 387 | 1,105 | 1,348 | 0.589 | 0.647 |
| TS250 D24 s03 | 45 | 2,076 | 2,993 | 0.543 | 0.650 |
| TS250 D27 s01 | 380 | 1,062 | 1,740 | 0.572 | Not assessable: no shared CNV span |
| TS250 D27 s03 | 440 | 0 | 0 | Undefined: both empty | Not assessable |

## Qualitative inspection

All nine matched B-scans were inspected in synchronized native-grid galleries.
Lead-only pixels are cyan, Shichu-only pixels pink, and exact overlap yellow in
the right-hand overlay panels.

- **TS241 D42 B244:** most of lead's paint is contained within Shichu's paint
  (92.8%). Shichu draws larger footprints around the shared cluster and additional
  deeper marks. This is partly a footprint/extent difference, not wholesale
  disagreement about cluster location.
- **TS241 D42 B219:** the highest exact overlap (Dice 0.644). Several small spots
  coincide; Shichu also includes deeper isolated marks. Similar total area does
  not imply identical selections.
- **TS247 D21 B325 and D35 B282:** the strongest discrepancies. Lead includes
  broader bright patches close to the lower bright retinal band that Shichu
  largely omits. In B282, Shichu also marks an upper cluster extending above
  lead's selection. These are differences in which structures were included,
  not simply a uniform lateral/depth shift.
- **TS247 D21 B346:** both select upper and middle clusters, with different
  footprints; lead additionally marks a lower curved patch near the bright band.
- **TS250 D24 B387:** many central spots coincide, but Shichu includes more
  peripheral and deeper marks, and the individual painted outlines differ.
- **TS250 D24 B45, the example previously displayed:** both mark the central
  cluster. Shichu paints it more continuously and broadly; lead adds isolated
  marks farther to the right that Shichu does not mark. Shichu's total painted
  area is 44.2% larger here, despite only 9.0% larger area across all pairs.
- **TS250 D27 B380:** clusters are broadly co-located, with larger Shichu
  footprints. Lead has no saved CNV region on this slice, so a comparison
  restricted to shared CNV spans cannot evaluate these dots.
- **TS250 D27 B440:** neither reviewer painted dots. This records agreement in
  saved painting behavior; it does not independently establish biological absence.

## CNV extent and uncertainty

Lead has 3,852 painted pixels (37.8%) outside lead's own CNV spans, compared with
80 (0.7%) for Shichu. Lead's B380 has no CNV region marked, accounting for 1,062
of those pixels. The remaining 2,790 are outside lead's spans on the other seven
nonempty slices. This is a scope/annotation consistency issue to discuss, not
proof that either reviewer is wrong about those structures.

The shared-span sensitivity analysis requires both confirmed lesion reviews,
the intersection of their CNV spans, and columns that neither excluded and the
provider did not mark shadowed. It removes 37.8% of lead paint and 35.3% of Shichu
paint, so its higher Dice is conditional on that smaller region. It must not
replace the full comparison silently. Hyper_Ref's existing target rule permits
positive paint outside a CNV span, but does not treat all unpainted pixels outside
that span as reviewed negatives. Accordingly, the all-paint table describes
mask agreement and does not label unmatched pixels false positives or misses.

Hyper_Ref stores a binary brush mask and shared lesion confirmation, without the
per-dot unreliable/not-traceable states available for CNV edges. Confirmation
does not prove correctness or remove ambiguity in faint structures.

## Review priorities

First reconcile TS247 D35 B282, then TS247 D21 B325 and TS250 D24 B45. Agree on
whether the target is only discrete bright dots separate from the RPE, whether
broader/confluent bright patches belong, how tightly to trace each spot, and how
to handle dots outside the marked CNV extent. The stored tentative definition
describes dots within the CNV lesion, above and separate from the RPE. The images
here do not adjudicate which disputed marks satisfy that definition.

Until these conventions are reconciled, the labels support descriptive comparison
but should not be treated as interchangeable measurements of dot burden. Nine
slices from three animals are insufficient for a general reviewer-reliability claim.

## Evidence

- [Gallery 1: TS241 and TS247 B325](gallery_1.png)
- [Gallery 2: TS247 B346/B282 and TS250 B387](gallery_2.png)
- [Gallery 3: TS250 B45/B380/B440](gallery_3.png)
- [Exact numeric results and full scan identifiers](assessment.json)
- Reproduce with activated `octa`: `python code\reviewer_compare\assess_hyper.py`.
