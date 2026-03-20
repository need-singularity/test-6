import pytest
from tecs_h.collision.predictor import predict, PREDICTION_PROMPT_TEMPLATE


class TestPredict:
    def test_returns_prediction_dict(self, mocker):
        mock_claude = mocker.patch("tecs_h.collision.predictor.claude_call")
        mock_claude.return_value = {
            "beta0": 1, "beta1": 5, "hierarchy_score": 0.7,
            "max_persistence_h1": 0.4, "reasoning": "test"
        }
        result = predict(["Q11348", "Q192439"], hop=2)
        assert "beta0" in result
        assert "beta1" in result
        assert "hierarchy_score" in result
        assert "reasoning" in result

    def test_prompt_contains_entities(self, mocker):
        mock_claude = mocker.patch("tecs_h.collision.predictor.claude_call")
        mock_claude.return_value = {"beta0": 1, "beta1": 0, "hierarchy_score": 0.5, "max_persistence_h1": 0.1, "reasoning": "x"}
        predict(["Q11348", "Q192439"], hop=2)
        prompt = mock_claude.call_args[0][0]
        assert "Q11348" in prompt
        assert "Q192439" in prompt

    def test_prompt_template_has_required_fields(self):
        assert "beta0" in PREDICTION_PROMPT_TEMPLATE
        assert "beta1" in PREDICTION_PROMPT_TEMPLATE
        assert "hierarchy_score" in PREDICTION_PROMPT_TEMPLATE


from tecs_h.collision.clash import detect_clashes, ClashStrength


class TestDetectClashes:
    def test_strong_clash(self, sample_prediction, sample_actual):
        clashes = detect_clashes(sample_prediction, sample_actual)
        assert len(clashes) > 0
        beta1_clash = next(c for c in clashes if c["field"] == "beta1")
        assert beta1_clash["strength"] == ClashStrength.STRONG

    def test_no_clash_when_close(self):
        pred = {"beta0": 1, "beta1": 5, "hierarchy_score": 0.7, "max_persistence_h1": 0.5}
        actual = {"beta0": 1, "beta1": 6, "hierarchy_score": 0.65, "max_persistence_h1": 0.5}
        clashes = detect_clashes(pred, actual)
        assert len(clashes) == 0

    def test_zero_division_safe(self):
        pred = {"beta0": 0, "beta1": 0, "hierarchy_score": 0.0, "max_persistence_h1": 0.0}
        actual = {"beta0": 0, "beta1": 0, "hierarchy_score": 0.0, "max_persistence_h1": 0.0}
        clashes = detect_clashes(pred, actual)
        assert len(clashes) == 0

    def test_low_persistence_ignores_beta1(self):
        pred = {"beta0": 1, "beta1": 1, "hierarchy_score": 0.5, "max_persistence_h1": 0.005}
        actual = {"beta0": 1, "beta1": 50, "hierarchy_score": 0.5, "max_persistence_h1": 0.005}
        clashes = detect_clashes(pred, actual)
        beta1_clashes = [c for c in clashes if c["field"] == "beta1"]
        assert len(beta1_clashes) == 0

    def test_clash_includes_gap(self, sample_prediction, sample_actual):
        clashes = detect_clashes(sample_prediction, sample_actual)
        for c in clashes:
            assert "predicted" in c
            assert "actual" in c
            assert "gap" in c


from tecs_h.collision.resolver import resolve, RESOLVER_PROMPT_TEMPLATE


class TestResolve:
    def test_returns_hypothesis_dict(self, mocker):
        mock_claude = mocker.patch("tecs_h.collision.resolver.claude_call")
        mock_claude.return_value = {
            "hypothesis": "test hypothesis",
            "explanation": "test explanation",
            "testable_prediction": "test prediction",
            "involved_entities": ["Q1", "Q2"],
            "confidence": 0.7
        }
        clashes = [{"field": "beta1", "predicted": 3, "actual": 47, "gap": 44, "strength": "strong"}]
        pred = {"beta0": 1, "beta1": 3}
        actual = {"beta0": 1, "beta1": 47}
        result = resolve(pred, actual, clashes)
        assert "hypothesis" in result
        assert "confidence" in result
        assert "involved_entities" in result

    def test_prompt_includes_clash_data(self, mocker):
        mock_claude = mocker.patch("tecs_h.collision.resolver.claude_call")
        mock_claude.return_value = {
            "hypothesis": "h", "explanation": "e",
            "testable_prediction": "t", "involved_entities": [], "confidence": 0.5
        }
        clashes = [{"field": "beta1", "predicted": 3, "actual": 47, "gap": 44, "strength": "strong"}]
        resolve({"beta1": 3}, {"beta1": 47}, clashes)
        prompt = mock_claude.call_args[0][0]
        assert "47" in prompt
        assert "3" in prompt
