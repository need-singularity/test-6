import json
import os
import pytest
from tecs_h.output.formatter import format_hypothesis, save_result


class TestFormatHypothesis:
    def test_generates_id(self, sample_hypothesis, sample_prediction, sample_actual):
        clashes = [{"field": "beta1", "predicted": 3, "actual": 47, "gap": 44, "strength": "strong"}]
        result = format_hypothesis(hypothesis=sample_hypothesis, prediction=sample_prediction, actual=sample_actual, clashes=clashes)
        assert result["id"].startswith("hyp_")
        assert len(result["id"]) == len("hyp_YYYYMMDD_XXXXXX")

    def test_includes_all_fields(self, sample_hypothesis, sample_prediction, sample_actual):
        clashes = [{"field": "beta1", "predicted": 3, "actual": 47, "gap": 44, "strength": "strong"}]
        result = format_hypothesis(hypothesis=sample_hypothesis, prediction=sample_prediction, actual=sample_actual, clashes=clashes)
        assert "topological_basis" in result
        assert "natural_language" in result
        assert "confidence" in result

    def test_topological_basis_has_predicted_and_actual(self, sample_hypothesis, sample_prediction, sample_actual):
        clashes = [{"field": "beta1", "predicted": 3, "actual": 47, "gap": 44, "strength": "strong"}]
        result = format_hypothesis(hypothesis=sample_hypothesis, prediction=sample_prediction, actual=sample_actual, clashes=clashes)
        assert "predicted" in result["topological_basis"]
        assert "actual" in result["topological_basis"]


class TestSaveResult:
    def test_saves_to_correct_path(self, tmp_path, sample_hypothesis, sample_prediction, sample_actual):
        clashes = [{"field": "beta1", "predicted": 3, "actual": 47, "gap": 44, "strength": "strong"}]
        result = format_hypothesis(hypothesis=sample_hypothesis, prediction=sample_prediction, actual=sample_actual, clashes=clashes)
        path = save_result(result, base_dir=str(tmp_path))
        assert os.path.exists(path)
        with open(path) as f:
            loaded = json.load(f)
        assert loaded["id"] == result["id"]
