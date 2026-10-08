import os
from datetime import datetime
from unittest.mock import patch

from src.logic import APICalls, GitHistory
from src.logic.GitHistory import parse_log, noreply_author, map_authors, RECORD, FIELD

TOKEN = os.environ['GH_TOKEN']
DATE = datetime(2023, 11, 1)

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


def test_get_commits_since_same_as_api():
    # il clone non consuma quota; il risultato deve coincidere con quello delle API
    def normalize(commits):
        return {c["sha"]: (c["author"]["login"], c["commit"]["author"]["date"], sorted(f["filename"] for f in c["files"]))
                for c in commits if c["author"]}

    from_git = GitHistory.get_commits_since("fullmoonlullaby", "test", DATE, TOKEN)
    from_api = APICalls.get_commits_since("fullmoonlullaby", "test", DATE, TOKEN)
    assert len(from_git) > 0
    assert normalize(from_git) == normalize(from_api)


def test_get_commits_since_nonexistent_repo():
    try:
        GitHistory.get_commits_since("fullmoonlullaby", "repo-che-non-esiste", DATE, TOKEN)
        assert False
    except GitHistory.GitError:
        assert True


def test_get_commits_since_date_none():
    try:
        GitHistory.get_commits_since("fullmoonlullaby", "test", None, TOKEN)
        assert False
    except AttributeError:
        assert True


def test_get_commits_since_until_same_as_api():
    until = datetime(2023, 11, 25)

    def normalize(commits):
        return {c["sha"]: (c["author"]["login"], sorted(f["filename"] for f in c["files"])) for c in commits if c["author"]}

    from_git = GitHistory.get_commits_since("fullmoonlullaby", "test", DATE, TOKEN, until=until)
    from_api = APICalls.get_commits_since("fullmoonlullaby", "test", DATE, TOKEN, until=until)
    everything = GitHistory.get_commits_since("fullmoonlullaby", "test", DATE, TOKEN)
    assert normalize(from_git) == normalize(from_api)
    assert 0 < len(from_git) < len(everything)
    assert all(c["commit"]["author"]["date"] <= "2023-11-25T00:00:00Z" for c in from_git)


def test_get_commits_since_no_commits_in_range():
    # nessun commit dopo la data: git non riesce a fare il clone shallow, ma il risultato è semplicemente vuoto
    assert GitHistory.get_commits_since("fullmoonlullaby", "test", datetime(2026, 10, 1), TOKEN) == []


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


def test_clone_with_invalid_token_fails_quickly(tmp_path):
    # credenziali rifiutate da GitHub: errore immediato (poi si usano le API), nessuna attesa di input
    started = datetime.now()
    try:
        GitHistory.clone("https://github.com/apache/commons-io.git", str(tmp_path / "repo.git"), DATE,
                         "token-non-valido")
        assert False
    except GitHistory.GitError:
        pass
    assert (datetime.now() - started).total_seconds() < 60
