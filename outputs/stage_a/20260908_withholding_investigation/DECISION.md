# Decision after frozen-array measurements

Do not change stage_a/inference.py in this investigation.

Whole-A-line crossing exclusion affects 130,257/262,144 WT A-lines (49.69%).
96,782 A-lines (36.92% of the volume) still retain some measurements and would
newly become completely withheld. This is one training WT volume, not an
estimate for every scan. Human-supported cost is measured on the labelled
splits: 3,973 extra boundary-columns lost on train and 2,968 on validation.

At virtually equal validation human-positive coverage (29,679 vs 29,682 retained
boundary-columns), whole-A-line exclusion leaves 7.44% unreadable leakage versus
4.40% for entropy+signal; p95 error is 11.91 vs 11.05 um. Whole-A-line exclusion
does shorten the worst gross run more (35 vs 43), so this is a tradeoff, not
strict dominance on every outcome. The broad rule is not justified.

The >=4 flagged-surface variant is worth retaining as an experimental candidate.
It loses 630 supported validation boundary-columns, of which 541 (85.9%) are
from the single catastrophic B-scan. At matched coverage its leakage is nearly
identical to entropy+signal, p95 slightly better, and worst run identical.
Adding it to q0.96 entropy+signal gains only nine fewer unreadable surface-columns
than the matched-coverage score comparator, with two supported columns of
matching discrepancy. This small exploratory advantage, tested among several
variants on two corrected validation animals, is not enough to alter inference.

Shadow misses are not all redundant with entropy: the q0.94/q0.96 score catches
57.0%/47.8% of pooled shadow misses, and only 15.3%/10.2% of the 1,104 columns
caught by no existing reason. However, remaining misses overlap strongly with
readable tissue in the measured signal features. Five simple signal extensions
and their combinations with the score all leave more validation leakage than
the entropy+signal score at matched human-positive coverage. No cheap shadow
extension tested here earns adoption. This does not rule out a future spatial
detector; it rules out claiming that these simple extensions solved the misses.

The investigation is complete with a negative adoption decision and saved
experimental masks, tables and representative overlays. No inference edit,
checkpoint rewrite, training, branch mutation, or merge is needed. Re-test the
>=4 candidate and residual misses on the longer-trained checkpoint before any
further adoption decision. Longer training remains a separate experiment.
