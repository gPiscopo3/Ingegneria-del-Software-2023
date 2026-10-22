from datetime import datetime
from unittest.mock import patch

import pytest
from requests import HTTPError

from src.logic import APICalls
from src.logic.APICalls import (earlier_replies, graphql_earlier, graphql_earlier_replies, has_reply_in_range,
                                rest_earlier_replies, with_earlier_replies, get_issues_since, get_pulls_since)
from src.logic.DataManagement import get_communications_since

START = datetime(2023, 12, 1)
alice = {"id": 1, "login": "alice"}
bob = {"id": 2, "login": "bob"}
HEADER = {"Authorization": "Bearer t"}


def comment(number, date, user):
    return {"created_at": date, "user": user, "issue_url": f"https://api.github.com/repos/o/r/issues/{number}",
            "pull_request_url": f"https://api.github.com/repos/o/r/pulls/{number}"}


def communications_of(user):
    return {date: sorted(r.username for r in receivers) for date, receivers in user.communications.items()}


# --- scenari end-to-end (REST, senza token) ---------------------------------------------------------------------

def test_reply_in_range_to_comment_before_start_creates_edge():
    # PR aperta da alice in ottobre, commento di bob in ottobre, risposta di alice a dicembre: l'arco alice->bob
    # esiste anche se il commento di bob è precedente alla data di inizio
    pull = {"number": 5, "created_at": "2023-10-01T10:00:00Z", "user": alice, "pull_request": {}}
    bob_comment = comment(5, "2023-10-20T10:00:00Z", bob)
    alice_reply = comment(5, "2023-12-10T10:00:00Z", alice)

    def fake_pages(url, _header):
        return [bob_comment, alice_reply] if "/issues/5/comments" in url else []

    with patch.object(APICalls, "get_issue_listing", return_value=[pull]), \
            patch.object(APICalls, "get_pages_until", return_value=[alice_reply]), \
            patch.object(APICalls, "get_multiple_pages", side_effect=fake_pages):
        users = get_communications_since("o", "r", START, "")
    assert communications_of(users[1]) == {datetime(2023, 12, 10, 10): ["bob"]}
    assert communications_of(users[2]) == {}  # il commento di ottobre è fuori intervallo


def test_issue_with_only_earlier_reply_from_other_user_counts_as_communication():
    # il commento di bob (precedente all'inizio) è l'unico di un altro utente: senza di esso l'issue sembrerebbe
    # senza comunicazione e la risposta di alice a dicembre andrebbe persa
    issue = {"number": 8, "created_at": "2023-10-01T10:00:00Z", "user": alice}
    bob_comment = comment(8, "2023-10-20T10:00:00Z", bob)
    alice_reply = comment(8, "2023-12-05T10:00:00Z", alice)
    carol = {"id": 3, "login": "carol"}
    carol_comment = comment(8, "2023-12-06T10:00:00Z", carol)

    def fake_pages(url, _header):
        return [bob_comment, alice_reply, carol_comment] if "/issues/8/comments" in url else []

    with patch.object(APICalls, "get_issue_listing", return_value=[issue]), \
            patch.object(APICalls, "get_pages_until", return_value=[alice_reply, carol_comment]), \
            patch.object(APICalls, "get_multiple_pages", side_effect=fake_pages):
        users = get_communications_since("o", "r", START, "")
    assert communications_of(users[1]) == {datetime(2023, 12, 5, 10): ["bob"]}
    assert communications_of(users[3]) == {datetime(2023, 12, 6, 10): ["alice", "bob"]}


# --- quali elementi chiedono i commenti precedenti ---------------------------------------------------------------

def test_has_reply_in_range():
    replies = [(datetime(2023, 10, 1), alice), (datetime(2023, 12, 10), bob)]
    assert has_reply_in_range(replies, START)
    assert has_reply_in_range(replies, START, datetime(2023, 12, 10))  # estremo incluso
    assert not has_reply_in_range(replies, START, datetime(2023, 12, 9))
    assert not has_reply_in_range(replies[:1], START)
    assert has_reply_in_range([(START, alice)], START)  # inizio incluso


def test_only_old_items_with_a_reply_in_range_ask_for_earlier_comments():
    old_active = [(datetime(2023, 10, 1), alice), (datetime(2023, 12, 3), bob)]
    old_inactive = [(datetime(2023, 10, 1), alice)]  # aggiornata (es. etichetta) ma senza risposte nel periodo
    new = [(datetime(2023, 12, 2), alice), (datetime(2023, 12, 3), bob)]
    lists = [old_active, old_inactive, new]
    with patch.object(APICalls, "earlier_replies", return_value={}) as earlier:
        with_earlier_replies("o", "r", [1, 2, 3], lists, set(), START, None, HEADER)
    assert earlier.call_args.args[2] == [1]


def test_earlier_replies_are_added_to_the_right_item():
    lists = [[(datetime(2023, 10, 1), alice), (datetime(2023, 12, 3), alice)],
             [(datetime(2023, 10, 2), bob), (datetime(2023, 12, 4), bob)]]
    earlier = {2: [(datetime(2023, 10, 5), alice)]}
    with patch.object(APICalls, "earlier_replies", return_value=earlier):
        with_earlier_replies("o", "r", [1, 2], lists, set(), START, None, HEADER)
    assert len(lists[0]) == 2
    assert (datetime(2023, 10, 5), alice) in lists[1] and len(lists[1]) == 3


