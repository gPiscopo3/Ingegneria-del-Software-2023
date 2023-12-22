from datetime import datetime
from src.logic.APICalls import *

DATE = datetime(2023, 11, 1)
TOKEN = "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"
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
    except AttributeError:
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
