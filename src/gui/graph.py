import math
from collections import Counter
from typing import Dict
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
import networkx as nx
import numpy as np
from datetime import datetime
from src.gui.style import matplotlib_colors
from src.logic.DataManagement import get_collaborations_since, get_communications_since
from src.logic.Filters import collaborations_in_range, communications_in_range


def create_graph(owner: str, repo_name: str, starting_date: datetime, token: str, datai: datetime, dataf: datetime,
                 files):
    if files is None:
        files = get_collaborations_since(owner, repo_name, starting_date, token)
    collaborations = collaborations_in_range(datai, dataf, files.values())
    # print(collaborations)

    lista_trasformata = [
        [tuple(sorted((coppia[0], coppia[1]), key=lambda x: x.username)) for coppia in lista]
        for lista in collaborations
    ]

    conteggi_totali = Counter([item for sublist in lista_trasformata for item in sublist])

    G = nx.Graph()

    for coppia, conteggio in conteggi_totali.items():

        if conteggio > 0:
            G.add_edge(coppia[0].username, coppia[1].username, weight=conteggio)

    return G, files


def create_graph_communication(owner: str, repo_name: str, starting_date: datetime, token: str, datai: datetime,
                               dataf: datetime, all_users):
    if all_users is None:
        all_users = get_communications_since(owner, repo_name, starting_date, token)
    communications = communications_in_range(datai, dataf, all_users.values())  # mappa di adiacenza : Dict[User, List[User]]
    lista_archi_diretti = create_directed_edges(communications)
    conteggi_totali = Counter(lista_archi_diretti)
    G = nx.DiGraph()
    for coppia, conteggio in conteggi_totali.items():

        if conteggio > 0:
            G.add_edge(coppia[0].username, coppia[1].username, weight=conteggio)

    return G, all_users


MAX_EDGE_LABELS = 150  # oltre questa soglia le etichette dei pesi renderebbero il grafo illeggibile
LARGE_GRAPH_NODES = 150  # oltre questa soglia il grafo viene disegnato in modo alleggerito
MAX_NODE_LABELS = 40  # nei grafi grandi, etichette solo per i nodi più collegati (gli altri al passaggio del mouse)
MAX_ARROW_EDGES = 300  # oltre questa soglia gli archi diretti si disegnano senza frecce (una sola collezione)


