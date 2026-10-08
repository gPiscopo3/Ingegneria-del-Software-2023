import csv
import datetime as dt
import os

import networkx as nx
import pytest
import scipy.io

from src.logic import Export
from src.logic.DataManagement import load_data
from src.model.File import File
from src.model.User import User

START, END = dt.datetime(2023, 12, 1), dt.datetime(2023, 12, 31, 23, 59, 59)
EXAMPLE = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "examples", "apache_commons-io.graphapp")


def sample_data():
    # alice e bob collaborano su a.py; carol risponde a bob due volte; bob risponde a alice; dave solo fuori intervallo
    alice, bob, carol, dave = User(1, "alice"), User(2, "bob"), User(3, "carol"), User(4, "dave")
    a, b = File("a.py"), File("b.py")
    a.add_edit(dt.datetime(2023, 12, 2), alice)
    a.add_edit(dt.datetime(2023, 12, 3), bob)
    b.add_edit(dt.datetime(2023, 12, 4), carol)
    b.add_edit(dt.datetime(2024, 2, 1), dave)  # fuori intervallo
    carol.update_communication(dt.datetime(2023, 12, 5), {bob})
    carol.update_communication(dt.datetime(2023, 12, 6), {bob})
    bob.update_communication(dt.datetime(2023, 12, 7), {alice})
    files = {"a.py": a, "b.py": b}
    users = {1: alice, 2: bob, 3: carol}
    return files, users


def test_collaboration_graph():
    files, users = sample_data()
    g = Export.build_export_graph("collaborazioni", files, users, START, END)
    assert not g.is_directed()
    assert set(g.edges) == {("alice", "bob")} or set(g.edges) == {("bob", "alice")}
    assert g.edges["alice", "bob"]["weight"] == 1
    assert g.nodes["alice"]["github_id"] == 1


def test_communication_graph_directed_with_degrees():
    files, users = sample_data()
    g = Export.build_export_graph("comunicazioni", files, users, START, END)
    assert g.is_directed()
    assert g.edges["carol", "bob"]["weight"] == 2
    assert g.edges["bob", "alice"]["weight"] == 1
    assert g.nodes["bob"]["in_degree"] == 1 and g.nodes["bob"]["out_degree"] == 1
    assert g.nodes["carol"]["strength"] == 2


def test_composite_graph_keeps_both_weights():
    files, users = sample_data()
    g = Export.build_export_graph("composito", files, users, START, END)
    both = g.edges["alice", "bob"]  # collaborano e bob risponde ad alice
    assert (both["type"], both["weight_collaboration"], both["weight_communication"], both["weight"]) == \
           ("both", 1, 1, 2)
    only_communication = g.edges["carol", "bob"]
    assert (only_communication["type"], only_communication["weight"]) == ("communication", 2)


def test_composite_same_structure_as_shown_graph():
    from src.gui.graph import create_composite_graph  # pylint: disable=import-outside-toplevel
    data = load_data(EXAMPLE)
    start, end = dt.datetime(2023, 11, 15), dt.datetime(2023, 12, 18, 23, 59, 59)
    shown = create_composite_graph("o", "r", start, "", start, end, data["files"], data["users"])[0]
    exported = Export.build_export_graph("composito", data["files"], data["users"], start, end)
    assert set(map(frozenset, shown.edges)) == set(map(frozenset, exported.edges))
    assert set(shown.nodes) == set(exported.nodes)


def test_unknown_kind():
    with pytest.raises(ValueError):
        Export.build_export_graph("altro", {}, {}, START, END)


def test_nodes_edges_csv(tmp_path):
    files, users = sample_data()
    g = Export.build_export_graph("composito", files, users, START, END)
    nodes_path, edges_path = tmp_path / "nodes.csv", tmp_path / "edges.csv"
    Export.write_nodes_edges_csv(g, str(nodes_path), str(edges_path))
    with open(nodes_path, encoding="utf-8") as fp:
        nodes = list(csv.DictReader(fp))
    with open(edges_path, encoding="utf-8") as fp:
        edges = list(csv.DictReader(fp))
    assert {n["name"] for n in nodes} == {"alice", "bob", "carol"}
    assert [n["id"] for n in nodes] == ["1", "2", "3"]
    assert len(edges) == g.number_of_edges()
    assert set(edges[0]) == {"source", "target", "weight", "weight_collaboration", "weight_communication", "type"}


def test_graphml_roundtrip(tmp_path):
    files, users = sample_data()
    g = Export.build_export_graph("comunicazioni", files, users, START, END)
    info = Export.graph_info("comunicazioni", "o", "r", START, END, True)
    path = str(tmp_path / "g.graphml")
    Export.write_graphml(g, path, info)
    back = nx.read_graphml(path)
    assert back.is_directed()
    assert back.edges["carol", "bob"]["weight"] == 2
    assert back.graph["repository"] == "o/r"
    assert back.graph["interval_start"] == "2023-12-01T00:00:00Z"
    assert back.nodes["alice"]["github_id"] == 1


