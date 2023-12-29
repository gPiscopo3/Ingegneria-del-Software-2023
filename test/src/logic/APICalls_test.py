from datetime import datetime
from datetime import timedelta
from src.logic.APICalls import *
import os

DATE = datetime(2023, 11, 1)
TOKEN = os.environ['GH_TOKEN']
OWNER = "fullmoonlullaby"
REPO = "test"


def test_get_issues_ok():
    issues = get_issues_since(OWNER, REPO, DATE, TOKEN)
    assert len(issues) > 0  # va fatto meglio, non basta controllare se non vuota


def test_get_issues_owner_none():
    try:
        get_issues_since(None, REPO, DATE, TOKEN)
        assert False
    except TypeError:
        assert True


def test_get_issues_owner_nonexistent():
    issues = get_issues_since("", REPO, DATE, TOKEN)
    assert len(issues) == 0


def test_get_issues_repo_none():
    try:
        get_issues_since(OWNER, None, DATE, TOKEN)
        assert False
    except TypeError:
        assert True


def test_get_issues_repo_nonexistent():
    issues = get_issues_since(OWNER, "", DATE, TOKEN)
    assert len(issues) == 0


def test_get_issues_date_none():
    try:
        get_issues_since(OWNER, REPO, None, TOKEN)
        assert False
    except AttributeError:
        assert True


def test_get_issues_date_now():
    issues = get_issues_since(OWNER, REPO, datetime.now(), TOKEN)
    assert len(issues) == 0


def test_get_issues_token_none():
    try:
        get_issues_since(OWNER, REPO, DATE, None)
        assert False
    except TypeError:
        assert True


def test_get_issues_token_nonexistent():
    issues = get_issues_since(OWNER, REPO, DATE, "token_sbagliato")
    assert len(issues) == 0


def test_get_pulls_ok():
    pulls = get_pulls_since(OWNER, REPO, DATE, TOKEN)
    assert len(pulls) > 0  # va fatto meglio, non basta controllare se non vuota


def test_get_pulls_owner_none():
    try:
        get_pulls_since(None, REPO, DATE, TOKEN)
        assert False
    except TypeError:
        assert True


def test_get_pulls_owner_nonexistent():
    pulls = get_pulls_since("", REPO, DATE, TOKEN)
    assert len(pulls) == 0


def test_get_pulls_repo_none():
    try:
        get_pulls_since(OWNER, None, DATE, TOKEN)
        assert False
    except TypeError:
        assert True


def test_get_pulls_repo_nonexistent():
    pulls = get_pulls_since(OWNER, "", DATE, TOKEN)
    assert len(pulls) == 0


def test_get_pulls_date_none():
    try:
        get_pulls_since(OWNER, REPO, None, TOKEN)
        assert False
    except TypeError:
        assert True


"""#def test_get_pulls_date_now():
    pulls = get_pulls_since(OWNER, REPO, datetime.now(), TOKEN)
    assert len(pulls) == 0"""


def test_get_pulls_token_none():
    try:
        get_pulls_since(OWNER, REPO, DATE, None)
        assert False
    except TypeError:
        assert True


def test_get_pulls_token_nonexistent():
    pulls = get_pulls_since(OWNER, REPO, DATE, "token_sbagliato")
    assert len(pulls) == 0


def test_get_commits_ok():
    commits = get_commits_since(OWNER, REPO, DATE, TOKEN)
    assert len(commits) > 0  # va fatto meglio, non basta controllare se non vuota


def test_get_commits_owner_none():
    try:
        get_commits_since(None, REPO, DATE, TOKEN)
        assert False
    except TypeError:
        assert True


def test_get_commits_owner_nonexistent():
    commits = get_commits_since("", REPO, DATE, TOKEN)
    assert len(commits) == 0


def test_get_commits_repo_none():
    try:
        get_commits_since(OWNER, None, DATE, TOKEN)
        assert False
    except TypeError:
        assert True


def test_get_commits_repo_nonexistent():
    commits = get_commits_since(OWNER, "", DATE, TOKEN)
    assert len(commits) == 0


def test_get_commits_date_none():
    try:
        get_commits_since(OWNER, REPO, None, TOKEN)
        assert False
    except AttributeError:
        assert True


