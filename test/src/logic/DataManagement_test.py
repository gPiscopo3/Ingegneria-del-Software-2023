import os
import pickle
import sys
import datetime as dt
from unittest.mock import patch

import pytest

from src.logic import APICalls, GitHistory
from src.logic import DataManagement
from src.model.File import File
from src.model.User import User
from src.logic.DataManagement import save_data, load_data, activity_period, update_communications, communication_happened, \
    get_communications_since, get_collaborations_since, fetch_commits

# repository piccolo: senza cache su disco ogni test di integrazione scarica i dati da GitHub
owner = "fullmoonlullaby"
repo_name = "test"
starting_date = dt.datetime(2023, 12, 10)
starting_date_out = dt.datetime(2024, 12, 10)


def response(*replies):
    # risposte di una issue/PR come le restituisce APICalls: lista di (data, autore) ordinata per data
    return [(date, {"id": user_id, "login": login}) for date, user_id, login in replies]


def at(day, hour=0):
    return dt.datetime(2023, 12, day, hour)


def communications_of(user):
    return {date: sorted(r.username for r in receivers) for date, receivers in user.communications.items()}


def create_sample_data():
    alice = User(1, "alice")
    bob = User(2, "bob")
    alice.update_communication(dt.datetime(2023, 12, 1), {bob})
    file = File("README.md")
    file.add_edit(dt.datetime(2023, 12, 2), alice)
    file.add_edit(dt.datetime(2023, 12, 3), bob)
    return {"README.md": file}, {1: alice, 2: bob}


def write_pickle(path, data):
    with open(path, 'wb') as fp:
        pickle.dump(data, fp)


def valid_data(**changes):
    files, _ = create_sample_data()
    data = {"format": "graphapp-data", "version": 2, "owner": owner, "repo": repo_name,
            "starting_date": starting_date, "saved_at": dt.datetime(2024, 1, 10), "files": files, "users": None}
    data.update(changes)
    return data


def test_activity_period_ok():
    files, users = create_sample_data()
    assert activity_period(files, users) == (dt.datetime(2023, 12, 1), dt.datetime(2023, 12, 3))


def test_activity_period_only_files():
    files, _ = create_sample_data()
    assert activity_period(files, None) == (dt.datetime(2023, 12, 2), dt.datetime(2023, 12, 3))


def test_activity_period_only_users():
    _, users = create_sample_data()
    assert activity_period(None, users) == (dt.datetime(2023, 12, 1), dt.datetime(2023, 12, 1))


def test_activity_period_no_events():
    assert activity_period(None, None) is None
    assert activity_period({}, {1: User(1, "alice")}) is None


def test_save_load_data_ok(tmp_path):
    files, users = create_sample_data()
    path = str(tmp_path / "dati.graphapp")
    save_data(path, owner, repo_name, starting_date, files, users)
    data = load_data(path)
    assert data["version"] == DataManagement.DATA_VERSION
    assert (data["owner"], data["repo"], data["starting_date"]) == (owner, repo_name, starting_date)
    assert set(data["files"]) == {"README.md"}
    assert set(data["users"]) == {1, 2}
    # gli utenti condivisi restano lo stesso oggetto anche dopo il caricamento
    bob = data["users"][2]
    assert bob in data["users"][1].communications[dt.datetime(2023, 12, 1)]
    assert data["files"]["README.md"].modified_by[0] == (dt.datetime(2023, 12, 2), data["users"][1])


def test_save_load_data_partial(tmp_path):
    files, _ = create_sample_data()
    path = str(tmp_path / "dati.graphapp")
    save_data(path, owner, repo_name, starting_date, files, None)
    data = load_data(path)
    assert data["users"] is None
    assert len(data["files"]) == 1


def test_save_load_data_ranges(tmp_path):
    files, users = create_sample_data()
    files_range = (dt.datetime(2023, 12, 1), dt.datetime(2023, 12, 31, 23, 59, 59))
    users_range = (dt.datetime(2023, 11, 1), dt.datetime(2023, 12, 15, 23, 59, 59))
    path = str(tmp_path / "dati.graphapp")
    save_data(path, owner, repo_name, starting_date, files, users, files_range, users_range)
    data = load_data(path)
    assert data["files_range"] == files_range
    assert data["users_range"] == users_range
    assert data["starting_date"] == dt.datetime(2023, 11, 1)  # inizio minimo tra le due parti
    assert data["ending_date"] == dt.datetime(2023, 12, 31, 23, 59, 59)  # fine massima


