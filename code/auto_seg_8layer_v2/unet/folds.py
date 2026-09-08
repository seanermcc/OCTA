"""Animal-level cross-validation folds, derived from whatever is labelled now.

Deliberately a function over the current label set rather than a frozen list:
as more review packs are labelled the new animals are absorbed without editing
code.  Whole animals only -- volumes from one animal never straddle a fold, so
neither do same-session repeats.

Animal identity is the number only (``TS241``); sex letters conflict between
sessions for the same animal.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations


def animal_of(scan_id: str) -> str:
    return str(scan_id).split("_", 1)[0]


def animals_present(records) -> list[str]:
    return sorted({animal_of(r["scan_id"]) for r in records})


@dataclass(frozen=True)
class Fold:
    index: int
    test_animals: tuple
    train_animals: tuple

    def is_test(self, scan_id: str) -> bool:
        return animal_of(scan_id) in self.test_animals


def leave_two_animals_out(animal_ids) -> list[Fold]:
    """Every unordered pair of animals held out in turn.

    With few animals a single held-out split is too noisy, so the spread across
    folds is what gets reported, not just the mean.  Falls back to
    leave-one-animal-out below three animals, where a pair would leave nothing
    to train on.
    """
    animals = sorted({str(a) for a in animal_ids})
    if len(animals) < 2:
        raise AssertionError(
            f"leave-two-animals-out needs at least 2 animals, got {animals}")
    size = 2 if len(animals) >= 4 else 1
    folds = []
    for index, test in enumerate(combinations(animals, size)):
        train = tuple(a for a in animals if a not in test)
        if not train:
            raise AssertionError("a fold would have no training animals")
        folds.append(Fold(index=index, test_animals=tuple(test), train_animals=train))
    return folds


def split_records(records, fold: Fold):
    """``(train_records, test_records)`` for one fold, with no animal straddling."""
    train = [r for r in records if not fold.is_test(r["scan_id"])]
    test = [r for r in records if fold.is_test(r["scan_id"])]
    overlap = ({animal_of(r["scan_id"]) for r in train}
               & {animal_of(r["scan_id"]) for r in test})
    if overlap:
        raise AssertionError(f"animals straddle the fold: {sorted(overlap)}")
    if not test:
        raise AssertionError(f"fold {fold.index} holds out no B-scans")
    return train, test


def fold_report(records) -> list[dict]:
    """Per-fold B-scan and scan counts, for printing before a training run."""
    folds = leave_two_animals_out(animals_present(records))
    rows = []
    for fold in folds:
        train, test = split_records(records, fold)
        rows.append({
            "fold": fold.index,
            "test_animals": "+".join(fold.test_animals),
            "n_train_bscans": len(train),
            "n_test_bscans": len(test),
            "n_train_scans": len({r["scan_id"] for r in train}),
            "n_test_scans": len({r["scan_id"] for r in test}),
        })
    return rows
