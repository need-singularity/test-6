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
