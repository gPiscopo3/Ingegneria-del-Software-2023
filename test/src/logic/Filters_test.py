import datetime
from src.logic.DataManagement import load_data
from src.logic.Filters import communications_in_range, collaborations_in_range
from src.model.File import File
from src.model.User import User
import os

# dati di esempio inclusi nel repository: i test dei filtri non fanno chiamate alle API
EXAMPLE = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "examples", "apache_commons-io.graphapp")

START, END = datetime.datetime(2023, 12, 1), datetime.datetime(2023, 12, 31)


def sample_users():
    # alice risponde a bob all'inizio dell'intervallo, bob ad alice alla fine, carol solo fuori intervallo
    alice, bob, carol = User(1, "alice"), User(2, "bob"), User(3, "carol")
    alice.update_communication(START, {bob})
    bob.update_communication(END, {alice, carol})
    carol.update_communication(datetime.datetime(2024, 1, 1), {alice})
    return alice, bob, carol


def sample_files():
    alice, bob, carol = User(1, "alice"), User(2, "bob"), User(3, "carol")
    shared, solo, outside = File("shared.py"), File("solo.py"), File("outside.py")
    shared.add_edit(START, alice)
    shared.add_edit(END, bob)
    solo.add_edit(datetime.datetime(2023, 12, 5), carol)  # più modifiche, un solo autore: nessuna coppia
    solo.add_edit(datetime.datetime(2023, 12, 6), carol)
    outside.add_edit(datetime.datetime(2023, 11, 30), alice)  # una modifica prima dell'intervallo
    outside.add_edit(datetime.datetime(2023, 12, 10), carol)
    return [shared, solo, outside], (alice, bob, carol)


def names(users):
    return sorted(u.username for u in users)


def test_communications_in_range_ok():
    alice, bob, carol = sample_users()
    adj = communications_in_range(START, END, [alice, bob, carol])
    assert names(adj[alice]) == ["bob"]  # estremo iniziale incluso
    assert names(adj[bob]) == ["alice", "carol"]  # estremo finale incluso
    assert adj[carol] == []  # comunicazione fuori intervallo


def test_communications_in_range_example_data():
    data = load_data(EXAMPLE)
    adj = communications_in_range(datetime.datetime(2023, 11, 1), datetime.datetime(2023, 12, 19),
                                  data["users"].values())
    assert len(adj) == 11  # una voce per ogni utente
    assert sum(1 for receivers in adj.values() if receivers) == 4
    assert sum(len(receivers) for receivers in adj.values()) == 14


def test_communications_in_range_wrong_type():
    adj = communications_in_range(START, END, 5)
    assert (adj is None)


def test_communications_in_range_empty_users():
    adj = communications_in_range(START, END, {})
    assert adj == {}


def test_communications_in_range_date_invertite():
    adj = communications_in_range(END, START, list(sample_users()))
    assert all(receivers == [] for receivers in adj.values())


def test_collaborations_in_range_ok():
    files, (alice, bob, _) = sample_files()
    edges = collaborations_in_range(START, END, files)
    # solo shared.py: solo.py ha un unico autore, outside.py ha un solo autore nell'intervallo
    assert len(edges) == 1
    assert [set(pair) for pair in edges[0]] == [{alice, bob}]


def test_collaborations_in_range_example_data():
    data = load_data(EXAMPLE)
    edges = collaborations_in_range(datetime.datetime(2023, 11, 1), datetime.datetime(2023, 12, 19),
                                    data["files"].values())
    assert len(edges) == 7  # file con almeno due autori
    assert sum(len(pairs) for pairs in edges) == 11


def test_collaborations_in_range_wrong_type():
    edges = collaborations_in_range(START, END, 5)
    assert (edges is None)


def test_collaborations_in_range_empty_users():
    edges = collaborations_in_range(START, END, {})
    assert edges == []


def test_collaborations_in_range_date_invertite():
    files, _ = sample_files()
    edges = collaborations_in_range(END, START, files)
    assert edges == []