def test_get_issues_since_does_not_fetch_earlier_comments_for_new_issues():
    issue = {"number": 1, "created_at": "2023-12-02T00:00:00Z", "user": alice}
    with patch.object(APICalls, "get_issue_listing", return_value=[issue]), \
            patch.object(APICalls, "earlier_replies", return_value={}) as earlier:
        get_issues_since("o", "r", START, "", issue_comments={1: [comment(1, "2023-12-03T00:00:00Z", bob)]})
    assert earlier.call_args.args[2] == []


def test_get_pulls_since_asks_earlier_comments_for_old_pull_with_review_activity():
    # nessun commento nel periodo, ma una review sì: anche così la PR vecchia ha risposte nel periodo
    pull = {"number": 9, "created_at": "2023-10-01T00:00:00Z", "user": alice, "pull_request": {}}
    review = (datetime(2023, 12, 5), bob)
    with patch.object(APICalls, "get_issue_listing", return_value=[pull]), \
            patch.object(APICalls, "get_comments_by_number", return_value={}), \
            patch.object(APICalls, "pull_activity", return_value={9: [review]}), \
            patch.object(APICalls, "earlier_replies", return_value={9: [(datetime(2023, 10, 2), bob)]}) as earlier:
        pulls = get_pulls_since("o", "r", START, "")
    assert earlier.call_args.args[2] == [9] and earlier.call_args.args[3] == {9}
    assert [date for date, _ in pulls[0]] == [datetime(2023, 10, 1), datetime(2023, 10, 2), datetime(2023, 12, 5)]


# --- senza token: REST --------------------------------------------------------------------------------------------

def test_rest_earlier_replies_issue_uses_only_issue_comments_before_start():
    requested = []

    def fake_pages(url, _header):
        requested.append(url)
        return [comment(5, "2023-10-20T10:00:00Z", bob), comment(5, "2023-12-10T10:00:00Z", alice)]

    with patch.object(APICalls, "get_multiple_pages", side_effect=fake_pages):
        replies = rest_earlier_replies("o", "r", 5, False, START, {})
    assert replies == [(datetime(2023, 10, 20, 10), bob)]
    assert requested == ["https://api.github.com/repos/o/r/issues/5/comments?per_page=100"]


def test_rest_earlier_replies_pull_adds_review_comments():
    requested = []

    def fake_pages(url, _header):
        requested.append(url)
        return [comment(5, "2023-10-20T10:00:00Z", bob if "/pulls/" in url else alice)]

    with patch.object(APICalls, "get_multiple_pages", side_effect=fake_pages):
        replies = rest_earlier_replies("o", "r", 5, True, START, {})
    assert sorted(user["login"] for _, user in replies) == ["alice", "bob"]
    assert requested == ["https://api.github.com/repos/o/r/issues/5/comments?per_page=100",
                         "https://api.github.com/repos/o/r/pulls/5/comments?per_page=100"]


def test_earlier_replies_without_token_use_rest_per_item():
    with patch.object(APICalls, "post_graphql", side_effect=AssertionError("GraphQL senza token")), \
            patch.object(APICalls, "get_multiple_pages",
                         side_effect=lambda url, _h: [comment(0, "2023-10-20T10:00:00Z", bob)]):
        result = earlier_replies("o", "r", [3, 4], {4}, START, {})
    assert result == {3: [(datetime(2023, 10, 20, 10), bob)], 4: [(datetime(2023, 10, 20, 10), bob)] * 2}


def test_earlier_replies_without_numbers_does_nothing():
    with patch.object(APICalls, "post_graphql", side_effect=AssertionError("richiesta inattesa")), \
            patch.object(APICalls, "get_multiple_pages", side_effect=AssertionError("richiesta inattesa")):
        assert earlier_replies("o", "r", [], set(), START, HEADER) == {}


# --- con token: GraphQL -------------------------------------------------------------------------------------------

def node(date, login="bob", database_id=2, typename="User"):
    return {"createdAt": date, "author": {"__typename": typename, "login": login, "databaseId": database_id}}


def connection(*nodes, more=False):
    return {"pageInfo": {"hasNextPage": more}, "nodes": list(nodes)}


def test_earlier_replies_with_token_groups_numbers_in_few_queries():
    queries = []

    def fake_post(query, _variables, _header):
        queries.append(query)
        return {"data": {"repository": {}}}  # nessun elemento restituito: ripiego REST per tutti

    numbers = list(range(1, 46))
    with patch.object(APICalls, "post_graphql", side_effect=fake_post), \
            patch.object(APICalls, "get_multiple_pages", return_value=[]):
        result = earlier_replies("o", "r", numbers, set(), START, HEADER)
    assert len(queries) == 3  # 20 + 20 + 5 elementi
    assert sorted(result) == numbers
    assert all(f"n{n}: issueOrPullRequest(number: {n})" in queries[0] for n in range(1, 21))