def test_load_data_without_ranges(tmp_path):
    # file salvati prima degli intervalli: valgono da starting_date al salvataggio
    path = tmp_path / "vecchio.graphapp"
    write_pickle(path, valid_data(version=1))
    data = load_data(str(path))
    assert data["files_range"] == (starting_date, dt.datetime(2024, 1, 10))
    assert data["users_range"] is None
    assert data["ending_date"] == dt.datetime(2024, 1, 10)


def test_load_data_inverted_range_uses_fallback(tmp_path):
    path = tmp_path / "dati.graphapp"
    write_pickle(path, valid_data(files_range=(dt.datetime(2023, 12, 31), dt.datetime(2023, 12, 1))))
    assert load_data(str(path))["files_range"] == (starting_date, dt.datetime(2024, 1, 10))


def test_load_data_version_1_edits_converted(tmp_path):
    # versione 1: File.modified_by era un dict {data: autore}; al caricamento diventa una lista ordinata
    alice = User(1, "alice")
    file = File("a.py")
    file.modified_by = {dt.datetime(2023, 12, 1): alice, dt.datetime(2023, 12, 5): alice}
    path = tmp_path / "v1.graphapp"
    write_pickle(path, valid_data(version=1, files={"a.py": file}))
    edits = load_data(str(path))["files"]["a.py"].modified_by
    assert [date for date, _ in edits] == [dt.datetime(2023, 12, 5), dt.datetime(2023, 12, 1)]
    assert edits[0][1] is edits[1][1]  # lo stesso utente resta un unico oggetto


@pytest.mark.parametrize("changes", [
    {"version": 3},
    {"owner": ""},
    {"repo": None},
    {"files": ["non", "un", "dict"]},
    {"files": None, "users": None},
], ids=["version", "owner_empty", "repo_none", "files_not_dict", "nothing"])
def test_load_data_invalid_fields(tmp_path, changes):
    path = tmp_path / "dati.graphapp"
    write_pickle(path, valid_data(**changes))
    with pytest.raises(ValueError):
        load_data(str(path))


def test_save_load_data_long_chain(tmp_path):
    # repository grandi: utenti collegati in catena più lunga del limite di ricorsione di pickle
    size = 2 * sys.getrecursionlimit()
    chain = [User(i, f"user{i}") for i in range(size)]
    for current, following in zip(chain, chain[1:]):
        current.update_communication(dt.datetime(2023, 12, 1), {following})
    file = File("a.py")
    file.add_edit(dt.datetime(2023, 12, 2), chain[0])
    file.add_edit(dt.datetime(2023, 12, 3), chain[-1])
    path = str(tmp_path / "dati.graphapp")
    save_data(path, owner, repo_name, starting_date, {"a.py": file}, {user.identifier: user for user in chain})
    data = load_data(path)
    users = data["users"]
    assert len(users) == size
    for i in range(size - 1):
        assert users[i].username == f"user{i}"
        assert users[i].communications == {dt.datetime(2023, 12, 1): {users[i + 1]}}
    assert users[size - 1].communications == {}
    edits = data["files"]["a.py"].modified_by
    assert edits == [(dt.datetime(2023, 12, 2), users[0]), (dt.datetime(2023, 12, 3), users[size - 1])]


def test_save_load_data_distinct_users_stay_distinct(tmp_path):
    # come nei download reali: stesso identificativo, ma l'autore del file e quello delle comunicazioni sono oggetti diversi
    sender, receiver = User(1, "alice"), User(2, "bob")
    sender.update_communication(dt.datetime(2023, 12, 1), {receiver})
    file_author = User(1, "alice")
    file = File("a.py")
    file.add_edit(dt.datetime(2023, 12, 2), file_author)
    path = str(tmp_path / "dati.graphapp")
    save_data(path, owner, repo_name, starting_date, {"a.py": file}, {1: sender, 2: receiver})
    data = load_data(path)
    loaded_author = data["files"]["a.py"].modified_by[0][1]
    assert loaded_author is not data["users"][1]
    assert loaded_author.communications == {}
    assert data["users"][1].communications == {dt.datetime(2023, 12, 1): {data["users"][2]}}


def test_load_data_v3_bad_index(tmp_path):
    path = tmp_path / "dati.graphapp"
    write_pickle(path, valid_data(version=3, files=None, users={1: 5},
                                  user_table=[(1, "alice", [(dt.datetime(2023, 12, 1), [])])]))
    with pytest.raises(ValueError):
        load_data(str(path))


