import json
from decimal import Decimal

import pytest

from merchmind.connected import ProviderTransport, connect_research
from merchmind.journey_models import ResearchConnection
from merchmind.models import NicheBrief, ResearchPolicy
from merchmind.starter import seed_segments


def brief():
    return NicheBrief(
        brief_id="connected-demo",
        merchant_id="cozy-vibe-demo",
        market_country="BD",
        niche="desk accessories",
        description="Research small accessories for people working at home.",
    )


def connection(**updates):
    return ResearchConnection(
        model="configured-model",
        research_hosts=["reviews.example.org"],
        search_price_per_request_usd="0.01",
        model_input_price_per_million_usd="1",
        model_output_price_per_million_usd="1",
        max_estimated_cost_usd="1",
        **updates,
    )


class FakeTransport:
    def __init__(self):
        self.calls = []
        self.bad_citation = False
        self.truncated = False
        self.fail = False

    def request(self, host, path, headers, body, **limits):
        self.calls.append((host, path, body))
        if self.fail:
            raise ValueError("synthetic failure")
        if host == "api.search.brave.com":
            return {
                "web": {
                    "results": [
                        {
                            "url": "https://reviews.example.org/desk",
                            "title": "Desk context",
                            "description": "Synthetic public snippet about small desks.",
                        },
                        {
                            "url": "https://unapproved.example.org/no",
                            "title": "Wrong host",
                            "description": "Excluded",
                        },
                    ]
                }
            }
        from merchmind.storage import evidence_record

        source = evidence_record(
            {
                "url": "https://reviews.example.org/desk",
                "title": "Desk context",
                "snippet": "Synthetic public snippet about small desks.",
            },
            kind="web_search_result",
            reference="https://reviews.example.org/desk",
            uri="https://reviews.example.org/desk",
            assertion="unused",
            verified="unverified",
        )
        segments = seed_segments(brief())
        for s in segments:
            s.kind = "research_inference"
            s.evidence_ids = ["missing-id" if self.bad_citation else source.evidence_id]
        return {
            "choices": [
                {
                    "finish_reason": "length" if self.truncated else "stop",
                    "message": {
                        "content": json.dumps(
                            {"segments": [s.model_dump(mode="json") for s in segments]}
                        )
                    },
                }
            ]
        }


@pytest.fixture(autouse=True)
def keys(monkeypatch):
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "secret-search-key")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "secret-model-key")


def test_search_and_synthesis_are_connected_and_keep_sources_unverified(fixture):
    client = FakeTransport()
    result = connect_research(
        brief(),
        fixture["merchant"],
        ResearchPolicy(),
        connection(),
        online=True,
        share_brief=True,
        transport=client,
    )
    assert result.status == "complete"
    assert len(result.sources) == 1
    assert len(result.research.segments) == 4
    assert all(
        s.kind == "research_inference" and s.confidence == "low" for s in result.research.segments
    )
    assert result.sources[0].verification_status == "unverified"
    assert len(client.calls) == 4  # Three searches (domain limit), one synthesis.
    serialized = result.model_dump_json()
    assert "secret-search-key" not in serialized and "secret-model-key" not in serialized


@pytest.mark.parametrize("online,share", [(False, False), (True, False), (False, True)])
def test_brief_is_not_transmitted_without_both_opt_ins(fixture, online, share):
    client = FakeTransport()
    with pytest.raises(ValueError, match="--online and --share-brief"):
        connect_research(
            brief(),
            fixture["merchant"],
            ResearchPolicy(),
            connection(),
            online=online,
            share_brief=share,
            transport=client,
        )
    assert not client.calls


def test_missing_keys_make_no_requests(fixture, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY")
    client = FakeTransport()
    with pytest.raises(ValueError, match="environment"):
        connect_research(
            brief(),
            fixture["merchant"],
            ResearchPolicy(),
            connection(),
            online=True,
            share_brief=True,
            transport=client,
        )
    assert not client.calls


def test_cost_budget_is_checked_before_requests(fixture):
    config = connection()
    config.max_estimated_cost_usd = Decimal("0.001")
    client = FakeTransport()
    with pytest.raises(ValueError, match="cost upper estimate"):
        connect_research(
            brief(),
            fixture["merchant"],
            ResearchPolicy(),
            config,
            online=True,
            share_brief=True,
            transport=client,
        )
    assert not client.calls


@pytest.mark.parametrize("problem", ["bad_citation", "truncated", "fail"])
def test_failed_synthesis_is_explicit_partial_without_fabricated_groups(fixture, problem):
    client = FakeTransport()
    setattr(client, problem, True)
    result = connect_research(
        brief(),
        fixture["merchant"],
        ResearchPolicy(),
        connection(),
        online=True,
        share_brief=True,
        transport=client,
    )
    assert result.status == "partial" and result.research is None
    assert result.warnings


def test_no_arbitrary_provider_host_or_network_call():
    with pytest.raises(ValueError, match="Unsupported provider"):
        ProviderTransport().request("localhost", "/", {}, None, deadline=0, max_bytes=1000)


def test_unknown_provider_prices_block_requests(fixture):
    config = connection()
    config.search_price_per_request_usd = None
    client = FakeTransport()
    with pytest.raises(ValueError, match="unknown rates"):
        connect_research(
            brief(),
            fixture["merchant"],
            ResearchPolicy(),
            config,
            online=True,
            share_brief=True,
            transport=client,
        )
    assert not client.calls


@pytest.mark.parametrize(
    "payload",
    [
        {"choices": None},
        {"choices": []},
        {"choices": [None]},
        {"choices": ["secret-model-key"]},
        {"choices": [{"finish_reason": "stop", "message": "invalid"}]},
        {"choices": [{"finish_reason": "stop", "message": {"content": " "}}]},
    ],
)
def test_malformed_provider_envelopes_are_partial_not_tracebacks(fixture, monkeypatch, payload):
    client = FakeTransport()
    original = client.request

    def request(host, path, headers, body, **limits):
        return (
            payload if host == "api.deepseek.com" else original(host, path, headers, body, **limits)
        )

    monkeypatch.setattr(client, "request", request)
    result = connect_research(
        brief(),
        fixture["merchant"],
        ResearchPolicy(),
        connection(),
        online=True,
        share_brief=True,
        transport=client,
    )
    assert result.status == "partial" and result.research is None
    assert result.sources
    assert "secret-model-key" not in result.model_dump_json()