# disposizione dei nodi: con molti nodi meno iterazioni (il costo cresce col quadrato dei nodi)
def compute_layout(G):
    n = G.number_of_nodes()
    if n == 0:
        return {}
    iterations = 50 if n <= 300 else max(15, 50 * 300 // n)
    return nx.spring_layout(G, seed=42, k=2 / math.sqrt(n), iterations=iterations)


class GraphWidget(QWidget):
    # pos: disposizione già calcolata (es. al cambio tema), altrimenti viene calcolata qui
    def __init__(self, G, flag: int, edge_color: [], dark: bool = True, pos=None):
        super().__init__()
        self.pos = pos if pos is not None else compute_layout(G)
        self.fig = None
        self.canvas = None
        self.toolbar = None
        self.annotation = None
        self.background = None
        self.hover_index = None
        self.node_names = []
        self.node_coords = None
        self.node_radius = None
        self.initUI(G, flag, edge_color, dark)

    def initUI(self, G, flag, edge_color, dark):
        colors = matplotlib_colors(dark)

        # Creazione di un layout verticale per il widget
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Creazione della figura per il grafo (Figure e non pyplot, per non accumulare figure globali)
        fig = self.fig = Figure(facecolor=colors["background"])
        ax = self.ax = fig.add_subplot(111)
        ax.set_facecolor(colors["background"])
        ax.set_axis_off()
        canvas = self.canvas = FigureCanvasQTAgg(fig)

        # Toolbar per zoom, spostamento e salvataggio dell'immagine
        self.toolbar = NavigationToolbar2QT(canvas, self)
        layout.addWidget(self.toolbar)
        layout.addWidget(canvas)

        if G.number_of_nodes() == 0:
            ax.text(0.5, 0.5, "Nessuna interazione nell'intervallo selezionato", ha='center', va='center',
                    color=colors["text"], fontsize=11, transform=ax.transAxes)
            return

        # Disegno del grafo sulla figura: nei grafi grandi stile alleggerito, perché ogni zoom o spostamento
        # ridisegna tutti gli elementi
        pos = self.pos
        large = G.number_of_nodes() > LARGE_GRAPH_NODES
        degrees = dict(G.degree)
        max_degree = max(degrees.values(), default=1)
        if large:
            node_sizes = [15 + 600 * math.sqrt(degrees[n] / max_degree) for n in G.nodes]
        else:
            node_sizes = [min(300 + 120 * degrees[n], 3000) for n in G.nodes]
        weights = nx.get_edge_attributes(G, 'weight')
        max_weight = max(weights.values(), default=1)
        if large:
            widths = [0.4 + 1.6 * weights.get(e, 1) / max_weight for e in G.edges]
        else:
            widths = [1 + 3 * weights.get(e, 1) / max_weight for e in G.edges]

        if flag == 1:
            edge_colors = colors["edge"]
        elif flag == 2:
            edge_colors = colors["communications"]
        else:
            palette_map = {'blue': colors["collaborations"], 'red': colors["communications"],
                           'purple': colors["composite"]}
            edge_colors = [palette_map.get(c, c) for c in edge_color]

        edge_options = dict(ax=ax, width=widths, edge_color=edge_colors, alpha=0.35 if large else 0.75,
                            node_size=node_sizes)
        arrows = flag == 2 and G.number_of_edges() <= MAX_ARROW_EDGES
        if arrows:
            # ogni freccia è un oggetto grafico separato: solo con pochi archi
            edge_options.update(arrows=True, arrowstyle='-|>', arrowsize=12, connectionstyle='arc3, rad = 0.08')
        elif flag == 2:
            edge_options.update(arrows=False)  # un'unica collezione di linee, molto più veloce da ridisegnare
        nx.draw_networkx_edges(G, pos, **edge_options)
        nx.draw_networkx_nodes(G, pos, ax=ax, node_size=node_sizes, node_color=colors["node"],
                               edgecolors=colors["node_border"], linewidths=0.5 if large else 1.5)

        # etichette: tutte nei grafi piccoli, solo i nodi più collegati in quelli grandi
        labeled = list(G.nodes)
        if large:
            labeled = sorted(G.nodes, key=lambda n: degrees[n], reverse=True)[:MAX_NODE_LABELS]
        label_pos = {n: (pos[n][0], pos[n][1] + 0.045) for n in labeled}  # etichette sopra i nodi
        nx.draw_networkx_labels(G, label_pos, labels={n: n for n in labeled}, ax=ax, font_size=8,
                                font_color=colors["text"], verticalalignment='bottom',
                                bbox=dict(boxstyle='round,pad=0.2', fc=colors["label_bg"], ec='none', alpha=0.8))

        if G.number_of_edges() <= MAX_EDGE_LABELS and flag != 3:
            nx.draw_networkx_edge_labels(G, pos, ax=ax, edge_labels=weights, font_size=7,
                                         font_color=colors["text"], label_pos=0.4 if flag == 2 else 0.5,
                                         bbox=dict(boxstyle='round,pad=0.15', fc=colors["background"], ec='none'))

        if flag == 3:
            legend_labels = {'Collaborazioni': colors["collaborations"], 'Comunicazioni': colors["communications"],
                             'Entrambe': colors["composite"]}
            legend_handles = [Line2D([0], [0], color=color, linewidth=3, label=label)
                              for label, color in legend_labels.items()]
            legend = ax.legend(handles=legend_handles, title="Tipi di collegamenti", loc='best',
                               facecolor=colors["label_bg"], edgecolor=colors["label_bg"], labelcolor=colors["text"])
            legend.get_title().set_color(colors["text"])

        if large:
            note = f"Grafo grande: etichette solo per i {MAX_NODE_LABELS} nodi più collegati"
            if flag == 2 and not arrows:
                note += ", archi senza frecce"
            ax.text(0.01, 0.01, note + " · passa il mouse su un nodo per il nome", transform=ax.transAxes,
                    fontsize=7, color=colors["text"], alpha=0.7)

        self.setup_hover(G, degrees, node_sizes, colors)
        fig.tight_layout()

    # nome del nodo al passaggio del mouse; disegnato con il blitting, senza ridisegnare tutto il grafo
    def setup_hover(self, G, degrees, node_sizes, colors):
        self.node_names = [f"{n}\n{degrees[n]} collegamenti" for n in G.nodes]
        self.node_coords = np.array([self.pos[n] for n in G.nodes])
        # raggio in pixel di ogni nodo (la dimensione dei marker è un'area in punti²), almeno 6 px
        self.node_radius = np.maximum(np.sqrt(np.array(node_sizes)) / 2 * self.fig.dpi / 72, 6)
        self.annotation = self.ax.annotate("", xy=(0, 0), xytext=(10, 10), textcoords="offset points",
                                           fontsize=8, color=colors["text"], zorder=10, visible=False,
                                           bbox=dict(boxstyle='round,pad=0.3', fc=colors["label_bg"], ec='none'))
        self.annotation.set_animated(True)  # escluso dal disegno normale: si aggiunge sopra lo sfondo salvato
        self.canvas.mpl_connect("draw_event", self.on_draw)
        self.canvas.mpl_connect("motion_notify_event", self.on_hover)

    def on_draw(self, _event):
        self.background = self.canvas.copy_from_bbox(self.fig.bbox)
        self.hover_index = None

    def on_hover(self, event):
        if self.background is None or self.toolbar.mode:  # durante zoom/spostamento niente etichette
            return
        index = None
        if event.inaxes is self.ax:
            screen = self.ax.transData.transform(self.node_coords)
            distances = np.hypot(screen[:, 0] - event.x, screen[:, 1] - event.y)
            nearest = int(np.argmin(distances))
            if distances[nearest] <= self.node_radius[nearest]:
                index = nearest
        if index == self.hover_index:
            return
        self.hover_index = index
        self.canvas.restore_region(self.background)
        if index is not None:
            self.annotation.xy = self.node_coords[index]
            self.annotation.set_text(self.node_names[index])
            self.annotation.set_visible(True)
            self.ax.draw_artist(self.annotation)
        self.canvas.blit(self.fig.bbox)

    # libera subito figura e artisti quando il widget viene sostituito
    def release(self):
        if self.fig is not None:
            self.fig.clear()
        self.background = None


def create_composite_graph(owner: str, repo_name: str, starting_date: datetime, token: str, datai: datetime,
                           dataf: datetime,
                           files: dict, all_users):
    g1, files = create_graph(owner, repo_name, starting_date, token, datai, dataf,
                             files)
    g2, all_users = create_graph_communication(owner, repo_name, starting_date, token, datai,
                                               dataf, all_users)

    g2 = g2.to_undirected()

    merged_graph = nx.compose(g1, g2)

    # Assegna colori diversi agli archi di g1 e g2
    edge_colors = []
    for edge in merged_graph.edges:
        if edge in g1.edges and edge in g2.edges:
            # Arco presente in entrambi i grafi
            edge_colors.append('purple')
        elif edge in g1.edges:
            # Arco presente solo in g1
            edge_colors.append('blue')
        elif edge in g2.edges:
            # Arco presente solo in g2
            edge_colors.append('red')

    return merged_graph, files, all_users, edge_colors


def create_directed_edges(adj_map: Dict):
    edges = []
    for user, list_user in adj_map.items():
        for receiver in list_user:
            tup = (user, receiver)
            edges.append(tup)
    return edges
