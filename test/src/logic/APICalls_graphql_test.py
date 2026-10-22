import re
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from requests import HTTPError

from src.logic import APICalls
from src.logic.APICalls import graphql_replies, graphql_pull_activity, pull_activity, post_graphql

OWNER = "fullmoonlullaby"
REPO = "test"
HEADER = {"Authorization": "Bearer abc"}
DATE = datetime(2023, 11, 1)


@pytest.fixture(autouse=True)
def reset_cancel_event():
    APICalls.cancel_event.clear()
    yield
    APICalls.cancel_event.clear()


def empty_pull():
    return {"reviews": {"pageInfo": {"hasNextPage": False}, "nodes": []},
            "commits": {"pageInfo": {"hasNextPage": False}, "nodes": []}}


def review(login, user_id, submitted="2023-12-05T10:00:00Z", typename="User"):
    return {"submittedAt": submitted, "author": {"__typename": typename, "login": login, "databaseId": user_id}}


def commit(date, user=None, email=None):
    return {"commit": {"committedDate": date, "author": {"email": email, "user": user}}}


def fake_post_graphql(query, variables, header):
    # una PR vuota per ogni alias "pN:" della query
    numbers = re.findall(r"p(\d+): pullRequest", query)
    return {"data": {"repository": {f"p{n}": empty_pull() for n in numbers}}}


# ---------------------------------------------------------------------------------------------------------
# conversione della risposta GraphQL nel formato delle API REST


def test_graphql_replies_all_kinds():
    pull = empty_pull()
    pull["reviews"]["nodes"] = [
        review("alice", 1),
        review("dependabot", 49, "2023-12-05T11:00:00Z", "Bot"),  # i bot hanno il suffisso [bot] come in REST
        review("bob", 2, submitted=None),  # review in bozza: ignorata
        {"submittedAt": "2023-12-05T12:00:00Z", "author": None},  # account cancellato: ignorata
        {"submittedAt": "2023-12-05T12:30:00Z", "author": {"__typename": "Mannequin", "login": "m"}},  # senza id
    ]
    pull["commits"]["nodes"] = [
        commit("2023-12-06T10:00:00Z", user={"databaseId": 3, "login": "carol"}),
        commit("2023-12-06T11:00:00Z", email="7+dave@users.noreply.github.com"),  # utente non collegato: noreply
        commit("2023-12-06T12:00:00Z", email="eve@example.com"),  # nessun account GitHub: ignorato
        {"commit": {"committedDate": "2023-12-06T13:00:00Z", "author": None}},
    ]
    assert graphql_replies(pull) == [
        (datetime(2023, 12, 5, 10), {"id": 1, "login": "alice"}),
        (datetime(2023, 12, 5, 11), {"id": 49, "login": "dependabot[bot]"}),
        (datetime(2023, 12, 6, 10), {"id": 3, "login": "carol"}),
        (datetime(2023, 12, 6, 11), {"id": 7, "login": "dave"}),
    ]


@pytest.mark.parametrize("field", ["reviews", "commits"])
def test_graphql_replies_incomplete_pull_is_none(field):
    pull = empty_pull()
    pull[field]["pageInfo"]["hasNextPage"] = True  # più di 100 elementi: serve REST
    assert graphql_replies(pull) is None


def test_graphql_replies_missing_pull_is_none():
    assert graphql_replies(None) is None


# ---------------------------------------------------------------------------------------------------------
# quante richieste e di che tipo


def test_pull_activity_with_token_uses_one_query_every_50_pulls():
    numbers = list(range(1, 121))
    with patch.object(APICalls, "post_graphql", side_effect=fake_post_graphql) as post, \
            patch.object(APICalls, "get_multiple_pages", side_effect=AssertionError("REST non necessario")):
        activity = pull_activity(OWNER, REPO, numbers, HEADER)
    assert post.call_count == 3
    assert sorted(len(re.findall(r"pullRequest\(number", call.args[0])) for call in post.call_args_list) == [20, 50, 50]
    assert activity == {n: [] for n in numbers}


def test_pull_activity_without_token_uses_rest_only():
    with patch.object(APICalls, "post_graphql", side_effect=AssertionError("GraphQL richiede il token")), \
            patch.object(APICalls, "get_multiple_pages", return_value=[]) as pages:
        activity = pull_activity(OWNER, REPO, [4, 5], {})
    assert activity == {4: [], 5: []}
    urls = sorted(call.args[0] for call in pages.call_args_list)
    assert urls == sorted(f"{APICalls.BASE_URL}{OWNER}/{REPO}/pulls/{n}/{kind}?per_page=100"
                          for n in (4, 5) for kind in ("reviews", "commits"))


def test_pull_activity_progress_counts_pulls():
    calls = []
    with patch.object(APICalls, "post_graphql", side_effect=fake_post_graphql):
        pull_activity(OWNER, REPO, list(range(1, 121)), HEADER, lambda label, done, total: calls.append((done, total)))
    assert calls[-1] == (120, 120)
    assert all(total == 120 and 0 < done <= 120 for done, total in calls)


# ---------------------------------------------------------------------------------------------------------
# ritorno a REST


