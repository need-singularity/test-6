import pytest
from tecs_h.evaluator.random_baseline import filter_random, generate_random_graph


class TestGenerateRandomGraph:
    def test_correct_shape(self):
        graph = generate_random_graph(n_nodes=10, n_edges=15)
        assert graph["n_nodes"] == 10
        assert len(graph["edges"]) <= 15

    def test_no_self_loops(self):
        graph = generate_random_graph(n_nodes=10, n_edges=15)
        for u, v in graph["edges"]:
            assert u != v


class TestFilterRandom:
    def test_passes_unique_topology(self, mocker, sample_actual):
        mock_engine = mocker.patch("tecs_h.evaluator.random_baseline._get_engine")
        engine = mock_engine.return_value
        engine.compute_topology_from_edges.return_value = {"beta0": 5, "beta1": 0, "max_persistence_h1": 0.01}
        result = filter_random(sample_actual, n_nodes=10, n_edges=15)
        assert result["status"] == "pass"

    def test_rejects_common_topology(self, mocker, sample_actual):
        mock_engine = mocker.patch("tecs_h.evaluator.random_baseline._get_engine")
        engine = mock_engine.return_value
        engine.compute_topology_from_edges.return_value = {
            "beta0": sample_actual["beta0"], "beta1": sample_actual["beta1"],
            "max_persistence_h1": sample_actual["max_persistence_h1"],
        }
        result = filter_random(sample_actual, n_nodes=10, n_edges=15)
        assert result["status"] == "reject"


from tecs_h.evaluator.scale_test import filter_scale


class TestFilterScale:
    def test_passes_persistent_pattern(self, mocker):
        mock_build = mocker.patch("tecs_h.evaluator.scale_test.build_subgraph")
        mock_engine = mocker.patch("tecs_h.evaluator.scale_test._get_engine")
        engine = mock_engine.return_value
        mock_build.side_effect = [
            {"edges": [(0, 1)], "n_nodes": 10, "nodes": list(range(10))},
            {"edges": [(0, 1)], "n_nodes": 50, "nodes": list(range(50))},
        ]
        engine.compute_topology_from_edges.return_value = {"beta0": 1, "beta1": 10, "max_persistence_h1": 0.5}
        result = filter_scale(actual_topology={"beta0": 1, "beta1": 10}, entities=["Q1"], original_hop=2, max_nodes=300)
        assert result["status"] == "pass"

    def test_rejects_vanishing_pattern(self, mocker):
        mock_build = mocker.patch("tecs_h.evaluator.scale_test.build_subgraph")
        mock_engine = mocker.patch("tecs_h.evaluator.scale_test._get_engine")
        engine = mock_engine.return_value
        mock_build.side_effect = [
            {"edges": [(0, 1)], "n_nodes": 10, "nodes": list(range(10))},
            {"edges": [(0, 1)], "n_nodes": 50, "nodes": list(range(50))},
        ]
        engine.compute_topology_from_edges.side_effect = [
            {"beta0": 5, "beta1": 0, "max_persistence_h1": 0.01},
            {"beta0": 1, "beta1": 0, "max_persistence_h1": 0.01},
        ]
        result = filter_scale(actual_topology={"beta0": 1, "beta1": 10}, entities=["Q1"], original_hop=2, max_nodes=300)
        assert result["status"] == "reject"


from tecs_h.evaluator.non_topo_baseline import filter_non_topo


class TestFilterNonTopo:
    def test_passes_unique_hypothesis(self, mocker, sample_hypothesis):
        mock_claude = mocker.patch("tecs_h.evaluator.non_topo_baseline.claude_call")
        mock_claude.side_effect = [
            {"hypothesis": "completely different hypothesis about degree distribution"},
            {"same_core_claim": False, "confidence": 0.9},
        ]
        result = filter_non_topo(sample_hypothesis, graph_stats={"avg_degree": 3.2})
        assert result["status"] == "pass"

    def test_rejects_duplicate_hypothesis(self, mocker, sample_hypothesis):
        mock_claude = mocker.patch("tecs_h.evaluator.non_topo_baseline.claude_call")
        mock_claude.side_effect = [
            {"hypothesis": "basically the same thing"},
            {"same_core_claim": True, "confidence": 0.85},
        ]
        result = filter_non_topo(sample_hypothesis, graph_stats={"avg_degree": 3.2})
        assert result["status"] == "reject"

    def test_passes_when_comparison_low_confidence(self, mocker, sample_hypothesis):
        mock_claude = mocker.patch("tecs_h.evaluator.non_topo_baseline.claude_call")
        mock_claude.side_effect = [
            {"hypothesis": "somewhat similar"},
            {"same_core_claim": True, "confidence": 0.5},
        ]
        result = filter_non_topo(sample_hypothesis, graph_stats={"avg_degree": 3.2})
        assert result["status"] == "pass"


from tecs_h.evaluator.pipeline import evaluate


class TestEvaluatePipeline:
    def test_passes_all_filters(self, mocker, sample_hypothesis, sample_actual):
        mocker.patch("tecs_h.evaluator.pipeline.filter_random", return_value={"status": "pass"})
        mocker.patch("tecs_h.evaluator.pipeline.filter_scale", return_value={"status": "pass"})
        mocker.patch("tecs_h.evaluator.pipeline.filter_non_topo", return_value={"status": "pass"})
        result = evaluate(sample_hypothesis, sample_actual, ["Q1"], n_nodes=10, n_edges=15)
        assert result["status"] == "passed"
        assert result["filters_cleared"] == 3

    def test_stops_at_first_rejection(self, mocker, sample_hypothesis, sample_actual):
        mocker.patch("tecs_h.evaluator.pipeline.filter_random", return_value={"status": "reject", "reason": "random"})
        mock_scale = mocker.patch("tecs_h.evaluator.pipeline.filter_scale")
        mock_nontopo = mocker.patch("tecs_h.evaluator.pipeline.filter_non_topo")
        result = evaluate(sample_hypothesis, sample_actual, ["Q1"], n_nodes=10, n_edges=15)
        assert result["status"] == "rejected"
        mock_scale.assert_not_called()
        mock_nontopo.assert_not_called()
