from datetime import datetime
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import requests
from requests import HTTPError

from src.logic import APICalls
from src.logic.APICalls import *
from test.src.logic.APICalls_parallel_test import FakeResponse

DATE = datetime(2023, 11, 1)
OWNER = "fullmoonlullaby"
REPO = "test"
T = datetime(2023, 12, 5, 10, 0, 0)
T_STR = "2023-12-05T10:00:00Z"


def user(n):
    return {"id": n, "login": f"u{n}"}


def response_with(status, headers=None):
    return SimpleNamespace(status_code=status, headers=headers or {})


def assert_replies_shape(results):
    # ogni issue/PR: lista di (data, autore) ordinata per data, con l'apertura per prima
    for replies in results:
        assert replies
        assert all(isinstance(date, datetime) and {"id", "login"} <= set(author) for date, author in replies)
        dates = [date for date, _ in replies]
        assert dates == sorted(dates)


# *****************************************************************************************************
# test offline: nessuna chiamata a GitHub


def test_get_issues_owner_none():
    with pytest.raises(TypeError):
        get_issues_since(None, REPO, DATE, "")


def test_get_issues_repo_none():
    with pytest.raises(TypeError):
        get_issues_since(OWNER, None, DATE, "")


def test_get_issues_date_none():
    with pytest.raises(AttributeError):
        get_issues_since(OWNER, REPO, None, "")


def test_get_issues_token_none():
    with pytest.raises(TypeError):
        get_issues_since(OWNER, REPO, DATE, None)


def test_get_pulls_owner_none():
    with pytest.raises(TypeError):
        get_pulls_since(None, REPO, DATE, "")


def test_get_pulls_repo_none():
    with pytest.raises(TypeError):
        get_pulls_since(OWNER, None, DATE, "")


def test_get_pulls_date_none():
    with pytest.raises(TypeError):
        get_pulls_since(OWNER, REPO, None, "")


def test_get_pulls_token_none():
    with pytest.raises(TypeError):
        get_pulls_since(OWNER, REPO, DATE, None)


def test_get_commits_owner_none():
    with pytest.raises(TypeError):
        get_commits_since(None, REPO, DATE, "")


def test_get_commits_repo_none():
    with pytest.raises(TypeError):
        get_commits_since(OWNER, None, DATE, "")


def test_get_commits_token_none():
    with pytest.raises(TypeError):
        get_commits_since(OWNER, REPO, DATE, None)


def test_get_multiple_pages_bad_url():
    with pytest.raises(ValueError):
        get_multiple_pages("bad url", {})


def test_get_multiple_pages_none_url():
    assert get_multiple_pages(None, {}) == []


def test_get_multiple_pages_bad_header():
    with pytest.raises(AttributeError):
        get_multiple_pages("https://api.github.com/repos/fullmoonlullaby/test/issues", "wrong type")


def test_get_with_ratelimit_bad_url():
    with pytest.raises(ValueError):
        get_with_ratelimit("Bad url", {})


def test_get_with_ratelimit_none():
    with pytest.raises(ValueError):
        get_with_ratelimit(None, {})


def test_get_with_ratelimit_bad_header():
    with pytest.raises(AttributeError):
        get_with_ratelimit("https://api.github.com/repos/boh/test/issues", "wrong type")


def test_get_rate_limit_token_none():
    with pytest.raises(TypeError):
        get_rate_limit(None)


def test_reformat_response_wrong_type():
    with pytest.raises(TypeError):
        reformat_response("wrong type")


def test_reformat_response_all_kinds():
    items = [
        {"created_at": T_STR, "user": user(1)},  # commento
        {"created_at": T_STR, "user": None},  # utente cancellato: scartato
        {"submitted_at": "2023-12-06T10:00:00Z", "user": user(2)},  # review
        {"submitted_at": None, "user": user(2)},  # review in sospeso: scartata
        {"submitted_at": "2023-12-06T10:00:00Z", "user": None},
        {"commit": {"committer": {"date": "2023-12-07T10:00:00Z"}}, "author": user(3)},  # commit della PR
        {"commit": {"committer": {"date": "2023-12-07T10:00:00Z"}}, "author": None},  # autore senza account
    ]
    assert reformat_response(items) == [(T, user(1)), (datetime(2023, 12, 6, 10), user(2)),
                                        (datetime(2023, 12, 7, 10), user(3))]


