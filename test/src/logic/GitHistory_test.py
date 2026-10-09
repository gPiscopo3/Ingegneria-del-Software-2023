import json
import os
from datetime import datetime
from unittest.mock import patch

import pytest
import requests

from src.logic import APICalls, GitHistory
from src.logic.GitHistory import parse_log, noreply_author, map_authors, RECORD, FIELD

DATE = datetime(2023, 11, 1)
UNTIL = datetime(2023, 11, 25)

LOG = (RECORD + "aaa" + FIELD + "1+alice@users.noreply.github.com" + FIELD + "2023-11-26T14:37:21+01:00\n\n"
       "src/a.py\nsrc/b.py\n" +
       RECORD + "bbb" + FIELD + "bob@example.com" + FIELD + "2023-11-25T23:30:00-02:00\n\n"
       "README.md\n" +
       RECORD + "ccc" + FIELD + "bob@example.com" + FIELD + "2023-11-24T10:00:00+00:00\n")  # commit senza file


def test_parse_log_ok():
    commits = parse_log(LOG)
    assert [c[0] for c in commits] == ["aaa", "bbb", "ccc"]
    assert commits[0][3] == ["src/a.py", "src/b.py"]
    assert commits[2][3] == []


def test_parse_log_dates_in_utc():
    commits = parse_log(LOG)
    assert commits[0][2] == "2023-11-26T13:37:21Z"
    assert commits[1][2] == "2023-11-26T01:30:00Z"  # il fuso orario può cambiare il giorno


def test_parse_log_empty():
    assert parse_log("") == []


def test_noreply_author():
    assert noreply_author("149693954+fullmoonlullaby@users.noreply.github.com") == \
           {"id": 149693954, "login": "fullmoonlullaby"}
    assert noreply_author("bob@example.com") is None


def test_map_authors_uses_noreply_without_requests():
    with patch.object(APICalls, "get_with_ratelimit", side_effect=AssertionError("richiesta inattesa")):
        authors = map_authors("o", "r", "2023-11-01T00:00:00Z", {}, parse_log(LOG)[:1])
    assert authors == {"1+alice@users.noreply.github.com": {"id": 1, "login": "alice"}}


@pytest.fixture(name="downloads", scope="module")
def fixture_downloads():
    # ogni combinazione (git/API, con o senza until) scaricata una sola volta per tutti i test del modulo
    token = os.environ["GH_TOKEN"]
    return {
        "git": GitHistory.get_commits_since("fullmoonlullaby", "test", DATE, token),
        "api": APICalls.get_commits_since("fullmoonlullaby", "test", DATE, token),
        "git_until": GitHistory.get_commits_since("fullmoonlullaby", "test", DATE, token, until=UNTIL),
        "api_until": APICalls.get_commits_since("fullmoonlullaby", "test", DATE, token, until=UNTIL),
    }


@pytest.mark.integration
def test_get_commits_since_same_as_api(downloads):
    # il clone non consuma quota; il risultato deve coincidere con quello delle API
    def normalize(commits):
        return {c["sha"]: (c["author"]["login"], c["commit"]["author"]["date"], sorted(f["filename"] for f in c["files"]))
                for c in commits if c["author"]}

    assert len(downloads["git"]) > 0
    assert normalize(downloads["git"]) == normalize(downloads["api"])


@pytest.mark.integration
def test_get_commits_since_nonexistent_repo(token):
    with pytest.raises(GitHistory.GitError):
        GitHistory.get_commits_since("fullmoonlullaby", "repo-che-non-esiste", DATE, token)


def test_get_commits_since_date_none():
    with pytest.raises(AttributeError):
        GitHistory.get_commits_since("fullmoonlullaby", "test", None, "")


@pytest.mark.integration
def test_get_commits_since_until_same_as_api(downloads):
    def normalize(commits):
        return {c["sha"]: (c["author"]["login"], sorted(f["filename"] for f in c["files"])) for c in commits if c["author"]}

    from_git = downloads["git_until"]
    assert normalize(from_git) == normalize(downloads["api_until"])
    assert 0 < len(from_git) < len(downloads["git"])
    assert all(c["commit"]["author"]["date"] <= "2023-11-25T00:00:00Z" for c in from_git)


