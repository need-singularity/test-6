import pytest
from tecs_h.graph.builder import (
    build_sparql_query,
    parse_sparql_response,
    build_subgraph,
    BLACKLIST,
    WHITELIST,
)


class TestSparqlQuery:
    def test_builds_valid_sparql(self):
        query = build_sparql_query(["Q11348"], hop=1)
        assert "Q11348" in query
        assert "SELECT" in query

    def test_excludes_blacklisted_properties(self):
        query = build_sparql_query(["Q11348"], hop=1)
        for prop in BLACKLIST:
            assert prop not in query or f"FILTER" in query


class TestParseSparqlResponse:
    def test_parses_bindings(self):
        response = {
            "results": {
                "bindings": [
                    {
                        "source": {"value": "http://www.wikidata.org/entity/Q11348"},
                        "target": {"value": "http://www.wikidata.org/entity/Q192439"},
                        "prop": {"value": "http://www.wikidata.org/prop/direct/P279"},
                    }
                ]
            }
        }
        nodes, edges = parse_sparql_response(response)
        assert "Q11348" in nodes
        assert "Q192439" in nodes
        assert len(edges) == 1

    def test_empty_response(self):
        response = {"results": {"bindings": []}}
        nodes, edges = parse_sparql_response(response)
        assert len(nodes) == 0
        assert len(edges) == 0


class TestBuildSubgraph:
    def test_returns_correct_shape(self, mocker):
        mock_query = mocker.patch("tecs_h.graph.builder._sparql_query")
        mock_query.return_value = {
            "results": {
                "bindings": [
                    {
                        "source": {"value": "http://www.wikidata.org/entity/Q1"},
                        "target": {"value": "http://www.wikidata.org/entity/Q2"},
                        "prop": {"value": "http://www.wikidata.org/prop/direct/P279"},
                    },
                    {
                        "source": {"value": "http://www.wikidata.org/entity/Q2"},
                        "target": {"value": "http://www.wikidata.org/entity/Q3"},
                        "prop": {"value": "http://www.wikidata.org/prop/direct/P31"},
                    },
                ]
            }
        }
        result = build_subgraph(["Q1"], hop=1)
        assert "nodes" in result
        assert "edges" in result
        assert "n_nodes" in result
        assert result["n_nodes"] == len(result["nodes"])
        assert all(isinstance(e, tuple) and len(e) == 2 for e in result["edges"])

    def test_respects_max_nodes(self, mocker):
        bindings = [
            {
                "source": {"value": f"http://www.wikidata.org/entity/Q{i}"},
                "target": {"value": f"http://www.wikidata.org/entity/Q{i+1}"},
                "prop": {"value": "http://www.wikidata.org/prop/direct/P279"},
            }
            for i in range(50)
        ]
        mock_query = mocker.patch("tecs_h.graph.builder._sparql_query")
        mock_query.return_value = {"results": {"bindings": bindings}}
        result = build_subgraph(["Q1"], hop=1, max_nodes=10)
        assert result["n_nodes"] <= 10
