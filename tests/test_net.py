from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
import responses

from math_aware_source_digest import config, net


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def make(
    tmp_path: Path, hosts: tuple[str, ...] = ("example.org", "arxiv.org"), **network: object
) -> tuple[net.Fetcher, FakeClock]:
    cfg = config.Config(cache_root=tmp_path / "cache")
    cfg = dataclasses.replace(
        cfg,
        downloads=config.DownloadConfig(allowed_hosts=hosts),
        network=dataclasses.replace(cfg.network, **network),  # type: ignore[arg-type]
    )
    clock = FakeClock()
    return net.Fetcher(cfg, clock=clock, wall_clock=clock, sleep=clock.sleep), clock


# Policy


@pytest.mark.parametrize(
    "url",
    ["https://example.org/a", "https://export.arxiv.org/api", "https://EXAMPLE.org./b"],
)
def test_policy_allows_listed_hosts_and_subdomains(url: str) -> None:
    net.DownloadPolicy(["example.org", "arxiv.org"]).check(url)


@pytest.mark.parametrize(
    "url", ["https://evil.org/x", "https://notexample.org/", "https://example.org.evil.org/"]
)
def test_policy_asks_for_other_hosts(url: str) -> None:
    with pytest.raises(net.ApprovalRequired):
        net.DownloadPolicy(["example.org"]).check(url)


@pytest.mark.parametrize("url", ["http://example.org/", "file:///etc/passwd", "ftp://example.org/"])
def test_policy_refuses_other_schemes(url: str) -> None:
    with pytest.raises(net.NetError):
        net.DownloadPolicy(["example.org"]).check(url)


def test_empty_policy_asks_for_everything() -> None:
    with pytest.raises(net.ApprovalRequired):
        net.DownloadPolicy([]).check("https://arxiv.org/abs/1")


def test_approval_covers_one_url_not_its_host() -> None:
    policy = net.DownloadPolicy([])
    policy.approve("https://evil.org/paper.pdf")
    policy.check("https://evil.org/paper.pdf")
    with pytest.raises(net.ApprovalRequired):
        policy.check("https://evil.org/other.pdf")


@responses.activate
def test_unlisted_host_makes_no_request(tmp_path: Path) -> None:
    fetcher, _ = make(tmp_path)
    with pytest.raises(net.ApprovalRequired):
        fetcher.get("https://unlisted.org/x")
    assert len(responses.calls) == 0


@responses.activate
def test_redirect_out_of_policy_is_stopped(tmp_path: Path) -> None:
    responses.get("https://example.org/a", status=302, headers={"Location": "https://evil.org/b"})
    fetcher, _ = make(tmp_path)
    with pytest.raises(net.ApprovalRequired, match=r"evil\.org"):
        fetcher.get("https://example.org/a")


@responses.activate
def test_redirect_within_policy_is_followed(tmp_path: Path) -> None:
    responses.get("https://example.org/a", status=301, headers={"Location": "/b"})
    responses.get("https://example.org/b", body=b"ok")
    fetcher, _ = make(tmp_path)
    assert fetcher.get("https://example.org/a").content == b"ok"


@responses.activate
def test_redirect_loop_stops(tmp_path: Path) -> None:
    responses.get("https://example.org/a", status=302, headers={"Location": "/b"})
    responses.get("https://example.org/b", status=302, headers={"Location": "/a"})
    fetcher, _ = make(tmp_path)
    with pytest.raises(net.NetError, match="redirects"):
        fetcher.get("https://example.org/a", cache=False)


# Spacing


@responses.activate
def test_arxiv_requests_are_three_seconds_apart(tmp_path: Path) -> None:
    responses.get("https://export.arxiv.org/api/query", body=b"x")
    fetcher, clock = make(tmp_path)
    for i in range(3):
        fetcher.get("https://export.arxiv.org/api/query", params={"id": str(i)})
    assert clock.sleeps == [3.0, 3.0]


