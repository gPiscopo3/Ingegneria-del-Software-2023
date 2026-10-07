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