def test_reformat_response_same_second_keeps_all():
    items = [{"created_at": T_STR, "user": user(1)}, {"created_at": T_STR, "user": user(2)}]
    assert reformat_response(items) == [(T, user(1)), (T, user(2))]


def test_get_issues_same_second_replies():
    # apertura e due commenti nello stesso secondo: nessuno va perso e l'autore della issue resta primo
    issue = {"number": 1, "created_at": T_STR, "user": user(1)}
    comments = {1: [{"created_at": T_STR, "user": user(2)}, {"created_at": T_STR, "user": user(3)}]}
    with patch.object(APICalls, "get_pages_until", return_value=[issue, {"number": 2, "pull_request": {}}]):
        issues = get_issues_since(OWNER, REPO, DATE, "", issue_comments=comments)
    assert issues == [[(T, user(1)), (T, user(2)), (T, user(3))]]  # le pull request sono escluse


def test_get_pulls_same_second_replies():
    pull = {"number": 7, "created_at": T_STR, "user": user(1), "pull_request": {}}
    commit_item = {"commit": {"committer": {"date": T_STR}}, "author": user(3)}

    def fake_pages(url, header):
        if "/pulls/7/commits" in url:
            return [commit_item]
        return []

    with patch.object(APICalls, "get_issue_listing", return_value=[pull]),             patch.object(APICalls, "get_multiple_pages", side_effect=fake_pages):
        results = get_pulls_since("o", "r", DATE, "", issue_comments={7: [{"created_at": T_STR, "user": user(2)}]})
    assert results == [[(T, user(1)), (T, user(2)), (T, user(3))]]


def test_get_pulls_includes_pull_created_before_start_with_activity():
    # PR aperta prima di DATE ma con un commento dopo: come per le issue, conta
    old_pull = {"number": 4, "created_at": "2023-10-01T00:00:00Z", "user": user(1), "pull_request": {}}
    comment = {"created_at": "2023-11-15T00:00:00Z", "user": user(2)}
    with patch.object(APICalls, "get_issue_listing", return_value=[old_pull]),             patch.object(APICalls, "get_multiple_pages", return_value=[]):
        results = get_pulls_since("o", "r", DATE, "", issue_comments={4: [comment]})
    assert [author["id"] for _, author in results[0]] == [1, 2]
    assert results[0][1][0] == datetime(2023, 11, 15)


def test_pulls_and_issues_are_split_from_the_same_listing():
    listing = [{"number": 1, "created_at": T_STR, "user": user(1)},
               {"number": 2, "created_at": T_STR, "user": user(2), "pull_request": {}}]
    with patch.object(APICalls, "get_issue_listing", side_effect=AssertionError("elenco già scaricato")),             patch.object(APICalls, "get_multiple_pages", return_value=[]):
        issues = get_issues_since(OWNER, REPO, DATE, "", issue_comments={}, listing=listing)
        pulls = get_pulls_since(OWNER, REPO, DATE, "", issue_comments={}, listing=listing)
    assert issues == [[(T, user(1))]]
    assert pulls == [[(T, user(2))]]


@pytest.mark.parametrize("status, headers, expected", [
    (200, {}, None),
    (403, {"Retry-After": "30"}, 30),  # limite secondario
    (429, {"Retry-After": "5"}, 5),
    (429, {}, 60),  # 429 senza indicazioni
    (403, {}, None),  # 403 per permessi: non si riprova
    (403, {"X-RateLimit-Remaining": "1"}, None),
], ids=["ok", "retry_after_403", "retry_after_429", "429_default", "403_permissions", "403_quota_left"])
def test_seconds_to_wait(status, headers, expected):
    assert seconds_to_wait(response_with(status, headers)) == expected