def test_load_data_unsupported_version(tmp_path):
    path = tmp_path / "dati.graphapp"
    write_pickle(path, valid_data(version=99))
    with pytest.raises(ValueError):
        load_data(str(path))


def test_save_data_failure_keeps_previous_file(tmp_path):
    files, users = create_sample_data()
    path = tmp_path / "dati.graphapp"
    save_data(str(path), owner, repo_name, starting_date, files, users)
    before = path.read_bytes()
    with patch("src.logic.DataManagement.pickle.dump", side_effect=RecursionError):
        with pytest.raises(RecursionError):
            save_data(str(path), owner, repo_name, starting_date, files, users)
    assert path.read_bytes() == before
    assert os.listdir(tmp_path) == ["dati.graphapp"]  # nessun file temporaneo rimasto


def test_save_data_nothing_to_save(tmp_path):
    path = tmp_path / "dati.graphapp"
    with pytest.raises(ValueError):
        save_data(str(path), owner, repo_name, starting_date, None, None)
    assert not path.exists()


def test_load_data_empty_file(tmp_path):
    path = tmp_path / "vuoto.graphapp"
    path.write_bytes(b"")
    with pytest.raises(ValueError):
        load_data(str(path))


def test_load_data_corrupted_file(tmp_path):
    path = tmp_path / "corrotto.graphapp"
    path.write_bytes(b"questo non e' un file di dati")
    with pytest.raises(ValueError):
        load_data(str(path))


def test_load_data_wrong_format(tmp_path):
    path = tmp_path / "altro.graphapp"
    write_pickle(path, {'key1': 'value1'})
    with pytest.raises(ValueError):
        load_data(str(path))


def test_load_data_forbidden_class(tmp_path):
    # il file è valido in tutto tranne che per l'oggetto malevolo: l'errore deve venire dall'unpickler ristretto,
    # e il codice dell'oggetto non deve essere eseguito (altrimenti creerebbe la cartella)
    trace = tmp_path / "eseguito"

    class Malicious:
        def __reduce__(self):
            return os.mkdir, (str(trace),)

    path = tmp_path / "malevolo.graphapp"
    write_pickle(path, valid_data(files={"a.py": Malicious()}))
    with pytest.raises(ValueError):
        load_data(str(path))
    assert not trace.exists()


def test_load_data_nonexistent_file(tmp_path):
    with pytest.raises(OSError):
        load_data(str(tmp_path / "inesistente.graphapp"))


# *****************************************************************************************************
# comunicazioni: ogni risposta è rivolta agli autori delle risposte precedenti (escluso se stesso)


def test_update_communications_ok():
    all_users = {}
    update_communications(response((at(1), 1, "a"), (at(2), 2, "b"), (at(3), 1, "a"), (at(4), 3, "c")),
                          all_users, dt.datetime(2023, 11, 1))
    assert set(all_users) == {1, 2, 3}
    assert communications_of(all_users[2]) == {at(2): ["a"]}
    assert communications_of(all_users[1]) == {at(3): ["b"]}  # non comunica con se stesso
    assert communications_of(all_users[3]) == {at(4): ["a", "b"]}


def test_update_communications_same_second_replies():
    # due risposte nello stesso secondo di utenti diversi: entrambe contano
    all_users = {}
    update_communications(response((at(1), 1, "a"), (at(2), 2, "b"), (at(2), 3, "c")), all_users,
                          dt.datetime(2023, 11, 1))
    assert communications_of(all_users[2]) == {at(2): ["a"]}
    assert communications_of(all_users[3]) == {at(2): ["a", "b"]}


def test_update_communications_empty_response():
    all_users = {}
    update_communications(response=[], all_users=all_users, starting_date=starting_date)
    assert all_users == {}


def test_update_communications_out_range_starting_date():
    # gli utenti vengono creati, ma nessuna comunicazione prima di starting_date
    all_users = {}
    update_communications(response((at(1), 1, "a"), (at(2), 2, "b")), all_users, starting_date_out)
    assert set(all_users) == {1, 2}
    assert all(user.communications == {} for user in all_users.values())


def test_update_communications_author_before_range_is_receiver():
    # l'autore di una risposta fuori intervallo riceve comunque le risposte successive
    all_users = {}
    update_communications(response((at(1), 1, "a"), (at(20), 2, "b")), all_users, starting_date)
    assert all_users[1].communications == {}
    assert communications_of(all_users[2]) == {at(20): ["a"]}


