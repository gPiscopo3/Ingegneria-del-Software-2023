import json
import os
import pickle
import datetime as dt
from typing import Dict
from unittest.mock import MagicMock

from logic import APICalls
from model.User import User
from src.logic.DataManagement import save_all_user, update_communications, communication_happened, \
    get_communications_since, get_collaborations_since

filename = "file"
dict = {'key1': 'value1', 'key2': 'value2'}
owner = "apache"
repo_name = "commons-io"
token = "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"
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


def test_save_all_user_ok():
    save_all_user(filename, dict)
    with open(filename, 'rb') as fp:
        item = pickle.load(fp)
    os.remove(filename)
    assert (item == 'value1')


def test_save_all_user_none_type():
    save_all_user(None, dict)
    assert os.path.exists(filename) == False


def test_save_all_user_wrong_dict():
    save_all_user(filename, 'dict')
    assert os.path.exists(filename) == False


def test_save_all_user_empty_dict():
    save_all_user(filename, {})
    assert os.path.exists(filename) == False


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
    all_users_res = get_communications_since(owner, repo_name, starting_date, token)
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
        assert True  # passa solo se non c'è la repo nella cache per cui si fa la chiamata


def test_get_communications_since_date_now():
    all_users_res = get_communications_since(owner="fullmoonlullaby", repo_name="test",
                                             starting_date=starting_date_out, token=token)
    assert len(all_users_res) == 0  # passa solo se non c'è la repo nella cache per cui si fa la chiamata


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

#*****************************************************************************************************


def test_get_collaborations_since_ok():
    files = get_collaborations_since(owner, repo_name, starting_date, token)
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
        assert True  # passa solo se non c'è la repo nella cache per cui si fa la chiamata


def test_get_collaborations_since_date_now():
    files = get_collaborations_since(owner="fullmoonlullaby", repo_name="test",
                                             starting_date=starting_date_out, token=token)
    assert len(files) == 0  # passa solo se non c'è la repo nella cache per cui si fa la chiamata


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
