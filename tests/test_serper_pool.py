import requests
import pytest

from datetime import date

from src.serper_client import SerperClient, SerperPoolExhausted, generate_query_plan


class Response:
    def __init__(self, status, payload):
        self.status_code = status
        self.payload = payload
        self.ok = 200 <= status < 300

    def json(self):
        return self.payload


class Session:
    def __init__(self, outcomes):
        self.outcomes = iter(outcomes)
        self.keys = []

    def post(self, _url, json, headers, timeout):
        self.keys.append(headers["X-API-KEY"])
        outcome = next(self.outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def test_quota_rotates_to_second_key():
    session = Session([Response(429, {"message": "quota"}), Response(200, {"news": []})])
    client = SerperClient(["first", "second"], session=session, max_retries=1)
    assert client._request({"q": "test"}) == {"news": []}
    assert session.keys == ["first", "second"]
    assert client.diagnostics["key_failovers"] == 1


def test_timeout_retries_same_key_before_rotation():
    session = Session([
        requests.Timeout(), Response(429, {"message": "quota"}), Response(200, {"news": []}),
    ])
    client = SerperClient(["first", "second"], session=session, max_retries=1)
    client._request({"q": "test"})
    assert session.keys == ["first", "first", "second"]
    assert client.diagnostics["retries"] == 1


def test_all_keys_fail_in_controlled_way():
    session = Session([Response(401, {}), Response(429, {})])
    client = SerperClient(["first", "second"], session=session, max_retries=0)
    with pytest.raises(SerperPoolExhausted, match="menolak"):
        client._request({"q": "test"})


def test_query_plan_uses_only_selected_taxonomy_and_inclusive_boundaries(config):
    plan = generate_query_plan(
        ["LU.F"], config.taxonomy, config.keywords, date(2026, 7, 1), date(2026, 9, 6),
    )
    assert len(plan) == 2
    assert {item.taxonomy_code for item in plan} == {"LU.F"}
    assert {item.scope for item in plan} == {"local", "province"}
    assert all("after:2026-06-30 before:2026-09-07" in item.query for item in plan)