def test_only_incomplete_pulls_fall_back_to_rest():
    def post(query, variables, header):
        pulls = {"p1": empty_pull(), "p2": empty_pull(), "p3": None}  # la 3 non è stata restituita
        pulls["p1"]["reviews"]["nodes"] = [review("alice", 1)]
        pulls["p2"]["commits"]["pageInfo"]["hasNextPage"] = True  # più di 100 commit
        return {"data": {"repository": pulls}, "errors": [{"type": "NOT_FOUND"}]}

    rest = {2: [(datetime(2023, 12, 6), {"id": 2, "login": "bob"})], 3: []}
    with patch.object(APICalls, "post_graphql", side_effect=post), \
            patch.object(APICalls, "rest_pull_replies",
                         side_effect=lambda owner, repo, number, header: rest[number]) as fallback:
        activity = graphql_pull_activity(OWNER, REPO, [1, 2, 3], HEADER)
    assert [call.args[2] for call in fallback.call_args_list] == [2, 3]
    assert activity == {1: [(datetime(2023, 12, 5, 10), {"id": 1, "login": "alice"})], 2: rest[2], 3: []}


@pytest.mark.parametrize("failure", [HTTPError("502"), None], ids=["http_error", "no_data"])
def test_failed_query_falls_back_to_rest_for_the_whole_batch(failure):
    def post(query, variables, header):
        if failure is not None:
            raise failure
        return {"data": None, "errors": [{"type": "INTERNAL"}]}

    with patch.object(APICalls, "post_graphql", side_effect=post), \
            patch.object(APICalls, "rest_pull_replies", return_value=[]) as fallback:
        activity = graphql_pull_activity(OWNER, REPO, [1, 2, 3], HEADER)
    assert [call.args[2] for call in fallback.call_args_list] == [1, 2, 3]
    assert activity == {1: [], 2: [], 3: []}


# ---------------------------------------------------------------------------------------------------------
# richiesta HTTP, rate limit


def graphql_response(body, headers=None):
    response = MagicMock(status_code=200, headers=headers or {})
    response.json.return_value = body
    return response


def test_request_with_payload_is_a_post_with_json():
    session = MagicMock()
    session.post.return_value = graphql_response({"data": {}})
    with patch.object(APICalls, "_session", return_value=session):
        body = post_graphql("query { x }", {"owner": "o"}, HEADER)
    assert body == {"data": {}}
    session.get.assert_not_called()
    _, kwargs = session.post.call_args
    assert session.post.call_args.args == (APICalls.GRAPHQL_URL,)
    assert kwargs["json"] == {"query": "query { x }", "variables": {"owner": "o"}}
    assert kwargs["headers"]["Authorization"] == "Bearer abc"


def test_post_graphql_waits_for_reset_on_rate_limited_error():
    limited = graphql_response({"errors": [{"type": "RATE_LIMITED"}]},
                               {"X-RateLimit-Reset": str(int(datetime.now().timestamp()) + 30)})
    ok = graphql_response({"data": {"repository": {}}})
    waits = []
    with patch.object(APICalls, "_request_with_ratelimit", side_effect=[limited, ok]) as request, \
            patch.object(APICalls.cancel_event, "wait", side_effect=lambda seconds: waits.append(seconds) or False), \
            patch.object(APICalls._throttle, "pause") as pause:
        body = post_graphql("q", {}, HEADER)
    assert body == {"data": {"repository": {}}}
    assert request.call_count == 2
    assert len(waits) == 1 and 30 <= waits[0] <= 32  # fino al rinnovo della quota
    pause.assert_called_once_with(waits[0])


def test_post_graphql_cancelled_while_waiting():
    limited = graphql_response({"errors": [{"type": "RATE_LIMITED"}]}, {"X-RateLimit-Reset": "0"})
    with patch.object(APICalls, "_request_with_ratelimit", return_value=limited), \
            patch.object(APICalls.cancel_event, "wait", return_value=True), \
            patch.object(APICalls._throttle, "pause"):
        with pytest.raises(APICalls.DownloadCancelled):
            post_graphql("q", {}, HEADER)


def test_graphql_headers_do_not_change_displayed_rest_quota():
    APICalls.last_rate_limit.clear()
    APICalls.update_last_rate_limit(MagicMock(headers={"X-RateLimit-Resource": "graphql", "X-RateLimit-Limit": "5000",
                                                        "X-RateLimit-Remaining": "4999", "X-RateLimit-Reset": "1"}))
    assert not APICalls.last_rate_limit
    APICalls.update_last_rate_limit(MagicMock(headers={"X-RateLimit-Resource": "core", "X-RateLimit-Limit": "5000",
                                                        "X-RateLimit-Remaining": "4000", "X-RateLimit-Reset": "1"}))
    assert APICalls.last_rate_limit["remaining"] == 4000
    APICalls.last_rate_limit.clear()


# ---------------------------------------------------------------------------------------------------------
# integrazione: GraphQL e REST devono dare le stesse risposte


@pytest.mark.integration
def test_graphql_and_rest_give_same_replies(token):
    header = APICalls.build_header(token)
    listing = APICalls.get_issue_listing(OWNER, REPO, DATE, header)
    numbers = [item["number"] for item in listing if "pull_request" in item]
    assert numbers
    via_graphql = pull_activity(OWNER, REPO, numbers, header)
    for number in numbers:
        via_rest = APICalls.rest_pull_replies(OWNER, REPO, number, header)
        assert sorted((date, author["id"]) for date, author in via_graphql[number]) == \
               sorted((date, author["id"]) for date, author in via_rest)