def test_update_communications_until_inclusive():
    all_users = {}
    until = at(15)
    update_communications(response((at(11), 1, "a"), (until, 2, "b"), (at(16), 3, "c")), all_users,
                          starting_date, until)
    assert communications_of(all_users[2]) == {until: ["a"]}  # estremo finale incluso
    assert all_users[3].communications == {}  # dopo until


def test_update_communications_none_response():
    with pytest.raises(TypeError):
        update_communications(response=None, all_users={}, starting_date=starting_date)


def test_update_communications_bad_formatted_response():
    with pytest.raises(TypeError):
        update_communications(response=[(at(1), "")], all_users={}, starting_date=starting_date)


def test_update_communications_none_all_users():
    with pytest.raises(TypeError):
        update_communications(response=response((at(1), 1, "a")), all_users=None, starting_date=starting_date)


def test_update_communications_none_starting_date():
    with pytest.raises(TypeError):
        update_communications(response=response((at(1), 1, "a")), all_users={}, starting_date=None)


def test_communication_happened_different_authors():
    assert communication_happened(response((at(1), 1, "a"), (at(2), 2, "b"))) is True


def test_communication_happened_only_creator():
    assert communication_happened(response((at(1), 1, "a"), (at(2), 1, "a"))) is False


def test_communication_happened_none_response():
    with pytest.raises(TypeError):
        communication_happened(response=None)


def test_communication_happened_empty_response():
    assert communication_happened(response=[]) is False


def test_communication_happened_bad_formatted_response():
    with pytest.raises(TypeError):
        communication_happened(response=[(at(1), "")])


def test_get_communications_since_date_none():
    with pytest.raises(TypeError):
        get_communications_since(owner, repo_name, None, "")


def test_get_communications_since_downloads_listing_once():
    # issue e PR dallo stesso elenco: una sola scansione, e la PR vecchia ma attiva nel periodo conta
    t = "2023-12-12T10:00:00Z"
    listing = [{"number": 1, "created_at": t, "user": {"id": 1, "login": "alice"}},
               {"number": 2, "created_at": "2023-10-01T10:00:00Z", "user": {"id": 3, "login": "carol"},
                "pull_request": {}}]
    comments = {1: [{"created_at": t, "user": {"id": 2, "login": "bob"}}],
                2: [{"created_at": "2023-12-13T10:00:00Z", "user": {"id": 1, "login": "alice"}}]}
    with patch.object(APICalls, "get_comments_by_number", return_value=comments),             patch.object(APICalls, "get_issue_listing", return_value=listing) as get_listing,             patch.object(APICalls, "get_multiple_pages", return_value=[]):
        users = get_communications_since(owner, repo_name, starting_date, "")
    get_listing.assert_called_once()
    assert communications_of(users[2]) == {dt.datetime(2023, 12, 12, 10): ["alice"]}  # bob risponde alla issue
    assert communications_of(users[1]) == {dt.datetime(2023, 12, 13, 10): ["carol"]}  # alice alla PR vecchia


# *****************************************************************************************************
# collaborazioni con i commit simulati (nessuna chiamata a GitHub)


def commit(user_id, login, date, *files):
    return {"sha": f"{user_id}-{date}", "author": {"id": user_id, "login": login} if user_id else None,
            "commit": {"author": {"date": date}}, "files": [{"filename": f} for f in files]}


def test_get_collaborations_since_offline():
    commits = [
        commit(1, "alice", "2023-12-01T10:00:00Z", "a.py", "b.py"),
        commit(2, "bob", "2023-12-01T10:00:00Z", "a.py"),  # stesso file nello stesso secondo: entrambi contano
        commit(None, None, "2023-12-02T10:00:00Z", "a.py"),  # autore senza account GitHub: ignorato
        {"sha": "x", "author": {"id": 3, "login": "carol"}, "commit": {"author": {"date": "2023-12-03T10:00:00Z"}}},
        commit(1, "alice", "2023-12-04T10:00:00Z", "a.py"),
    ]
    with patch.object(DataManagement, "fetch_commits", return_value=commits):
        files = get_collaborations_since(owner, repo_name, starting_date, "")
    assert set(files) == {"a.py", "b.py"}
    a_edits = [(date.day, author.username) for date, author in files["a.py"].modified_by]
    assert a_edits[0] == (4, "alice")  # ordinate per data decrescente
    assert sorted(a_edits[1:]) == [(1, "alice"), (1, "bob")]
    # lo stesso utente è un unico oggetto in tutti i file
    assert files["a.py"].modified_by[0][1] is files["b.py"].modified_by[0][1]


