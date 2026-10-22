from datetime import datetime
from unittest.mock import patch

import pytest
import requests
from requests import HTTPError

from src.logic import APICalls
from src.logic.APICalls import get_issue_listing, get_pulls_since

START = datetime(2023, 12, 1, 8, 30, 0)
ISSUES_URL = "https://api.github.com/repos/o/r/issues"


def page(items, next_url=None, status=200):
    res = requests.Response()
    res.status_code = status
    res.json = lambda: items
    if next_url:
        res.headers["Link"] = f'<{next_url}>; rel="next"'
    return res


def entry(number, day, pull=False):
    item = {"number": number, "created_at": f"2023-12-{day:02d}T00:00:00Z", "user": {"id": 1, "login": "alice"}}
    if pull:
        item["pull_request"] = {}
    return item


def test_listing_requests_all_states_ordered_by_creation_since_start():
    requested = []

    def fake_get(url, _header):
        requested.append(url)
        return page([])

    with patch.object(APICalls, "get_with_ratelimit", side_effect=fake_get):
        get_issue_listing("o", "r", START, {})
    assert len(requested) == 1
    base, query = requested[0].split("?")
    assert base == ISSUES_URL
    assert sorted(query.split("&")) == sorted(["state=all", "per_page=100", "sort=created", "direction=asc",
                                               "since=2023-12-01T08:30:00Z"])


def test_listing_passes_the_header_to_every_request():
    headers = []

    def fake_get(url, header):
        headers.append(header)
        return page([entry(1, 2)], "p2") if url != "p2" else page([entry(2, 3)])

    with patch.object(APICalls, "get_with_ratelimit", side_effect=fake_get):
        get_issue_listing("o", "r", START, {"Authorization": "Bearer t"})
    assert headers == [{"Authorization": "Bearer t"}] * 2


def test_listing_keeps_issues_and_pulls_together():
    items = [entry(1, 2), entry(2, 3, pull=True)]
    with patch.object(APICalls, "get_with_ratelimit", return_value=page(items)):
        listing = get_issue_listing("o", "r", START, {})
    assert [("pull_request" in i) for i in listing] == [False, True]
    assert [i["number"] for i in listing] == [1, 2]


def test_listing_without_until_reads_all_pages():
    pages = {"p2": page([entry(3, 10)], "p3"), "p3": page([entry(4, 28)])}
    requested = []

    def fake_get(url, _header):
        requested.append(url)
        return pages[url] if url in pages else page([entry(1, 2), entry(2, 5)], "p2")

    with patch.object(APICalls, "get_with_ratelimit", side_effect=fake_get):
        listing = get_issue_listing("o", "r", START, {})
    assert [i["number"] for i in listing] == [1, 2, 3, 4]
    assert requested[1:] == ["p2", "p3"]


def test_listing_with_until_excludes_later_items_and_stops_paging():
    pages = {"p2": page([entry(3, 14), entry(4, 18)], "p3"), "p3": page([entry(5, 25)])}
    requested = []

    def fake_get(url, _header):
        requested.append(url)
        return pages[url] if url in pages else page([entry(1, 2), entry(2, 5)], "p2")

    with patch.object(APICalls, "get_with_ratelimit", side_effect=fake_get):
        listing = get_issue_listing("o", "r", START, {}, until=datetime(2023, 12, 15))
    assert [i["number"] for i in listing] == [1, 2, 3]  # il 4 è creato dopo until
    assert requested[1:] == ["p2"]  # p3 contiene solo elementi creati dopo until: non viene richiesta


def test_listing_until_keeps_item_created_exactly_at_until():
    with patch.object(APICalls, "get_with_ratelimit", return_value=page([entry(1, 15)])):
        listing = get_issue_listing("o", "r", START, {}, until=datetime(2023, 12, 15))
    assert [i["number"] for i in listing] == [1]


def test_listing_empty_when_repository_not_found():
    response = page([], status=404)
    response.raise_for_status = lambda: (_ for _ in ()).throw(HTTPError(response=response))
    response.reason = "Not Found"
    with patch.object(APICalls, "get_with_ratelimit", return_value=response):
        assert get_issue_listing("o", "r", START, {}) == []


@pytest.mark.parametrize("until", [None, datetime(2023, 12, 31)])
def test_listing_raises_on_server_error(until):
    response = page([], status=502)
    response.raise_for_status = lambda: (_ for _ in ()).throw(HTTPError(response=response))
    with patch.object(APICalls, "get_with_ratelimit", return_value=response):
        with pytest.raises(HTTPError):
            get_issue_listing("o", "r", START, {}, until=until)


def test_pulls_are_read_from_the_issues_listing_not_from_the_pulls_endpoint():
    requested = []

    def fake_pages_until(url, _header, _until):
        requested.append(url)
        return [] if "/comments" in url else [entry(7, 3, pull=True)]

    with patch.object(APICalls, "get_pages_until", side_effect=fake_pages_until), \
            patch.object(APICalls, "get_multiple_pages", return_value=[]):
        pulls = get_pulls_since("o", "r", START, "")
    assert len(pulls) == 1
    listing_urls = [u for u in requested if "/comments" not in u]
    assert len(listing_urls) == 1 and listing_urls[0].startswith(ISSUES_URL + "?")
    assert not any("/pulls?" in u for u in requested)