@pytest.mark.integration
def test_get_commits_since_no_commits_in_range(token):
    # nessun commit dopo la data: git non riesce a fare il clone shallow, ma il risultato è semplicemente vuoto
    assert GitHistory.get_commits_since("fullmoonlullaby", "test", datetime(2026, 10, 1), token) == []


def clone_call(token):
    with patch.object(GitHistory, "_run") as run:
        GitHistory.clone("https://github.com/o/r.git", "dest", DATE, token)
    command, _, env, _ = run.call_args.args
    return command, env


def test_clone_never_asks_for_credentials():
    # né richiesta nel terminale né finestra di Git Credential Manager: con credenziali rifiutate git deve fallire
    command, env = clone_call("token-di-prova")
    assert command[:4] == ["git", "-c", "credential.helper=", "clone"]
    assert env["GIT_TERMINAL_PROMPT"] == "0"
    assert env["GCM_INTERACTIVE"] == "never"


def test_clone_token_only_in_environment():
    command, env = clone_call("token-di-prova")
    assert not any("token-di-prova" in part for part in command)
    assert env["GIT_CONFIG_KEY_0"] == "http.extraHeader"
    assert env["GIT_CONFIG_VALUE_0"].startswith("Authorization: Basic ")
    _, env = clone_call("")
    assert "GIT_CONFIG_COUNT" not in env or env.get("GIT_CONFIG_KEY_0") != "http.extraHeader"


@pytest.mark.integration
def test_clone_with_invalid_token_fails_quickly(tmp_path):
    # credenziali rifiutate da GitHub: errore immediato (poi si usano le API), nessuna attesa di input
    started = datetime.now()
    with pytest.raises(GitHistory.GitError):
        GitHistory.clone("https://github.com/apache/commons-io.git", str(tmp_path / "repo.git"), DATE,
                         "token-non-valido")
    assert (datetime.now() - started).total_seconds() < 60


def test_git_log_without_rename_detection():
    # il clone non ha i blob: con il rilevamento dei rename git li scaricherebbe uno a uno e il download si blocca
    def fake_run(_command, stdout_path, *_):
        open(stdout_path, "w", encoding="utf-8").close()  # git log senza commit

    with patch.object(GitHistory, "clone"), patch.object(GitHistory, "_run", side_effect=fake_run) as run, \
            patch.object(GitHistory, "read_shallow", return_value=set()), \
            patch.object(GitHistory, "map_authors", return_value={}):
        GitHistory.get_commits_since("o", "r", DATE, "")
    command = run.call_args.args[0]
    assert command[3] == "log"
    assert "--no-renames" in command


def api_response(status, body=None):
    res = requests.Response()
    res.status_code = status
    res._content = json.dumps(body if body is not None else {}).encode()
    return res


# bob@example.com non compare nell'elenco dei commit (404): resta lo step 2, un commit per email
def map_bob(commit_response):
    def fake_get(url, _header):
        if "/commits/bbb" in url:
            return commit_response
        return api_response(404)

    with patch.object(APICalls, "get_with_ratelimit", side_effect=fake_get):
        return map_authors("o", "r", "2023-11-01T00:00:00Z", {}, parse_log(LOG)[1:])


def test_map_authors_resolves_author_from_single_commit():
    authors = map_bob(api_response(200, {"author": {"id": 7, "login": "bob"}}))
    assert authors == {"bob@example.com": {"id": 7, "login": "bob"}}


def test_map_authors_commit_without_account_is_none():
    assert map_bob(api_response(200, {"author": None})) == {"bob@example.com": None}


@pytest.mark.parametrize("status", [404, 422])
def test_map_authors_unknown_commit_is_none(status):
    assert map_bob(api_response(status)) == {"bob@example.com": None}


@pytest.mark.parametrize("status", [403, 429, 500, 502])
def test_map_authors_raises_on_quota_and_server_errors(status):
    with pytest.raises(requests.HTTPError):
        map_bob(api_response(status))
