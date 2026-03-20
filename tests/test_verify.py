import pytest
from tecs_h.verify.cross_check import find_sibling_entities, cross_check


class TestFindSiblingEntities:
    def test_finds_siblings(self, mocker):
        mock_query = mocker.patch("tecs_h.verify.cross_check._sparql_query")
        mock_query.return_value = {
            "results": {"bindings": [
                {"sibling": {"value": "http://www.wikidata.org/entity/Q100"}},
                {"sibling": {"value": "http://www.wikidata.org/entity/Q200"}},
            ]}
        }
        siblings = find_sibling_entities("Q1", limit=5)
        assert "Q100" in siblings
        assert "Q200" in siblings

    def test_empty_when_no_siblings(self, mocker):
        mock_query = mocker.patch("tecs_h.verify.cross_check._sparql_query")
        mock_query.return_value = {"results": {"bindings": []}}
        assert find_sibling_entities("Q1") == []


class TestCrossCheck:
    def test_reproduces_pattern(self, mocker):
        mocker.patch("tecs_h.verify.cross_check.find_sibling_entities", return_value=["Q100", "Q200"])
        mock_compute = mocker.patch("tecs_h.verify.cross_check._compute_and_check")
        mock_compute.return_value = True
        result = cross_check(hypothesis={"involved_entities": ["Q1", "Q2"]}, actual_topology={"beta0": 1, "beta1": 10}, min_checks=2)
        assert result["reproduced"]
        assert result["confidence_adjustment"] > 0

    def test_no_reproduction(self, mocker):
        mocker.patch("tecs_h.verify.cross_check.find_sibling_entities", return_value=["Q100", "Q200"])
        mock_compute = mocker.patch("tecs_h.verify.cross_check._compute_and_check")
        mock_compute.return_value = False
        result = cross_check(hypothesis={"involved_entities": ["Q1", "Q2"]}, actual_topology={"beta0": 1, "beta1": 10}, min_checks=2)
        assert not result["reproduced"]
        assert result["warning"] == "단일 사례"