def test_mat_undirected_symmetric(tmp_path):
    files, users = sample_data()
    g = Export.build_export_graph("composito", files, users, START, END)
    path = str(tmp_path / "g.mat")
    Export.write_mat(g, path, Export.graph_info("composito", "o", "r", START, END, False))
    m = scipy.io.loadmat(path, squeeze_me=True)
    a = m["A"].toarray()
    assert (a == a.T).all()  # MATLAB graph() richiede una matrice simmetrica
    assert a.sum() == 2 * sum(w for _, _, w in g.edges(data="weight"))
    assert list(m["names"]) == list(g.nodes)
    assert "A_collaboration" in m and "A_communication" in m
    assert m["info"]["graph_type"] == "composito"


def test_mat_directed(tmp_path):
    files, users = sample_data()
    g = Export.build_export_graph("comunicazioni", files, users, START, END)
    path = str(tmp_path / "g.mat")
    Export.write_mat(g, path, Export.graph_info("comunicazioni", "o", "r", START, END, True))
    m = scipy.io.loadmat(path, squeeze_me=True)
    names = list(m["names"])
    a = m["A"].toarray()
    assert a[names.index("carol"), names.index("bob")] == 2
    assert a[names.index("bob"), names.index("carol")] == 0
    assert list(m["weight"]) == [w for _, _, w in g.edges(data="weight")]


def test_edits_csv_only_in_range(tmp_path):
    files, _ = sample_data()
    path = str(tmp_path / "edits.csv")
    assert Export.write_edits_csv(files, START, END, path) == 3  # la modifica di dave è fuori intervallo
    with open(path, encoding="utf-8") as fp:
        rows = list(csv.DictReader(fp))
    assert rows[0] == {"developer": "alice", "developer_id": "1", "file": "a.py", "timestamp": "2023-12-02T00:00:00Z"}


def test_interactions_csv(tmp_path):
    _, users = sample_data()
    path = str(tmp_path / "interactions.csv")
    assert Export.write_interactions_csv(users, START, END, path) == 3
    with open(path, encoding="utf-8") as fp:
        rows = list(csv.DictReader(fp))
    assert [(r["source"], r["target"]) for r in rows] == [("carol", "bob"), ("carol", "bob"), ("bob", "alice")]


def export_context():
    files, users = sample_data()
    return {"owner": "o", "repo": "r", "kind": "composito", "start": START, "end": END, "files": files,
            "users": users}


ALL_KEYS = ["csv", "graphml", "mat", "edits", "interactions"]


def test_export_more_modes_single_zip(tmp_path):
    import zipfile  # pylint: disable=import-outside-toplevel
    created = Export.export_files(export_context(), ALL_KEYS, str(tmp_path), "dati")
    assert created == [str(tmp_path / "dati.zip")]
    assert sorted(os.listdir(tmp_path)) == ["dati.zip"]  # nessun file sciolto né temporaneo
    with zipfile.ZipFile(created[0]) as archive:
        assert sorted(archive.namelist()) == sorted(Export.file_names(ALL_KEYS, "dati"))
        archive.extractall(tmp_path / "estratti")
    g = nx.read_graphml(str(tmp_path / "estratti" / "dati.graphml"))
    assert g.edges["alice", "bob"]["type"] == "both"
    m = scipy.io.loadmat(str(tmp_path / "estratti" / "dati.mat"), squeeze_me=True)
    assert m["info"]["repository"] == "o/r"


def test_export_single_mode_without_zip(tmp_path):
    created = Export.export_files(export_context(), ["graphml"], str(tmp_path), "dati")
    assert created == [str(tmp_path / "dati.graphml")]
    assert os.listdir(tmp_path) == ["dati.graphml"]


def test_export_csv_alone_two_files(tmp_path):
    created = Export.export_files(export_context(), ["csv"], str(tmp_path), "dati")
    assert sorted(os.path.basename(p) for p in created) == ["dati_edges.csv", "dati_nodes.csv"]
    assert sorted(os.listdir(tmp_path)) == ["dati_edges.csv", "dati_nodes.csv"]


def test_output_names():
    assert Export.output_names(ALL_KEYS, "dati") == ["dati.zip"]
    assert Export.output_names(["mat"], "dati") == ["dati.mat"]
    assert Export.output_names(["csv"], "dati") == ["dati_nodes.csv", "dati_edges.csv"]


def test_export_no_modes(tmp_path):
    with pytest.raises(ValueError):
        Export.export_files(export_context(), [], str(tmp_path), "dati")
