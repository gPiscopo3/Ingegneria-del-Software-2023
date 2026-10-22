import struct
from xml.etree import ElementTree

import networkx as nx

from src.gui.graph import compute_layout, draw_graph, save_graph_image
from src.gui.style import matplotlib_colors


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


def test_draw_graph_empty_returns_none():
    from matplotlib.figure import Figure  # pylint: disable=import-outside-toplevel
    ax = Figure().add_subplot(111)
    assert draw_graph(ax, nx.Graph(), 1, None, matplotlib_colors(False), {}) is None


def test_draw_graph_large_directed():
    from matplotlib.figure import Figure  # pylint: disable=import-outside-toplevel
    g = nx.gnm_random_graph(400, 900, seed=2, directed=True)
    nx.set_edge_attributes(g, 1, "weight")
    ax = Figure().add_subplot(111)
    degrees, sizes = draw_graph(ax, g, 2, None, matplotlib_colors(True), compute_layout(g))
    assert len(degrees) == len(sizes) == 400


def sample_composite():
    g = nx.Graph()
    g.add_edge("alice", "bob", weight=2)
    g.add_edge("bob", "carol", weight=1)
    return g, ["purple", "red"]


def test_save_graph_image_png(tmp_path):
    g, colors = sample_composite()
    path = str(tmp_path / "g.png")
    save_graph_image(path, g, 3, colors, compute_layout(g), title="o/r · composite", dpi=100)
    with open(path, "rb") as fp:
        header = fp.read(24)
    assert header[:8] == b"\x89PNG\r\n\x1a\n"
    width, height = struct.unpack(">II", header[16:24])
    assert (width, height) == (1200, 900)  # 12x9 pollici a 100 dpi


def test_save_graph_image_svg_and_pdf(tmp_path):
    g, colors = sample_composite()
    save_graph_image(str(tmp_path / "g.svg"), g, 3, colors, None)
    assert ElementTree.parse(str(tmp_path / "g.svg")).getroot().tag.endswith("svg")
    save_graph_image(str(tmp_path / "g.pdf"), g, 3, colors, None)
    with open(tmp_path / "g.pdf", "rb") as fp:
        assert fp.read(5) == b"%PDF-"
