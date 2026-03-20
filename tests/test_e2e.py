"""End-to-end test with all components mocked at the boundary."""
import pytest
from tecs_h.loop.batch import run_batch


class TestEndToEnd:
    def test_full_pipeline_produces_output(self, mocker, tmp_path):
        import subprocess
        import json

        mock_claude = mocker.patch("tecs_h.claude_io.client.subprocess.run")
        prediction = {"beta0": 1, "beta1": 3, "hierarchy_score": 0.8, "max_persistence_h1": 0.5, "reasoning": "test"}
        hypothesis = {"hypothesis": "새로운 구조적 관계", "explanation": "β₁ 차이가 큼",
                      "testable_prediction": "유사 쌍에서도 재현", "involved_entities": ["Q11348", "Q192439"], "confidence": 0.72}
        non_topo_hyp = {"hypothesis": "completely different"}
        comparison = {"same_core_claim": False, "confidence": 0.9}
        repackaging = {"is_repackaging": False, "confidence": 0.2, "original_fact": ""}
        call_count = {"n": 0}

        def mock_run_side_effect(*args, **kwargs):
            responses = [prediction, hypothesis, non_topo_hyp, comparison, repackaging]
            idx = min(call_count["n"], len(responses) - 1)
            call_count["n"] += 1
            return subprocess.CompletedProcess(args=[], returncode=0,
                stdout=json.dumps(responses[idx], ensure_ascii=False), stderr="")

        mock_claude.side_effect = mock_run_side_effect

        mocker.patch("tecs_h.graph.builder._sparql_query", return_value={
            "results": {"bindings": [
                {"source": {"value": "http://www.wikidata.org/entity/Q11348"},
                 "target": {"value": "http://www.wikidata.org/entity/Q192439"},
                 "prop": {"value": "http://www.wikidata.org/prop/direct/P279"}}
            ]}
        })
        mocker.patch("tecs_h.novelty.filter._sparql_query", return_value={"boolean": False})
        mocker.patch("tecs_h.verify.cross_check._sparql_query", return_value={"results": {"bindings": []}})
        mocker.patch("tecs_h.loop.batch.cross_check", return_value={
            "reproduced": False, "warning": "형제 엔티티 부족", "confidence_adjustment": 0
        })

        mock_engine_cls = mocker.patch("tecs_h.loop.batch._get_engine")
        engine = mock_engine_cls.return_value
        engine.compute_topology_from_edges.return_value = {"beta0": 1, "beta1": 47, "max_persistence_h1": 0.85, "long_h1": []}
        engine.compute_hyperbolicity.return_value = {"hierarchy_score": 0.3}

        mocker.patch("tecs_h.evaluator.pipeline.filter_random", return_value={"status": "pass"})
        mocker.patch("tecs_h.evaluator.pipeline.filter_scale", return_value={"status": "pass"})

        seed_groups = [{"entities": ["Q11348", "Q192439"], "hop": 2}]
        results = run_batch(seed_groups, rounds_per_group=1, results_dir=str(tmp_path))
        assert len(results) >= 1
        result = results[0]
        assert result["id"].startswith("hyp_")
        assert result["hypothesis"] != ""
        assert "topological_basis" in result

    def test_empty_batch_no_crash(self, mocker):
        results = run_batch([], rounds_per_group=5)
        assert results == []
