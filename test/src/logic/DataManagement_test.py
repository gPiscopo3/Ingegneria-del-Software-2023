import os
import pickle

from src.logic.DataManagement import save_all_user

filename = "file"
dict = {'key1': 'value1', 'key2': 'value2'}


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
