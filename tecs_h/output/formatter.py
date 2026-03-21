"""JSON + natural language hypothesis output formatter."""

import json
import os
import uuid
from datetime import date


def format_hypothesis(hypothesis: dict, prediction: dict, actual: dict, clashes: list[dict], evaluation: dict | None = None, novelty: dict | None = None) -> dict:
    today = date.today().strftime("%Y%m%d")
    hex_id = uuid.uuid4().hex[:6]
    primary_clash = clashes[0] if clashes else {}
    return {
        "id": f"hyp_{today}_{hex_id}",
        "hypothesis": hypothesis.get("hypothesis", ""),
        "explanation": hypothesis.get("explanation", ""),
        "confidence": hypothesis.get("confidence", 0.0),
        "involved_entities": hypothesis.get("involved_entities", []),
        "topological_basis": {
            "predicted": {"beta0": prediction.get("beta0"), "beta1": prediction.get("beta1")},
            "actual": {"beta0": actual.get("beta0"), "beta1": actual.get("beta1")},
            "clash_type": f"{primary_clash.get('field', 'unknown')}_mismatch",
            "clash_gap": primary_clash.get("gap", 0),
        },
        "evaluation": evaluation or {},
        "novelty": novelty or {},
        "testable_prediction": hypothesis.get("testable_prediction", ""),
        "natural_language": _generate_natural_language(hypothesis, prediction, actual, clashes),
    }


def _generate_natural_language(hypothesis, prediction, actual, clashes):
    entities = ", ".join(hypothesis.get("involved_entities", []))
    parts = [f"엔티티 [{entities}]의 서브그래프 분석 결과:"]
    for clash in clashes:
        parts.append(f"  {clash['field']}: 예측={clash['predicted']}, 실제={clash['actual']} (차이={clash['gap']})")
    parts.append(f"가설: {hypothesis.get('hypothesis', '')}")
    parts.append(f"확신도: {hypothesis.get('confidence', 0):.2f}")
    return "\n".join(parts)


def save_result(result: dict, base_dir: str = "results") -> str:
    today = date.today().strftime("%Y-%m-%d")
    dir_path = os.path.join(base_dir, today)
    os.makedirs(dir_path, exist_ok=True)
    file_path = os.path.join(dir_path, f"{result['id']}.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    # Append to summary log
    _append_summary(result, base_dir)
    return file_path


def _append_summary(result: dict, base_dir: str = "results") -> None:
    """Append one-line summary to cumulative log file."""
    log_path = os.path.join(base_dir, "hypothesis_log.tsv")
    exists = os.path.exists(log_path)
    with open(log_path, "a", encoding="utf-8") as f:
        if not exists:
            f.write("id\tconfidence\tclash_type\tclash_gap\thypothesis\n")
        hyp_text = result.get("hypothesis", "").replace("\t", " ").replace("\n", " ")[:200]
        clash_type = result.get("topological_basis", {}).get("clash_type", "")
        clash_gap = result.get("topological_basis", {}).get("clash_gap", 0)
        f.write(f"{result['id']}\t{result.get('confidence', 0):.2f}\t{clash_type}\t{clash_gap}\t{hyp_text}\n")