@responses.activate
def test_other_hosts_use_the_default_interval(tmp_path: Path) -> None:
    responses.get("https://example.org/a", body=b"x")
    fetcher, clock = make(tmp_path)
    fetcher.get("https://example.org/a", cache=False)
    clock.now += 0.25
    fetcher.get("https://example.org/a", cache=False)
    assert clock.sleeps == [0.75]


# Backoff


@responses.activate
def test_429_honours_retry_after(tmp_path: Path) -> None:
    responses.get("https://example.org/a", status=429, headers={"Retry-After": "7"})
    responses.get("https://example.org/a", body=b"ok")
    fetcher, clock = make(tmp_path)
    assert fetcher.get("https://example.org/a").content == b"ok"
    assert 7.0 in clock.sleeps


@responses.activate
def test_503_backs_off_exponentially_then_gives_up(tmp_path: Path) -> None:
    responses.get("https://example.org/a", status=503)
    fetcher, clock = make(tmp_path, max_retries=3)
    with pytest.raises(net.RateLimited, match="after 3 retries"):
        fetcher.get("https://example.org/a")
    assert len(responses.calls) == 4
    backoffs = [s for s in clock.sleeps if s >= net.BACKOFF_BASE_S]
    assert backoffs == [5.0, 10.0, 20.0]


def test_retry_after_parses_dates_and_caps() -> None:
    assert net.retry_after_s("Wed, 21 Oct 2015 07:28:10 GMT", 0, now=1445412480.0) == 10.0
    assert net.retry_after_s("100000", 0, now=0) == net.BACKOFF_MAX_S
    assert net.retry_after_s("garbage", 2, now=0) == 20.0


@responses.activate
def test_other_errors_are_not_retried(tmp_path: Path) -> None:
    responses.get("https://example.org/a", status=404)
    fetcher, _ = make(tmp_path)
    with pytest.raises(net.NetError, match="HTTP 404"):
        fetcher.get("https://example.org/a")
    assert len(responses.calls) == 1


# Cache


@responses.activate
def test_second_request_comes_from_the_cache(tmp_path: Path) -> None:
    responses.get("https://example.org/a", json={"v": 1})
    fetcher, _ = make(tmp_path)
    first = fetcher.get("https://example.org/a")
    second = fetcher.get("https://example.org/a")
    assert not first.from_cache and second.from_cache
    assert second.json() == {"v": 1}
    assert len(responses.calls) == 1


@responses.activate
def test_refresh_bypasses_the_cache(tmp_path: Path) -> None:
    responses.get("https://example.org/a", body=b"1")
    fetcher, _ = make(tmp_path)
    fetcher.get("https://example.org/a")
    fetcher.get("https://example.org/a", refresh=True)
    assert len(responses.calls) == 2


@responses.activate
def test_post_bodies_are_part_of_the_cache_key(tmp_path: Path) -> None:
    responses.post("https://example.org/batch", json=[1])
    fetcher, _ = make(tmp_path)
    fetcher.post_json("https://example.org/batch", {"ids": ["a"]})
    fetcher.post_json("https://example.org/batch", {"ids": ["b"]})
    fetcher.post_json("https://example.org/batch", {"ids": ["a"]})
    assert len(responses.calls) == 2


@responses.activate
def test_failures_are_not_cached(tmp_path: Path) -> None:
    responses.get("https://example.org/a", status=500)
    responses.get("https://example.org/a", body=b"ok")
    fetcher, _ = make(tmp_path)
    with pytest.raises(net.NetError):
        fetcher.get("https://example.org/a")
    assert fetcher.get("https://example.org/a").content == b"ok"


# Privacy


@responses.activate
def test_contact_email_is_sent_only_when_configured(tmp_path: Path) -> None:
    responses.get("https://example.org/a", body=b"x")
    fetcher, _ = make(tmp_path)
    fetcher.get("https://example.org/a")
    assert "mailto" not in responses.calls[0].request.headers["User-Agent"]

    fetcher2, _ = make(tmp_path / "2", contact_email="me@example.org")
    fetcher2.get("https://example.org/a")
    assert "mailto:me@example.org" in responses.calls[1].request.headers["User-Agent"]
