import datetime
from src.logic.DataManagement import get_communications_since, get_collaborations_since
from src.logic.Filters import communications_in_range, collaborations_in_range
import os

TOKEN = os.environ['GH_TOKEN']
header = {"Authorization": "Bearer " + TOKEN}
dt = datetime.datetime(2023, 12, 13)

comm_locali = get_communications_since("apache", "commons-io", dt, TOKEN)
collab_locali = get_collaborations_since("apache", "commons-io", dt, TOKEN)


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
