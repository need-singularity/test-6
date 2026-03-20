import pytest
from tecs_h.loop.batch import run_collision_round, run_batch


class TestRunCollisionRound:
    def test_skips_when_no_clash(self, mocker):
        mocker.patch("tecs_h.loop.batch.build_subgraph", return_value={
            "edges": [(0, 1)], "n_nodes": 2, "nodes": ["Q1", "Q2"]
        })
        mock_predict = mocker.patch("tecs_h.loop.batch.predict")
        mock_predict.return_value = {"beta0": 1, "beta1": 5, "hierarchy_score": 0.7, "max_persistence_h1": 0.5}
        mock_compute = mocker.patch("tecs_h.loop.batch.compute_topology")
        mock_compute.return_value = {"beta0": 1, "beta1": 5, "hierarchy_score": 0.7, "max_persistence_h1": 0.5, "long_h1": []}
        mock_clash = mocker.patch("tecs_h.loop.batch.detect_clashes")
        mock_clash.return_value = []
        result = run_collision_round(["Q1", "Q2"], hop=2)
        assert result is None

    def test_returns_hypothesis_on_clash(self, mocker):
        mocker.patch("tecs_h.loop.batch.build_subgraph", return_value={
            "edges": [(0, 1)], "n_nodes": 2, "nodes": ["Q1", "Q2"]
        })
        mocker.patch("tecs_h.loop.batch.predict", return_value={"beta0": 1, "beta1": 3, "hierarchy_score": 0.8, "max_persistence_h1": 0.5})
        mocker.patch("tecs_h.loop.batch.compute_topology", return_value={"beta0": 1, "beta1": 47, "hierarchy_score": 0.3, "max_persistence_h1": 0.85, "long_h1": []})
        mocker.patch("tecs_h.loop.batch.detect_clashes", return_value=[{"field": "beta1", "predicted": 3, "actual": 47, "gap": 44, "strength": "strong"}])
        mocker.patch("tecs_h.loop.batch.resolve", return_value={
            "hypothesis": "test", "explanation": "test", "testable_prediction": "test", "involved_entities": ["Q1"], "confidence": 0.7
        })
        result = run_collision_round(["Q1", "Q2"], hop=2)
        assert result is not None
        assert "hypothesis" in result


class TestRunBatch:
    def test_collects_results(self, mocker):
        mock_round = mocker.patch("tecs_h.loop.batch.run_collision_round")
        mock_round.side_effect = [
            {"hypothesis": {"hypothesis": "h1", "explanation": "e", "testable_prediction": "t", "involved_entities": ["Q1"], "confidence": 0.5},
             "prediction": {"beta0": 1, "beta1": 3}, "actual": {"beta0": 1, "beta1": 47},
             "clashes": [{"field": "beta1", "predicted": 3, "actual": 47, "gap": 44, "strength": "strong"}],
             "subgraph": {"edges": [(0,1)], "n_nodes": 2, "nodes": ["Q1","Q2"]}},
            None,
            {"hypothesis": {"hypothesis": "h2", "explanation": "e", "testable_prediction": "t", "involved_entities": ["Q2"], "confidence": 0.6},
             "prediction": {"beta0": 1, "beta1": 5}, "actual": {"beta0": 2, "beta1": 20},
             "clashes": [{"field": "beta1", "predicted": 5, "actual": 20, "gap": 15, "strength": "strong"}],
             "subgraph": {"edges": [(0,1)], "n_nodes": 2, "nodes": ["Q1","Q2"]}},
        ]
        seed_groups = [{"entities": ["Q1", "Q2"], "hop": 2}]
        results = run_batch(seed_groups, rounds_per_group=3)
        assert len(results) == 2

    def test_handles_round_error(self, mocker):
        mock_round = mocker.patch("tecs_h.loop.batch.run_collision_round")
        mock_round.side_effect = [Exception("test error"), None]
        seed_groups = [{"entities": ["Q1"], "hop": 2}]
        results = run_batch(seed_groups, rounds_per_group=2)
        assert len(results) == 0