def test_fetch_commits_falls_back_to_api_when_clone_fails():
    messages = []
    with patch.object(GitHistory, "git_available", return_value=True), \
            patch.object(GitHistory, "get_commits_since", side_effect=GitHistory.GitError("negato")), \
            patch.object(APICalls, "get_commits_since", return_value=["dalle API"]) as api:
        result = fetch_commits(owner, repo_name, starting_date, "", lambda m, d, t: messages.append(m))
    assert result == ["dalle API"]
    api.assert_called_once()
    assert len(messages) == 1


def test_fetch_commits_without_git_uses_api():
    with patch.object(GitHistory, "git_available", return_value=False), \
            patch.object(GitHistory, "get_commits_since", side_effect=AssertionError("git non disponibile")), \
            patch.object(APICalls, "get_commits_since", return_value=[]) as api:
        assert fetch_commits(owner, repo_name, starting_date, "") == []
    api.assert_called_once()


@pytest.mark.parametrize("git", [True, False], ids=["git", "api"])
def test_get_collaborations_since_date_none(git):
    with patch.object(GitHistory, "git_available", return_value=git), \
            patch.object(APICalls, "get_multiple_pages", return_value=[]):
        with pytest.raises(AttributeError):
            get_collaborations_since(owner, repo_name, None, "")


# *****************************************************************************************************
# integrazione: chiamate reali a GitHub


@pytest.mark.integration
def test_get_communications_since_ok(token):
    start = dt.datetime(year=2023, month=11, day=1)
    all_users_res = get_communications_since(owner, repo_name, start, token)
    assert any(user.communications for user in all_users_res.values())
    for user_id, user in all_users_res.items():
        assert user.identifier == user_id
        for date, receivers in user.communications.items():
            assert date >= start
            assert receivers and user not in receivers
        dates = list(user.communications)
        assert dates == sorted(dates, reverse=True)


@pytest.mark.integration
def test_get_communications_since_owner_nonexistent(token, http_statuses):
    assert get_communications_since("", repo_name, starting_date, token) == {}
    assert set(http_statuses) == {404}


@pytest.mark.integration
def test_get_communications_since_repo_nonexistent(token, http_statuses):
    assert get_communications_since(owner, "", starting_date, token) == {}
    assert set(http_statuses) == {404}


@pytest.mark.integration
def test_get_communications_since_date_now(token, http_statuses):
    assert get_communications_since(owner, repo_name, starting_date_out, token) == {}
    assert set(http_statuses) == {200}  # vuoto perché non ci sono dati, non per un errore


@pytest.mark.integration
def test_get_communications_since_token_nonexistent(http_statuses):
    assert get_communications_since(owner, repo_name, starting_date, 'token_sbagliato') == {}
    assert set(http_statuses) == {401}


@pytest.mark.integration
def test_get_collaborations_since_ok(token):
    start = dt.datetime(year=2023, month=11, day=1)
    files = get_collaborations_since(owner, repo_name, start, token)
    assert len(files) > 0
    for name, file in files.items():
        assert file.identifier == name
        dates = [date for date, _ in file.modified_by]
        assert dates and dates == sorted(dates, reverse=True)
        assert all(date >= start for date in dates)
        assert all(isinstance(author, User) for _, author in file.modified_by)


@pytest.mark.integration
def test_get_collaborations_since_owner_nonexistent(token, http_statuses):
    with patch.object(GitHistory, "git_available", return_value=False):
        assert get_collaborations_since("", repo_name, starting_date, token) == {}
    assert set(http_statuses) == {404}


@pytest.mark.integration
def test_get_collaborations_since_repo_nonexistent(token, http_statuses):
    with patch.object(GitHistory, "git_available", return_value=False):
        assert get_collaborations_since(owner, "", starting_date, token) == {}
    assert set(http_statuses) == {404}


@pytest.mark.integration
def test_get_collaborations_since_token_nonexistent(http_statuses):
    with patch.object(GitHistory, "git_available", return_value=False):
        assert get_collaborations_since(owner, repo_name, starting_date, 'token_sbagliato') == {}
    assert set(http_statuses) == {401}


@pytest.mark.integration
def test_get_collaborations_since_date_now(token):
    assert get_collaborations_since(owner, repo_name, starting_date_out, token) == {}