def test_graphql_earlier_replies_uses_graphql_data_without_rest():
    repository = {"n1": {"comments": connection(node("2023-10-20T10:00:00Z"), node("2023-12-02T10:00:00Z"))},
                  "n2": {"comments": connection(node("2023-10-21T10:00:00Z", "alice", 1)),
                         "reviewThreads": connection(*[{"comments": connection(node("2023-10-22T10:00:00Z"))}])}}
    with patch.object(APICalls, "post_graphql", return_value={"data": {"repository": repository}}), \
            patch.object(APICalls, "get_multiple_pages", side_effect=AssertionError("REST non necessario")):
        result = graphql_earlier_replies("o", "r", [1, 2], {2}, START, HEADER)
    assert result[1] == [(datetime(2023, 10, 20, 10), bob)]  # il commento di dicembre non è "precedente"
    assert result[2] == [(datetime(2023, 10, 21, 10), alice), (datetime(2023, 10, 22, 10), bob)]


def test_graphql_earlier_replies_falls_back_to_rest_for_missing_or_incomplete_items():
    repository = {"n1": {"comments": connection(node("2023-10-20T10:00:00Z"))},  # completo
                  "n3": {"comments": connection(node("2023-10-20T10:00:00Z"), more=True)}}  # incompleto
    requested = []

    def fake_pages(url, _header):
        requested.append(url)
        return [comment(0, "2023-10-19T10:00:00Z", alice)]

    with patch.object(APICalls, "post_graphql", return_value={"data": {"repository": repository}}), \
            patch.object(APICalls, "get_multiple_pages", side_effect=fake_pages):
        result = graphql_earlier_replies("o", "r", [1, 2, 3], set(), START, HEADER)  # il 2 non è restituito
    assert result[1] == [(datetime(2023, 10, 20, 10), bob)]
    assert result[2] == result[3] == [(datetime(2023, 10, 19, 10), alice)]
    assert sorted(requested) == ["https://api.github.com/repos/o/r/issues/2/comments?per_page=100",
                                 "https://api.github.com/repos/o/r/issues/3/comments?per_page=100"]


def test_graphql_earlier_replies_falls_back_to_rest_when_the_request_fails():
    with patch.object(APICalls, "post_graphql", side_effect=HTTPError("502")), \
            patch.object(APICalls, "get_multiple_pages",
                         return_value=[comment(0, "2023-10-19T10:00:00Z", alice)]) as pages:
        result = graphql_earlier_replies("o", "r", [1, 2], set(), START, HEADER)
    assert result == {1: [(datetime(2023, 10, 19, 10), alice)], 2: [(datetime(2023, 10, 19, 10), alice)]}
    assert pages.call_count == 2


def test_graphql_earlier_skips_deleted_accounts_and_marks_bots():
    item = {"comments": connection({"createdAt": "2023-10-01T00:00:00Z", "author": None},
                                   {"createdAt": "2023-10-02T00:00:00Z",
                                    "author": {"__typename": "Mannequin", "login": "m"}},  # senza databaseId
                                   node("2023-10-03T00:00:00Z", "dependabot", 49699333, "Bot"))}
    assert graphql_earlier(item, START) == [(datetime(2023, 10, 3), {"id": 49699333, "login": "dependabot[bot]"})]


def test_graphql_earlier_none_when_item_missing():
    assert graphql_earlier(None, START) is None


def test_graphql_earlier_completeness_of_comments():
    before = node("2023-10-20T10:00:00Z")
    after = node("2023-12-02T10:00:00Z")
    # altre pagine, ma l'ultimo commento ricevuto è già dopo l'inizio: quelli precedenti ci sono tutti
    assert graphql_earlier({"comments": connection(before, after, more=True)}, START) == [(datetime(2023, 10, 20, 10), bob)]
    # altre pagine e l'ultimo ricevuto è ancora precedente: potrebbero mancarne
    assert graphql_earlier({"comments": connection(before, more=True)}, START) is None
    assert graphql_earlier({"comments": connection(more=True)}, START) is None


def test_graphql_earlier_none_when_review_threads_are_incomplete():
    thread = {"comments": connection(node("2023-10-22T10:00:00Z"))}
    assert graphql_earlier({"comments": connection(), "reviewThreads": connection(thread, more=True)}, START) is None
    long_thread = {"comments": connection(node("2023-10-22T10:00:00Z"), more=True)}
    assert graphql_earlier({"comments": connection(), "reviewThreads": connection(long_thread)}, START) is None
    assert graphql_earlier({"comments": connection(), "reviewThreads": connection(thread)}, START) == \
        [(datetime(2023, 10, 22, 10), bob)]


@pytest.mark.parametrize("login, kind", [("dependabot", "Bot"), ("bob", "User")])
def test_graphql_earlier_keeps_author_id_and_login(login, kind):
    item = {"comments": connection(node("2023-10-01T00:00:00Z", login, 77, kind))}
    [(_, author)] = graphql_earlier(item, START)
    assert author == {"id": 77, "login": login + ("[bot]" if kind == "Bot" else "")}
