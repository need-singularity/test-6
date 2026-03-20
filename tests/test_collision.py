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
