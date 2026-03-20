"""Clash detection: compare predicted vs actual topological invariants."""

from enum import Enum


class ClashStrength(str, Enum):
    STRONG = "strong"
    MEDIUM = "medium"
    WEAK = "weak"


FIELDS = ["beta0", "beta1", "hierarchy_score", "max_persistence_h1"]
PERSISTENCE_THRESHOLD = 0.01


def detect_clashes(prediction: dict, actual: dict) -> list[dict]:
    """Detect clashes between predicted and actual topological values.

    Returns list of clash dicts with field, predicted, actual, gap, strength.
    Skips beta1 clash if max_persistence_h1 < PERSISTENCE_THRESHOLD.
    """
    clashes = []
    actual_persistence = actual.get("max_persistence_h1", 0)

    for field in FIELDS:
        pred_val = prediction.get(field, 0)
        actual_val = actual.get(field, 0)

        if field == "beta1" and actual_persistence < PERSISTENCE_THRESHOLD:
            continue

        gap = abs(pred_val - actual_val)
        max_val = max(pred_val, actual_val)

        if max_val == 0:
            continue

        ratio = gap / max_val

        if ratio > 0.5:
            strength = ClashStrength.STRONG
        elif ratio > 0.2:
            strength = ClashStrength.MEDIUM
        else:
            continue

        clashes.append({
            "field": field,
            "predicted": pred_val,
            "actual": actual_val,
            "gap": gap,
            "strength": strength,
        })

    return clashes
