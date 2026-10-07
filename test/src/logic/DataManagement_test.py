import json
import os
import pickle
import datetime as dt
from typing import Dict
from unittest.mock import MagicMock

from src.logic import APICalls
import pytest

from src.model.File import File
from src.model.User import User
from src.logic.DataManagement import save_data, load_data, activity_period, update_communications, communication_happened, \
    get_communications_since, get_collaborations_since

# repository piccolo: senza cache su disco ogni test scarica i dati da GitHub
owner = "fullmoonlullaby"
repo_name = "test"
token = os.environ['GH_TOKEN']
starting_date = dt.datetime(2023, 12, 10)
starting_date_out = dt.datetime(2024, 12, 10)

response_getpulls_bad_formatted = {1: ""}

user = User("1", "nick")
all_users = {1: user}


def create_mock_response_getpulls():
    return [
        {
            dt.datetime(2023, 12, 22, 0, 30, 42): {
                'login': 'user2',
                'id': 49699332,
                'node_id': 'MDM6Qm90NDk2OTkzMzN=',
                'avatar_url': 'https://avatars.githubusercontent.com/in/29120?v=4',
                'gravatar_id': '',
                'url': 'https://api.github.com/users/user2%5Bbot%5D',
                'html_url': 'https://github.com/apps/user2',
                'type': 'Bot',
                'site_admin': False
            }
        },
        {
            dt.datetime(2023, 12, 22, 0, 30, 43): {
                'login': 'dependabot[bot]',
                'id': 49699333,
                'node_id': 'MDM6Qm90NDk2OTkzMzM=',
                'avatar_url': 'https://avatars.githubusercontent.com/in/29110?v=4',
                'gravatar_id': '',
                'url': 'https://api.github.com/users/dependabot%5Bbot%5D',
                'html_url': 'https://github.com/apps/dependabot',
                'type': 'Bot',
                'site_admin': False
            }
        }
    ]


# Creazione del mock
mock_get_pulls_since = MagicMock(return_value=create_mock_response_getpulls())


def create_sample_data():
    alice = User(1, "alice")
    bob = User(2, "bob")
    alice.update_communication(dt.datetime(2023, 12, 1), {bob})
    file = File("README.md")
    file.add_edit(dt.datetime(2023, 12, 2), alice)
    file.add_edit(dt.datetime(2023, 12, 3), bob)
    return {"README.md": file}, {1: alice, 2: bob}


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
    assert (data["owner"], data["repo"], data["starting_date"]) == (owner, repo_name, starting_date)
    assert set(data["files"]) == {"README.md"}
    assert set(data["users"]) == {1, 2}
    # gli utenti condivisi restano lo stesso oggetto anche dopo il caricamento
    bob = data["users"][2]
    assert bob in data["users"][1].communications[dt.datetime(2023, 12, 1)]
    assert data["files"]["README.md"].modified_by[dt.datetime(2023, 12, 2)] is data["users"][1]


def test_save_load_data_partial(tmp_path):
    files, _ = create_sample_data()
    path = str(tmp_path / "dati.graphapp")
    save_data(path, owner, repo_name, starting_date, files, None)
    data = load_data(path)
    assert data["users"] is None
    assert len(data["files"]) == 1


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
    with open(path, 'wb') as fp:
        pickle.dump({'key1': 'value1'}, fp)
    with pytest.raises(ValueError):
        load_data(str(path))


class Malicious:
    def __reduce__(self):
        return os.system, ("echo pwned",)


def test_load_data_forbidden_class(tmp_path):
    path = tmp_path / "malevolo.graphapp"
    with open(path, 'wb') as fp:
        pickle.dump({"format": "graphapp-data", "version": 1, "files": Malicious()}, fp)
    with pytest.raises(ValueError):
        load_data(str(path))


def test_load_data_nonexistent_file(tmp_path):
    with pytest.raises(OSError):
        load_data(str(tmp_path / "inesistente.graphapp"))


def test_update_communications_ok():
    for pull in mock_get_pulls_since.return_value:
        update_communications(response=pull, all_users=all_users, starting_date=starting_date)
        assert len(all_users) > 1


def test_update_communications_none_response():
    try:
        update_communications(response=None, all_users=all_users, starting_date=starting_date)
        assert False
    except AttributeError:
        assert True


def test_update_communications_empty_response():
    all_users = {1: user}
    update_communications(response={}, all_users=all_users, starting_date=starting_date)
    assert all_users == {1: user}


def test_update_communications_bad_formatted_response():
    try:
        update_communications(response=response_getpulls_bad_formatted, all_users=all_users, starting_date=None)
        assert False
    except TypeError:
        assert True