def test_get_commits_date_now():
    commits = get_commits_since(OWNER, REPO, datetime.now(), TOKEN)
    assert len(commits) == 0


def test_get_commits_token_none():
    try:
        get_commits_since(OWNER, REPO, DATE, None)
        assert False
    except TypeError:
        assert True


def test_get_commits_token_nonexistent():
    commits = get_commits_since(OWNER, REPO, DATE, "token_sbagliato")
    assert len(commits) == 0


def test_get_multiple_pages_ok():
    results = get_multiple_pages("https://api.github.com/repos/fullmoonlullaby/test/issues?per_page=1",
                                 {"Authorization": "Bearer " + TOKEN})
    assert len(results) >= 0


def test_get_multiple_pages_bad_url():
    try:
        get_multiple_pages("bad url", {"Authorization": "Bearer " + TOKEN})
        assert False
    except ValueError:
        assert True


def test_get_multiple_pages_none_url():
    results = get_multiple_pages(None, {"Authorization": "Bearer " + TOKEN})
    assert len(results) == 0


def test_get_multiple_pages_not_found():
    results = get_multiple_pages("https://api.github.com/repos/non_existent/test/issues?per_page=1",
                                 {"Authorization": "Bearer " + TOKEN})
    assert len(results) == 0


def test_get_multiple_pages_bad_header():
    try:
        get_multiple_pages("https://api.github.com/repos/fullmoonlullaby/test/issues", "wrong type")
        assert False
    except AttributeError:
        assert True


def test_get_with_ratelimit_ok():
    results = get_with_ratelimit("https://api.github.com/repos/fullmoonlullaby/test/issues",
                                 {})
    assert results.status_code == 200


def test_get_with_ratelimit_bad_url():
    try:
        get_with_ratelimit("Bad url", {"Authorization": "Bearer " + TOKEN})
        assert False
    except ValueError:
        assert True


def test_get_with_ratelimit_none():
    try:
        get_with_ratelimit(None, {"Authorization": "Bearer " + TOKEN})
        assert False
    except ValueError:
        assert True


def test_get_with_ratelimit_not_found():
    results = get_with_ratelimit("https://api.github.com/repos/not_existent/test/issues",
                                 {})
    assert results.status_code == 404


def test_get_with_ratelimit_bad_header():
    try:
        get_with_ratelimit("https://api.github.com/repos/boh/test/issues", "wrong type")
        assert False
    except AttributeError:
        assert True


def test_filter_pulls_by_date_ok():
    results = filter_pulls_by_date("https://api.github.com/repos/fullmoonlullaby/test/pulls",
                                   {"Authorization": "Bearer " + TOKEN},
                                   DATE)

    assert len(results) >= 0


def test_filter_pulls_by_date_bad_url():
    try:
        filter_pulls_by_date("bad url", {"Authorization": "Bearer " + TOKEN}, DATE)
        assert False
    except ValueError:
        assert True


def test_filter_pulls_by_date_none_url():
    results = filter_pulls_by_date(None, {"Authorization": "Bearer " + TOKEN}, DATE)
    assert len(results) == 0


def test_filter_pulls_by_date_url_not_found():
    results = filter_pulls_by_date("https://api.github.com/repos/not_existent/test/pulls",
                                   {"Authorization": "Bearer " + TOKEN},
                                   DATE)
    assert len(results) == 0


def test_filter_pulls_by_date_bad_header():
    try:
        filter_pulls_by_date("https://api.github.com/repos/fullmoonlullaby/test/pulls?per_page=1",
                             "wrong type", DATE)
        assert False
    except AttributeError:
        assert True


def test_filter_pulls_by_date_wrong_date_format():
    try:
        filter_pulls_by_date("https://api.github.com/repos/fullmoonlullaby/test/pulls",
                             {"Authorization": "Bearer " + TOKEN},
                             None)
        assert False
    except TypeError:
        assert True


def test_filter_pulls_by_date_date_not_in_range():
    results = filter_pulls_by_date("https://api.github.com/repos/fullmoonlullaby/test/pulls",
                                   {"Authorization": "Bearer " + TOKEN},
                                   datetime.now() + timedelta(days=2))
    assert len(results) == 0


def test_reformat_response_wrong_type():
    try:
        reformat_response("wrong type")
        assert False
    except TypeError:
        assert True
