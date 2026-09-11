import requests
import pytest

from datetime import date

from src.config_loader import expand_selection
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


def test_rejected_key_is_not_reused_for_next_query():
    session = Session([Response(429, {}), Response(200, {"news": []}), Response(200, {"news": []})])
    client = SerperClient(["first", "second"], session=session)
    client._request({"q": "one"})
    client._request({"q": "two"})
    assert session.keys == ["first", "second", "second"]


def test_network_failure_does_not_discard_key():
    from src.serper_client import SerperError
    session = Session([requests.Timeout(), Response(200, {"news": []})])
    client = SerperClient(["first", "second"], session=session, max_retries=0)
    with pytest.raises(SerperError, match="Koneksi"):
        client._request({"q": "one"})
    client._request({"q": "two"})
    assert session.keys == ["first", "first"]
    assert client.diagnostics["key_failovers"] == 0


def test_parallel_queries_overlap_and_keep_order():
    from threading import Barrier
    from src.serper_client import QueryPlanItem
    barrier = Barrier(3)
    class ParallelSession:
        def post(self, _url, json, **_kwargs):
            barrier.wait(timeout=5)
            return Response(200, {"news": [{"title": json["q"], "link": "https://example.com"}]})
    client = SerperClient(["placeholder"], session=ParallelSession())
    plan = [QueryPlanItem("LU.F", "local", str(i)) for i in range(6)]
    records = client.collect(plan)
    assert [row["title"] for row in records] == [str(i) for i in range(6)]
    assert client.diagnostics["requests"] == 6
    assert client.diagnostics["completed_queries"] == 6


def test_partial_queries_survive_failure_and_pool_stops_new_batches(monkeypatch):
    from src.serper_client import QueryPlanItem
    client = SerperClient(["placeholder"])
    calls = []
    def request(payload):
        calls.append(payload["q"])
        if payload["q"] == "1":
            raise SerperPoolExhausted("fixture failure")
        return {"news": [{"title": payload["q"]}]}
    monkeypatch.setattr(client, "_request", request)
    records = client.collect([QueryPlanItem("LU.F", "local", str(i)) for i in range(8)])
    assert len(calls) == 3
    assert [row["title"] for row in records] == ["0", "2"]
    assert client.diagnostics["failed_queries"] == 6


def test_query_plan_uses_only_selected_taxonomy_and_inclusive_boundaries(config):
    plan = generate_query_plan(
        ["LU.F"], config.taxonomy, config.serper_keywords, date(2026, 7, 1), date(2026, 9, 6),
    )
    assert len(plan) == 2
    assert {item.taxonomy_code for item in plan} == {"LU.F"}
    assert {item.scope for item in plan} == {"local", "province"}
    assert all("after:2026-06-30 before:2026-09-07" in item.query for item in plan)


def test_selected_parent_uses_only_parent_keywords_and_can_create_multiple_packs(config):
    selected = expand_selection(["LU.C"], config.taxonomy)
    plan = generate_query_plan(
        selected, config.taxonomy, config.serper_keywords,
        date(2026, 7, 1), date(2026, 9, 6),
    )
    assert len(plan) == 4
    assert {item.taxonomy_code for item in plan} == {"LU.C"}
    assert sum(item.scope == "local" for item in plan) == 2
    assert sum(item.scope == "province" for item in plan) == 2


def test_concurrent_key_failover_rotates_once():
    from threading import Barrier, Lock
    from src.serper_client import QueryPlanItem
    barrier, lock = Barrier(3), Lock()
    calls = []
    class QuotaSession:
        def post(self, _url, headers, **_kwargs):
            with lock:
                calls.append(headers["X-API-KEY"])
            if headers["X-API-KEY"] == "first":
                barrier.wait(timeout=5)
                return Response(429, {})
            return Response(200, {"news": []})
    client = SerperClient(["first", "second"], session=QuotaSession())
    client.collect([QueryPlanItem("LU.F", "local", str(i)) for i in range(4)])
    assert calls.count("first") == 3
    assert calls.count("second") == 4
    assert client.diagnostics["key_failovers"] == 1
    assert client.diagnostics["requests"] == 7


@pytest.mark.parametrize("values,total,checked", [([10, 20], 30, 2), ([0, 0], 0, 2), ([10, None], None, 1), ([True, -1], None, 0)])
def test_credit_totals_are_complete_and_valid(monkeypatch, values, total, checked):
    from src.serper_client import fetch_serper_credits
    calls = []
    class BalanceResponse:
        def __init__(self, value): self.value = value
        def raise_for_status(self): pass
        def json(self): return {"balance": self.value, "credits": 999999}
    class BalanceSession:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def get(self, url, headers, **kwargs):
            assert url == "https://google.serper.dev/account"
            assert kwargs["allow_redirects"] is False
            key = headers["X-API-KEY"]
            calls.append(key)
            return BalanceResponse(values[int(key)])
    monkeypatch.setattr("src.serper_client.requests.Session", BalanceSession)
    result = fetch_serper_credits(["0", "1", "0", " "])
    assert result == {"total": total, "checked_keys": checked, "configured_keys": 2}
    assert sorted(calls) == ["0", "1"]


def test_balance_error_is_safe_and_empty_keys_do_not_request(monkeypatch):
    from src.serper_client import fetch_serper_credits
    class BadSession:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def get(self, *args, **kwargs): raise requests.Timeout("secret-value")
    monkeypatch.setattr("src.serper_client.requests.Session", BadSession)
    assert fetch_serper_credits([])["total"] == 0
    result = fetch_serper_credits(["placeholder"])
    assert result["total"] is None
    assert "secret-value" not in str(result)
