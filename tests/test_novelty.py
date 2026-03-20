import pytest
from tecs_h.novelty.filter import filter_novelty, check_wikidata_relation, check_trivial_specialization


class TestCheckWikidataRelation:
    def test_finds_existing_relation(self, mocker):
        mock_query = mocker.patch("tecs_h.novelty.filter._sparql_query")
        mock_query.return_value = {"boolean": True}
        assert check_wikidata_relation("Q1", "Q2") is True

    def test_no_relation(self, mocker):
        mock_query = mocker.patch("tecs_h.novelty.filter._sparql_query")
        mock_query.return_value = {"boolean": False}
        assert check_wikidata_relation("Q1", "Q2") is False


class TestCheckTrivialSpecialization:
    def test_trivial_parent_child(self, mocker):
        mock_query = mocker.patch("tecs_h.novelty.filter._sparql_query")
        mock_query.return_value = {"boolean": True}
        assert check_trivial_specialization("Q1", "Q2") is True

    def test_not_trivial(self, mocker):
        mock_query = mocker.patch("tecs_h.novelty.filter._sparql_query")
        mock_query.return_value = {"boolean": False}
        assert check_trivial_specialization("Q1", "Q2") is False


class TestFilterNovelty:
    def test_rejects_existing_relation(self, mocker):
        mocker.patch("tecs_h.novelty.filter.check_wikidata_relation", return_value=True)
        hyp = {"involved_entities": ["Q1", "Q2"], "hypothesis": "test"}
        result = filter_novelty(hyp)
        assert result["status"] == "reject"

    def test_rejects_repackaging(self, mocker):
        mocker.patch("tecs_h.novelty.filter.check_wikidata_relation", return_value=False)
        mocker.patch("tecs_h.novelty.filter.check_trivial_specialization", return_value=False)
        mock_claude = mocker.patch("tecs_h.novelty.filter.llm_call")
        mock_claude.return_value = {"is_repackaging": True, "confidence": 0.9, "original_fact": "known theorem"}
        hyp = {"involved_entities": ["Q1", "Q2"], "hypothesis": "test"}
        result = filter_novelty(hyp)
        assert result["status"] == "reject"

    def test_passes_novel(self, mocker):
        mocker.patch("tecs_h.novelty.filter.check_wikidata_relation", return_value=False)
        mocker.patch("tecs_h.novelty.filter.check_trivial_specialization", return_value=False)
        mock_claude = mocker.patch("tecs_h.novelty.filter.llm_call")
        mock_claude.return_value = {"is_repackaging": False, "confidence": 0.3, "original_fact": ""}
        hyp = {"involved_entities": ["Q1", "Q2"], "hypothesis": "test"}
        result = filter_novelty(hyp)
        assert result["status"] == "pass"
