import threading
import time
from datetime import datetime
from unittest.mock import patch

import pytest

from src.logic import APICalls
from src.logic.APICalls import DownloadCancelled, parallel_map, get_commits_since, get_with_ratelimit

DATE = datetime(2023, 11, 1)


@pytest.fixture(autouse=True)
def reset_cancel_event():
    APICalls.cancel_event.clear()
    yield
    APICalls.cancel_event.clear()


def test_parallel_map_keeps_order():
    def slow_square(x):
        time.sleep(0.01 * (5 - x % 5))  # i primi elementi finiscono per ultimi
        return x * x

    assert parallel_map(slow_square, range(20)) == [x * x for x in range(20)]


def test_parallel_map_uses_threads():
    threads = set()

    def record(_):
        threads.add(threading.get_ident())
        time.sleep(0.05)

    parallel_map(record, range(APICalls.MAX_WORKERS))
    assert len(threads) > 1


def test_parallel_map_progress():
    calls = []
    parallel_map(lambda x: x, range(5), lambda label, done, total: calls.append((label, done, total)), "Test")
    assert calls[-1] == ("Test", 5, 5)
    assert [done for _, done, _ in calls] == sorted(done for _, done, _ in calls)


def test_parallel_map_empty():
    assert parallel_map(lambda x: x, []) == []


def test_parallel_map_propagates_cancel():
    def cancel_on_three(x):
        if x == 3:
            raise DownloadCancelled()
        return x

    with pytest.raises(DownloadCancelled):
        parallel_map(cancel_on_three, range(10))


def test_get_commits_since_downloads_shared_commits_once():
    branches = [{"commit": {"sha": "b1"}}, {"commit": {"sha": "b2"}}]
    commits_by_branch = {
        "b1": [{"sha": "c1", "url": "u1"}, {"sha": "c2", "url": "u2"}],
        "b2": [{"sha": "c2", "url": "u2"}, {"sha": "c3", "url": "u3"}],  # c2 è in entrambi i branch
    }

    def fake_pages(url, header):
        if "/branches" in url:
            return branches
        return commits_by_branch[url.rsplit("sha=", 1)[1]]

    with patch.object(APICalls, "get_multiple_pages", side_effect=fake_pages), \
            patch.object(APICalls, "get_commit", side_effect=lambda url, header: {"url": url}) as get_commit:
        commits = get_commits_since("owner", "repo", DATE, "")

    assert sorted(c["url"] for c in commits) == ["u1", "u2", "u3"]
    assert get_commit.call_count == 3


def test_get_with_ratelimit_cancelled():
    APICalls.cancel_event.set()
    with pytest.raises(DownloadCancelled):
        get_with_ratelimit("https://api.github.com/repos/fullmoonlullaby/test", {})


def test_get_pulls_since_two_requests_per_pull():
    pulls = [{"number": n, "created_at": "2023-12-0%dT00:00:00Z" % n, "user": {"id": n, "login": f"u{n}"},
              "pull_request": {}} for n in (1, 2, 3)]
    comment = {"created_at": "2023-12-05T00:00:00Z", "user": {"id": 9, "login": "commentatore"},
               "issue_url": "https://api.github.com/repos/o/r/issues/2",
               "pull_request_url": "https://api.github.com/repos/o/r/pulls/3"}
    requested = []

    def fake_pages(url, header):
        requested.append(url)
        if "/issues/comments" in url or "/pulls/comments" in url:
            return [comment]
        return []

    with patch.object(APICalls, "get_issue_listing", return_value=pulls), \
            patch.object(APICalls, "get_multiple_pages", side_effect=fake_pages):
        results = APICalls.get_pulls_since("o", "r", DATE, "")

    per_pull = [u for u in requested if "/comments" not in u]
    assert len(per_pull) == 2 * len(pulls)  # solo reviews e commits per ogni PR
    assert len(requested) - len(per_pull) == 2  # commenti e commenti di review in blocco
    commenter = {"id": 9, "login": "commentatore"}
    assert commenter in [author for _, author in results[1]]  # commento della PR 2 (via issue_url)
    assert commenter in [author for _, author in results[2]]  # commento di review della PR 3
    assert commenter not in [author for _, author in results[0]]


class FakeResponse:
    def __init__(self, items, next_url=None):
        self.items = items
        self.headers = {"Link": f'<{next_url}>; rel="next"'} if next_url else {}

    def json(self):
        return self.items

    def raise_for_status(self):
        pass


def item(day):
    return {"created_at": f"2023-12-{day:02d}T00:00:00Z"}


def test_get_pages_until_stops_after_until():
    pages = {"p1": FakeResponse([item(1), item(2)], "p2"), "p2": FakeResponse([item(3), item(9)], "p3"),
             "p3": FakeResponse([item(10)])}
    requested = []

    def fake_get(url, header):
        requested.append(url)
        return pages[url]

    with patch.object(APICalls, "get_with_ratelimit", side_effect=fake_get):
        results = APICalls.get_pages_until("p1", {}, datetime(2023, 12, 5))
    assert [r["created_at"][8:10] for r in results] == ["01", "02", "03"]
    assert requested == ["p1", "p2"]  # la pagina p3 è tutta fuori intervallo: non viene richiesta


def test_get_pages_until_none_reads_everything():
    with patch.object(APICalls, "get_multiple_pages", return_value=[item(1), item(20)]) as pages:
        assert len(APICalls.get_pages_until("p1", {}, None)) == 2
    pages.assert_called_once()


def test_get_with_ratelimit_retries_network_errors():
    import requests
    ok = FakeResponse([])
    ok.status_code = 200
    attempts = []

    class FlakySession:
        def get(self, *args, **kwargs):
            attempts.append(1)
            if len(attempts) == 1:
                raise requests.Timeout("timeout simulato")
            return ok

    with patch.object(APICalls, "_session", lambda: FlakySession()), patch.object(APICalls.cancel_event, "wait",
                                                                                 return_value=False):
        assert get_with_ratelimit("https://api.github.com/x", {}) is ok
    assert len(attempts) == 2


def test_parallel_map_reports_progress_after_every_completed_item():
    calls = []
    gate = threading.Event()

    # il primo elemento resta bloccato finché non ha già finito il secondo: se il progresso arrivasse solo alla
    # fine, il secondo elemento non sarebbe mai notificato prima del primo
    def func(x):
        if x == 0:
            assert gate.wait(5)
        return x

    def progress(label, done, total):
        calls.append((done, total))
        if done >= 1:
            gate.set()

    parallel_map(func, [0, 1], progress, "Test")
    assert calls[0] == (1, 2)
    assert calls[-1] == (2, 2)


def test_parallel_map_progress_counts_each_item_once():
    calls = []
    parallel_map(lambda x: x, range(30), lambda label, done, total: calls.append(done), "Test")
    assert calls[-1] == 30
    assert calls == sorted(set(calls))  # sempre crescente, mai ripetuto
