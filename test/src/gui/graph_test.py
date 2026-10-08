import networkx as nx

from src.gui.graph import compute_layout


def test_compute_layout_empty():
    assert compute_layout(nx.Graph()) == {}


def test_compute_layout_all_nodes():
    g = nx.path_graph(10)
    pos = compute_layout(g)
    assert set(pos) == set(g.nodes)


def test_compute_layout_large_graph_is_deterministic():
    # nei grafi grandi si usano meno iterazioni, ma la disposizione resta riproducibile (seed fisso)
    g = nx.gnm_random_graph(600, 1500, seed=1)
    first, second = compute_layout(g), compute_layout(g)
    assert all((first[n] == second[n]).all() for n in g.nodes)
