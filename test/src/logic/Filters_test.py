import datetime
from src.logic.DataManagement import load_data
from src.logic.Filters import communications_in_range, collaborations_in_range
import os

# dati di esempio inclusi nel repository: i test dei filtri non fanno chiamate alle API
EXAMPLE = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "examples", "apache_commons-io.graphapp")
data = load_data(EXAMPLE)
comm_locali = data["users"]
collab_locali = data["files"]


def test_communications_in_range_ok():
    adj = communications_in_range(datetime.datetime(2023, 11, 1),
                                  datetime.datetime(2023, 12, 19), comm_locali.values())
    assert (adj)  # passa se adj è non vuota


def test_communications_in_range_wrong_type():
    adj = communications_in_range(datetime.datetime(2023, 11, 1),
                                  datetime.datetime(2023, 12, 19), 5)
    assert (adj is None)


def test_communications_in_range_empty_users():
    adj = communications_in_range(datetime.datetime(2023, 11, 1),
                                  datetime.datetime(2023, 12, 19), {})
    assert (not adj)  # passa se adj è vuota


def test_communications_in_range_date_invertite():
    adj = communications_in_range(datetime.datetime(2023, 12, 1),
                                  datetime.datetime(2023, 11, 19), comm_locali.values())
    tmp = []
    for user, list_user in adj.items():
        if len(list_user) > 0:
            tmp.append(list_user)
    assert (not tmp)  # passa se tmp è vuota


def test_collaborations_in_range_ok():
    edges = collaborations_in_range(datetime.datetime(2023, 11, 1),
                                    datetime.datetime(2023, 12, 19), collab_locali.values())
    assert (edges)  # passa se edges è non vuoto


def test_collaborations_in_range_wrong_type():
    edges = collaborations_in_range(datetime.datetime(2023, 11, 1),
                                    datetime.datetime(2023, 12, 19), 5)
    assert (edges is None)


def test_collaborations_in_range_empty_users():
    edges = collaborations_in_range(datetime.datetime(2023, 11, 1),
                                    datetime.datetime(2023, 12, 19), {})
    assert (not edges)  # passa se edges è vuoto


def test_collaborations_in_range_date_invertite():
    edges = collaborations_in_range(datetime.datetime(2023, 12, 1),
                                    datetime.datetime(2023, 11, 19), collab_locali.values())
    assert (not edges)  # passa se edges è vuoto