def test_update_communications_none_all_users():
    try:
        for pull in mock_get_pulls_since.return_value:
            update_communications(response=pull, all_users=None, starting_date=starting_date)
        assert False
    except TypeError:
        assert True


def test_update_communications_empty_all_users():
    for pull in mock_get_pulls_since.return_value:
        update_communications(response=pull, all_users={}, starting_date=starting_date)
    assert len(all_users) > 0


def test_update_communications_none_starting_date():
    try:
        for pull in mock_get_pulls_since.return_value:
            update_communications(response=pull, all_users=all_users, starting_date=None)
        assert False
    except TypeError:
        assert True


def test_update_communications_out_range_starting_date():
    for pull in mock_get_pulls_since.return_value:
        update_communications(response=pull, all_users=all_users, starting_date=starting_date_out)
    assert len(all_users) == 3  # verranno aggiunti dal mock altri 2 utenti


def test_communication_happened_ok():
    for pull in mock_get_pulls_since.return_value:
        communication_happened(response=pull)
    assert True


def test_communication_happened_none_response():
    try:
        communication_happened(response=None)
        assert False
    except TypeError:
        assert True


def test_communication_happened_empty_response():
    result = communication_happened(response={})
    assert result is False


def test_communication_happened_bad_formatted_response():
    try:
        communication_happened(response=response_getpulls_bad_formatted)
        assert False
    except TypeError:
        assert True


def test_get_communications_since_ok():
    all_users_res = get_communications_since(owner, repo_name, dt.datetime(year=2023, month=11, day=1), token)
    assert len(all_users_res) > 0  # va fatto meglio, non basta controllare se non vuota


def test_get_communications_since_owner_none():
    try:
        get_communications_since(None, repo_name, starting_date, token)
        assert False
    except TypeError:
        assert True


def test_get_communications_since_owner_nonexistent():
    all_users_res = get_communications_since("", repo_name, starting_date, token)
    assert len(all_users_res) == 0


def test_get_communications_since_repo_none():
    try:
        get_communications_since(owner, None, starting_date, token)
        assert False
    except TypeError:
        assert True


def test_get_communications_since_repo_nonexistent():
    all_users_res1 = get_communications_since(owner, "", starting_date, token)
    assert len(all_users_res1) == 0


def test_get_communications_since_date_none():
    try:
        get_communications_since(owner="fullmoonlullaby", repo_name="test",
                                 starting_date=None, token=token)
        assert False
    except TypeError:
        assert True


def test_get_communications_since_date_now():
    all_users_res = get_communications_since(owner="fullmoonlullaby", repo_name="test",
                                             starting_date=starting_date_out, token=token)
    assert len(all_users_res) == 0


def test_get_communications_since_token_none():
    try:
        get_communications_since(owner="fullmoonlullaby", repo_name="test",
                                 starting_date=starting_date, token=None)
        assert False
    except TypeError:
        assert True


def test_get_communications_since_token_nonexistent():
    all_users_res = get_communications_since(owner="fullmoonlullaby", repo_name="test",
                                             starting_date=starting_date, token='token_sbagliato')

    assert len(all_users_res) == 0


# *****************************************************************************************************


def test_get_collaborations_since_ok():
    files = get_collaborations_since(owner, repo_name, dt.datetime(year=2023, month=11, day=1), token)
    assert len(files) > 0


def test_get_collaborations_since_owner_none():
    try:
        get_collaborations_since(None, repo_name, starting_date, token)
        assert False
    except TypeError:
        assert True


def test_get_collaborations_since_owner_nonexistent():
    files = get_collaborations_since("", repo_name, starting_date, token)
    assert len(files) == 0


def test_get_collaborations_since_repo_none():
    try:
        get_collaborations_since(owner, None, starting_date, token)
        assert False
    except TypeError:
        assert True


def test_get_collaborations_since_repo_nonexistent():
    files = get_collaborations_since(owner, "", starting_date, token)
    assert len(files) == 0


def test_get_collaborations_since_date_none():
    try:
        get_collaborations_since(owner="fullmoonlullaby", repo_name="test",
                                 starting_date=None, token=token)
        assert False
    except AttributeError:
        assert True


def test_get_collaborations_since_date_now():
    files = get_collaborations_since(owner="fullmoonlullaby", repo_name="test",
                                     starting_date=starting_date_out, token=token)
    assert len(files) == 0


def test_get_collaborations_since_token_none():
    try:
        get_collaborations_since(owner="fullmoonlullaby", repo_name="test",
                                 starting_date=starting_date, token=None)
        assert False
    except TypeError:
        assert True


def test_get_collaborations_since_token_nonexistent():
    files = get_collaborations_since(owner="fullmoonlullaby", repo_name="test",
                                     starting_date=starting_date, token='token_sbagliato')

    assert len(files) == 0
