# Published tree shrew retinal layer values

Source: Grannonico M, Miller DA, Liu M, Krause MA, Savier E, Erisir A,
Netland PA, Cang J, Zhang HF, Liu X. *Comparative In Vivo Imaging of Retinal
Structures in Tree Shrews, Humans, and Mice.* eNeuro 11(3), March 2024.
DOI: 10.1523/ENEURO.0373-23.2024

The machine-readable version lives in `code/octa/reference.py`, which is the
single source of truth. This file explains where the numbers came from and how
far to trust each one. Only tree shrew values are recorded — the paper also
reports mouse and human, and mixing species here would be an easy and
catastrophic mistake.

Central = 500 µm radius from the ONH. Peripheral = 1,200 µm radius.

## The table

| Layer | Central (µm) | Peripheral (µm) | Where it comes from |
|---|---|---|---|
| TOTAL | 250.7 ± 25 | 229.8 ± 21 | stated in Results text |
| RNFL | 81.7 ± 23 | 62.8 ± 17 | stated in text — **axon bundle height**, see below |
| GCL | 12.5 ± 4.5 | 10.1 ± 3.7 | stated in text |
| IPL | 50.0 ± 5.9 | 45.7 ± 3.4 | stated in text |
| IPL S1 | 19.5 ± 2.1 | 18.3 ± 2.1 | stated in text |
| IPL S2 | 12.4 ± 1.9 | 9.7 ± 1.6 | stated in text |
| IPL S3 | 17.2 ± 2.2 | 17.8 ± 1.5 | stated in text |
| INL | ~34 | ~34 | **read off Figure 3C** — no number in the text |
| ONL | ~14 | ~19 | **read off Figure 3C** — no number in the text |

Not measured by the paper at all, and assumed in `reference.py` from the
residual plus our own outer-retina landmarks: OPL 12, IS 15, OS 12, RPE-BM 19.

## Why the figure-read INL and ONL are trustworthy enough

They pass an arithmetic check they had no reason to pass. Summing the layers
and subtracting from the paper's own independently measured TOTAL:

```
central     81.7 + 12.5 + 50.0 + 34 + 14 = 192.2   ->  250.7 - 192.2 = 58.5 um
peripheral  62.8 + 10.1 + 45.7 + 34 + 19 = 171.6   ->  229.8 - 171.6 = 58.2 um
```

Both residuals — the space left for OPL + IS + OS + RPE-BM — agree to 0.3 µm,
despite being differences of separately measured quantities. The IPL sublayers
independently sum to the stated whole-IPL thickness (49.1 vs 50.0 central,
45.8 vs 45.7 peripheral).

They are still flagged `confirmed=False` in `reference.py`. If a result turns
on the exact INL or ONL value, re-read Figure 3C rather than relying on this.

## Structure, not just numbers

These qualitative statements from the paper are what make the boundaries
findable, and they are why the cost-image polarities in `SURFACE_COST` are what
they are:

- The tree shrew GCL is **"a distinct dark band"** — unlike mouse, where the
  IPL blends with the GCL into a single GCIPL. This is the single most
  important fact for getting the cascade right.
- RGC axon bundles in the tree shrew RNFL are **"vertically elongated, densely
  packed, and stratified"** centrally, becoming "a monolayer of round or
  oval-shaped axon bundles" peripherally. Confocal (Fig 5B) confirms bundles
  wrapped in GFAP processes, and 3–4 soma layers of RGCs in the GCL versus 1–2
  in mouse.
- The IPL consists of **"two bright strata divided by a dark band in the
  middle"** — S1 bright, S2 dark, S3 bright. The paper defines S1 as top IPL
  boundary to the first minimum of the valley, S2 between the two minima of
  the valley, S3 from the second minimum to the bottom IPL boundary.
- The ONL is **"significantly thinner in tree shrews compared with mice and
  humans"**, confirmed ex vivo by DAPI (Fig 6B).

## Axon bundle height is not mean RNFL thickness

The paper's RNFL figure is the height *of the bundles*. Because tree shrew RNFL
is organised into discrete bundles with thinner gaps between them, a per-A-line
RNFL thickness map averages both and lands below the published figure, with
genuinely large lateral variation.

`plausible_range("RNFL")` widens the lower bound by 0.35× for this reason. A
mean RNFL well under 62 µm is expected anatomy. A mean RNFL *above* the
published bundle height is the suspicious direction.

## Measurement conditions differ from ours

Worth remembering before treating a mismatch as our bug:

| | Paper | Us |
|---|---|---|
| System | Halo 100 vis-OCT, 1.3 µm axial | lab OCT-A, 1.12 µm/px |
| Processing | speckle-reduced resampled SR-B-scans | 3-B-scan average in dB |
| IPL sublayers | average of 250 SR-A-lines (~545 µm) | per-A-line |
| Sampling | radial rings at known eccentricity | ~1460 µm field, ONH often outside |
| Animals | n = 3 healthy | 11 animals, WT and laser-CNV, 3 years |

The IPL sublamina row is the one where this matters most: the paper resolves
S1/S2/S3 from heavily averaged speckle-reduced A-lines. Our IPL spans only
~0.6 dB peak-to-valley, against ~6 dB at the ILM, which is why those two
surfaces come out prior-only.

## Verification against our own data

Stacking the peripheral column from the ILM predicts boundary depths that match
landmarks measured independently in the TS165 wild-type slab (85 B-scans,
ILM-flattened, vessel-free A-lines only) to within ~8 µm — including four
landmarks within ~4 µm. See the table in `SKILL.md`. That agreement is the
evidence that the current labelling is right and the previous one was not; it
is worth re-running if the priors are ever changed.