def test_seconds_to_wait_primary_limit():
    with patch.object(APICalls.time, "time", return_value=1000):
        wait_s = seconds_to_wait(response_with(403, {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1100"}))
    assert wait_s == 101
    with patch.object(APICalls.time, "time", return_value=2000):  # reset già passato: si riprova subito
        assert seconds_to_wait(response_with(403, {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1100"})) == 1


class ScriptedSession:
    # sessione finta: restituisce (o solleva) un elemento della lista a ogni richiesta
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def get(self, *args, **kwargs):
        outcome = self.outcomes[min(self.calls, len(self.outcomes) - 1)]
        self.calls += 1
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def scripted(outcomes):
    session = ScriptedSession(outcomes)
    patches = [patch.object(APICalls, "_session", lambda: session),
               patch.object(APICalls.cancel_event, "wait", return_value=False),
               patch.object(APICalls._throttle, "pause")]
    return session, patches


def test_get_with_ratelimit_network_errors_exhausted():
    session, patches = scripted([requests.ConnectionError("rete assente")])
    with patches[0], patches[1], patches[2]:
        with pytest.raises(requests.ConnectionError):
            get_with_ratelimit("https://api.github.com/x", {})
    assert session.calls == APICalls.MAX_RETRIES


def test_get_with_ratelimit_always_limited_returns_last_response():
    limited = response_with(429, {"Retry-After": "1"})
    session, patches = scripted([limited])
    with patches[0], patches[1], patches[2] as pause:
        assert get_with_ratelimit("https://api.github.com/x", {}) is limited
    assert session.calls == APICalls.MAX_RETRIES
    assert pause.call_count == APICalls.MAX_RETRIES


def test_get_with_ratelimit_retries_after_limit():
    ok = response_with(200)
    session, patches = scripted([response_with(429, {"Retry-After": "1"}), ok])
    with patches[0], patches[1], patches[2]:
        assert get_with_ratelimit("https://api.github.com/x", {}) is ok
    assert session.calls == 2


def test_get_commit_paginates_files():
    pages = {"c": FakeResponse({"sha": "c", "files": [{"filename": "a"}]}, "c2"),
             "c2": FakeResponse({"files": [{"filename": "b"}]}, "c3"),
             "c3": FakeResponse({"files": [{"filename": "c"}]})}
    with patch.object(APICalls, "get_with_ratelimit", side_effect=lambda url, header: pages[url]):
        commit = get_commit("c", {})
    assert [f["filename"] for f in commit["files"]] == ["a", "b", "c"]


def test_get_commits_since_skips_commit_with_http_error():
    def fake_pages(url, header):
        if "/branches" in url:
            return [{"commit": {"sha": "b1"}}]
        return [{"sha": "ok", "url": "u-ok"}, {"sha": "ko", "url": "u-ko"}]

    def fake_commit(url, header):
        if url == "u-ko":
            raise HTTPError(response=SimpleNamespace(text="errore simulato"))
        return {"url": url}

    with patch.object(APICalls, "get_multiple_pages", side_effect=fake_pages), \
            patch.object(APICalls, "get_commit", side_effect=fake_commit):
        assert get_commits_since(OWNER, REPO, DATE, "") == [{"url": "u-ok"}]


# *****************************************************************************************************
# integrazione: chiamate reali a GitHub


@pytest.mark.integration
def test_get_issues_ok(token):
    issues = get_issues_since(OWNER, REPO, DATE, token)
    assert len(issues) > 0
    assert_replies_shape(issues)


@pytest.mark.integration
def test_get_issues_owner_nonexistent(token, http_statuses):
    assert get_issues_since("", REPO, DATE, token) == []
    assert set(http_statuses) == {404}


@pytest.mark.integration
def test_get_issues_repo_nonexistent(token, http_statuses):
    assert get_issues_since(OWNER, "", DATE, token) == []
    assert set(http_statuses) == {404}


@pytest.mark.integration
def test_get_issues_date_now(token, http_statuses):
    assert get_issues_since(OWNER, REPO, datetime.now(), token) == []
    assert set(http_statuses) == {200}


@pytest.mark.integration
def test_get_issues_token_nonexistent(http_statuses):
    assert get_issues_since(OWNER, REPO, DATE, "token_sbagliato") == []
    assert set(http_statuses) == {401}


@pytest.mark.integration
def test_get_pulls_ok(token):
    pulls = get_pulls_since(OWNER, REPO, DATE, token)
    assert len(pulls) > 0
    assert_replies_shape(pulls)
    # ogni PR è stata aperta dopo DATE oppure ha almeno una risposta dopo DATE
    assert all(any(date >= DATE for date, _ in replies) for replies in pulls)


@pytest.mark.integration
def test_get_pulls_owner_nonexistent(token, http_statuses):
    assert get_pulls_since("", REPO, DATE, token) == []
    assert set(http_statuses) == {404}


@pytest.mark.integration
def test_get_pulls_repo_nonexistent(token, http_statuses):
    assert get_pulls_since(OWNER, "", DATE, token) == []
    assert set(http_statuses) == {404}


@pytest.mark.integration
def test_get_pulls_token_nonexistent(http_statuses):
    assert get_pulls_since(OWNER, REPO, DATE, "token_sbagliato") == []
    assert set(http_statuses) == {401}


@pytest.mark.integration
def test_get_commits_ok(token):
    commits = get_commits_since(OWNER, REPO, DATE, token)
    assert len(commits) > 0
    for commit in commits:
        assert {"sha", "commit", "files"} <= set(commit)
        assert datetime.strptime(commit["commit"]["committer"]["date"], DATE_FORMAT) >= DATE
    assert len({c["sha"] for c in commits}) == len(commits)  # nessun commit ripetuto tra i branch


@pytest.mark.integration
def test_get_commits_owner_nonexistent(token, http_statuses):
    assert get_commits_since("", REPO, DATE, token) == []
    assert set(http_statuses) == {404}


@pytest.mark.integration
def test_get_commits_repo_nonexistent(token, http_statuses):
    assert get_commits_since(OWNER, "", DATE, token) == []
    assert set(http_statuses) == {404}


@pytest.mark.integration
def test_get_commits_date_none(token):
    with pytest.raises(AttributeError):
        get_commits_since(OWNER, REPO, None, token)


@pytest.mark.integration
def test_get_commits_date_now(token):
    assert get_commits_since(OWNER, REPO, datetime.now(), token) == []


@pytest.mark.integration
def test_get_commits_token_nonexistent(http_statuses):
    assert get_commits_since(OWNER, REPO, DATE, "token_sbagliato") == []
    assert set(http_statuses) == {401}


@pytest.mark.integration
def test_get_multiple_pages_ok(token, http_statuses):
    results = get_multiple_pages("https://api.github.com/repos/fullmoonlullaby/test/issues?state=all&per_page=1",
                                 {"Authorization": "Bearer " + token})
    assert len(http_statuses) > 1  # più pagine lette seguendo l'header Link
    assert len(results) == len(http_statuses)  # un elemento per pagina
    assert set(http_statuses) == {200}


@pytest.mark.integration
def test_get_multiple_pages_not_found(token, http_statuses):
    assert get_multiple_pages("https://api.github.com/repos/non_existent/test/issues?per_page=1",
                              {"Authorization": "Bearer " + token}) == []
    assert http_statuses == [404]


@pytest.mark.integration
def test_get_with_ratelimit_ok():
    results = get_with_ratelimit("https://api.github.com/repos/fullmoonlullaby/test/issues", {})
    assert results.status_code == 200


@pytest.mark.integration
def test_get_with_ratelimit_not_found():
    results = get_with_ratelimit("https://api.github.com/repos/not_existent/test/issues", {})
    assert results.status_code == 404


@pytest.mark.integration
def test_get_rate_limit_token_ok(token):
    rate = get_rate_limit(token)
    assert rate is not None
    assert 0 <= rate["remaining"] <= rate["limit"]
    assert rate["reset"] > 0


@pytest.mark.integration
def test_get_rate_limit_no_token():
    rate = get_rate_limit("")
    assert rate["limit"] == 60


@pytest.mark.integration
def test_get_rate_limit_token_nonexistent():
    assert get_rate_limit("token_sbagliato") is None
