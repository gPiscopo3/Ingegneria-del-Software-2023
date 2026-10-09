from datetime import datetime
from unittest.mock import patch

from src.logic import APICalls
from src.logic.APICalls import created_before, get_comments_by_number
from src.logic.DataManagement import get_communications_since

START = datetime(2023, 12, 1)
alice = {"id": 1, "login": "alice"}
bob = {"id": 2, "login": "bob"}


def comment(number, date, user):
    return {"created_at": date, "user": user, "issue_url": f"https://api.github.com/repos/o/r/issues/{number}",
            "pull_request_url": f"https://api.github.com/repos/o/r/pulls/{number}"}


def communications_of(user):
    return {date: sorted(r.username for r in receivers) for date, receivers in user.communications.items()}


def test_created_before_selects_only_items_older_than_start():
    items = [{"number": 1, "created_at": "2023-11-30T23:59:59Z"},
             {"number": 2, "created_at": "2023-12-01T00:00:00Z"},
             {"number": 3, "created_at": "2024-01-01T00:00:00Z"}]
    assert created_before(items, START) == [1]


def test_old_issue_gets_comments_from_before_start():
    in_range = comment(5, "2023-12-10T10:00:00Z", alice)
    earlier = comment(5, "2023-10-20T10:00:00Z", bob)
    requested = []

    def fake_pages(url, _header):
        requested.append(url)
        return [earlier, in_range]

    with patch.object(APICalls, "get_pages_until", return_value=[in_range]), \
            patch.object(APICalls, "get_multiple_pages", side_effect=fake_pages):
        grouped = get_comments_by_number("o", "r", "issues", START, {}, earlier=[5])
    assert grouped == {5: [earlier, in_range]}
    assert requested == ["https://api.github.com/repos/o/r/issues/5/comments?per_page=100"]


def test_old_pull_review_comments_use_the_pulls_endpoint():
    earlier = comment(5, "2023-10-20T10:00:00Z", bob)
    requested = []

    def fake_pages(url, _header):
        requested.append(url)
        return [earlier]

    with patch.object(APICalls, "get_pages_until", return_value=[]), \
            patch.object(APICalls, "get_multiple_pages", side_effect=fake_pages):
        grouped = get_comments_by_number("o", "r", "pulls", START, {}, earlier=[5])
    assert grouped == {5: [earlier]}
    assert requested == ["https://api.github.com/repos/o/r/pulls/5/comments?per_page=100"]


def test_earlier_comments_respect_until():
    inside = comment(5, "2023-12-10T10:00:00Z", alice)
    after = comment(5, "2023-12-30T10:00:00Z", bob)
    with patch.object(APICalls, "get_pages_until", return_value=[inside]), \
            patch.object(APICalls, "get_multiple_pages", return_value=[inside, after]):
        grouped = get_comments_by_number("o", "r", "issues", START, {}, until=datetime(2023, 12, 20), earlier=[5])
    assert grouped == {5: [inside]}


def test_without_earlier_numbers_no_per_number_request():
    in_range = comment(6, "2023-12-10T10:00:00Z", alice)
    with patch.object(APICalls, "get_pages_until", return_value=[in_range]), \
            patch.object(APICalls, "get_multiple_pages", side_effect=AssertionError("richiesta inattesa")):
        assert get_comments_by_number("o", "r", "issues", START, {}) == {6: [in_range]}


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
